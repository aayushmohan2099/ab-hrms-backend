from datetime import date
import calendar
from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from core.models import SalaryStructure
from employees.models import EmployeeProfile
from attendance.models import DailyAttendance
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from payroll.models import DesignationPayrollRule, PayrollRun, PayrollRecord
from departments.models import Department
from .serializers import (
    DesignationPayrollRuleSerializer, 
    PayrollRunSerializer, 
    PayrollRecordSerializer
)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

# --- Designation Payroll Rules ---
class DesignationRuleListView(generics.ListAPIView):
    serializer_class = DesignationPayrollRuleSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        return DesignationPayrollRule.objects.filter(
            designation__department_id=dept_id, is_active=True
        ).order_by('designation__name')

class DesignationRuleCreateView(generics.CreateAPIView):
    serializer_class = DesignationPayrollRuleSerializer

    def perform_create(self, serializer):
        dept_id = self.kwargs.get('dept_id')
        designation = serializer.validated_data.get('designation')
        if designation.department_id != int(dept_id):
            raise ValidationError({"designation": "Designation does not belong to this department."})
        serializer.save(created_by=self.request.user)

class DesignationRuleUpdateView(generics.UpdateAPIView):
    serializer_class = DesignationPayrollRuleSerializer
    lookup_field = 'id'

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        return DesignationPayrollRule.objects.filter(designation__department_id=dept_id, is_active=True)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

class DesignationRuleDeleteView(generics.DestroyAPIView):
    lookup_field = 'id'

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        return DesignationPayrollRule.objects.filter(designation__department_id=dept_id, is_active=True)

    def perform_destroy(self, instance):
        instance.delete(by_user=self.request.user)


# --- Payroll Runs ---
class PayrollRunListView(generics.ListAPIView):
    serializer_class = PayrollRunSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        return PayrollRun.objects.filter(department_id=dept_id, is_active=True).order_by('-pay_year', '-pay_month')

class PayrollRunCreateView(generics.CreateAPIView):
    serializer_class = PayrollRunSerializer

    def perform_create(self, serializer):
        dept_id = self.kwargs.get('dept_id')
        department = get_object_or_404(Department, id=dept_id, is_active=True)
        serializer.save(created_by=self.request.user, department=department)

class PayrollRunUpdateView(generics.UpdateAPIView):
    serializer_class = PayrollRunSerializer
    lookup_field = 'id'

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        return PayrollRun.objects.filter(department_id=dept_id, is_active=True)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

class PayrollRunDeleteView(generics.DestroyAPIView):
    lookup_field = 'id'

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        return PayrollRun.objects.filter(department_id=dept_id, is_active=True)

    def perform_destroy(self, instance):
        instance.delete(by_user=self.request.user)


# --- Payroll Records (Scoped by Department & Run) ---
class PayrollRecordListView(generics.ListAPIView):
    serializer_class = PayrollRecordSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        run_id = self.kwargs.get('run_id')
        return PayrollRecord.objects.filter(
            payroll_run__department_id=dept_id, 
            payroll_run_id=run_id, 
            is_active=True
        ).order_by('employee__user__employee_code')

class PayrollRecordCreateView(generics.CreateAPIView):
    serializer_class = PayrollRecordSerializer

    def perform_create(self, serializer):
        dept_id = self.kwargs.get('dept_id')
        run_id = self.kwargs.get('run_id')
        run = get_object_or_404(PayrollRun, id=run_id, department_id=dept_id, is_active=True)
        serializer.save(created_by=self.request.user, payroll_run=run)

class PayrollRecordUpdateView(generics.UpdateAPIView):
    serializer_class = PayrollRecordSerializer
    lookup_field = 'id'

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        run_id = self.kwargs.get('run_id')
        return PayrollRecord.objects.filter(
            payroll_run__department_id=dept_id, 
            payroll_run_id=run_id, 
            is_active=True
        )

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

class PayrollRecordDeleteView(generics.DestroyAPIView):
    lookup_field = 'id'

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        run_id = self.kwargs.get('run_id')
        return PayrollRecord.objects.filter(
            payroll_run__department_id=dept_id, 
            payroll_run_id=run_id, 
            is_active=True
        )

    def perform_destroy(self, instance):
        instance.delete(by_user=self.request.user)

# Payroll - Calculation Engine
class GeneratePayrollRecordsView(APIView):
    """
    Triggers the calculation engine for a specific PayrollRun.
    ABSENT days are immediate Loss of Pay.
    CASUAL and SICK leaves draw from a 15-day Financial Year allowance.
    Statutory Deductions (EPF, ESIC, TDS) are calculated on the Base Honorarium.
    Loss of Pay (LOP) is deducted to calculate Final Net Pay.
    """
    @transaction.atomic
    def post(self, request, dept_id, run_id):
        run = get_object_or_404(PayrollRun, id=run_id, department_id=dept_id, is_active=True)
        
        if run.status in ['APPROVED', 'LOCKED']:
            return Response({"detail": "Cannot regenerate records for an approved/locked run."}, status=status.HTTP_400_BAD_REQUEST)

        year = run.pay_year
        month = run.pay_month
        _, total_days_in_month = calendar.monthrange(year, month)
        today = date.today()

        # Determine Financial Year boundaries (April 1 to March 31)
        if month >= 4:
            fy_start_year = year
        else:
            fy_start_year = year - 1
        fy_start_date = date(fy_start_year, 4, 1)

        # Determine end of previous month for historical count
        if month == 1:
            last_month_end = date(year - 1, 12, 31)
        else:
            _, last_day_prev = calendar.monthrange(year, month - 1)
            last_month_end = date(year, month - 1, last_day_prev)

        # Get active employees in the department
        employees = EmployeeProfile.objects.select_related('designation').filter(
            department_id=dept_id, is_active=True
        )

        structure = run.salary_structure
        if not structure:
             return Response({"detail": "No Salary Structure linked to this run."}, status=status.HTTP_400_BAD_REQUEST)

        records_created = 0
        total_gross = 0
        total_deductions = 0
        total_net = 0

        for emp in employees:
            rule = DesignationPayrollRule.objects.filter(designation=emp.designation, is_active=True).first()
            
            # 1. Current Month Attendance
            att_records = DailyAttendance.objects.filter(
                employee=emp, date__year=year, date__month=month, is_active=True
            )
            prs_days = att_records.filter(status='PRESENT').count()
            weekends = att_records.filter(status='WEEKEND').count()
            holidays = att_records.filter(status='HOLIDAY').count()
            cl_days = att_records.filter(status='CASUAL_LEAVE').count()
            sl_days = att_records.filter(status='SICK_LEAVE').count()
            pl_days = att_records.filter(status='PAID_LEAVE').count()
            absent_db = att_records.filter(status='ABSENT').count()
            
            remaining_days = 0
            if today.year == year and today.month == month and today.day < total_days_in_month:
                remaining_days = total_days_in_month - today.day
            
            explicit_days = prs_days + weekends + holidays + cl_days + sl_days + pl_days + absent_db + remaining_days
            unmarked_past_days = max(0, total_days_in_month - explicit_days)
            
            # Unauthorized absences (Immediate Loss of Pay)
            current_month_absent_total = absent_db + unmarked_past_days
            
            # Authorized Leaves (Count against the 15-day allowance)
            current_month_allowance_leaves = cl_days + sl_days

            # 2. Historical Leave Usage (Authorized only)
            historical_leaves_used = DailyAttendance.objects.filter(
                employee=emp,
                date__gte=fy_start_date,
                date__lte=last_month_end,
                status__in=['CASUAL_LEAVE', 'SICK_LEAVE'],
                is_active=True
            ).count()

            # 3. Pro-ration Logic
            allowance_remaining = max(0, 15 - historical_leaves_used)
            
            # If they took more authorized leaves this month than they had left, the excess becomes deductible
            excess_leaves_this_month = max(0, current_month_allowance_leaves - allowance_remaining)
            
            # Total days to deduct salary for
            total_deductible_days = current_month_absent_total + excess_leaves_this_month
            effective_days = max(0, total_days_in_month - total_deductible_days)

            base_gross = float(emp.monthly_honorarium or 0)
            per_day_pay = base_gross / total_days_in_month if total_days_in_month else 0
            
            # Calculate Loss of Pay (LOP) amount
            lop_amount = round(total_deductible_days * per_day_pay, 2)

            # Gross pay is Base Honorarium minus LOP
            pro_rated_gross = max(0.0, round(base_gross - lop_amount, 2))

            # 4. Calculate Statutory Deductions (Calculated on Base Honorarium)
            epf_rate = float(structure.epf_rate) if rule and rule.applies_epf else 0
            esic_rate = float(structure.esic_rate) if rule and rule.applies_esic else 0
            tds_rate = float(structure.tds_rate) if rule and rule.applies_tds else 0

            epf_amt = round(base_gross * (epf_rate / 100), 2)
            esic_amt = round(base_gross * (esic_rate / 100), 2)
            tds_amt = round(base_gross * (tds_rate / 100), 2)
            
            emp_total_ded = epf_amt + esic_amt + tds_amt
            
            # Net Pay = Pro-rated Gross - Statutory Deductions
            net_pay = round(pro_rated_gross - emp_total_ded, 2)
            net_pay = max(0.0, net_pay) # Prevent negative salary

            # 5. Save Record
            PayrollRecord.objects.update_or_create(
                payroll_run=run,
                employee=emp,
                defaults={
                    'designation_snapshot': emp.designation.name,
                    'total_working_days': total_days_in_month,
                    'days_present': effective_days, 
                    'days_absent': total_deductible_days, 
                    'monthly_honorarium': base_gross,
                    'gross_pay': pro_rated_gross,
                    'tds_amount': tds_amt,
                    'epf_amount': epf_amt,
                    'esic_amount': esic_amt,
                    'total_deductions': emp_total_ded,
                    'net_pay': net_pay,
                    'status': 'COMPUTED',
                    'updated_by': request.user
                }
            )
            records_created += 1
            total_gross += pro_rated_gross
            total_deductions += emp_total_ded
            total_net += net_pay

        # Update Run Totals
        run.total_gross = total_gross
        run.total_deductions = total_deductions
        run.total_net = total_net
        run.status = 'COMPLETED'
        run.save()

        return Response({"detail": f"Calculated payroll for {records_created} employees."}, status=status.HTTP_200_OK)