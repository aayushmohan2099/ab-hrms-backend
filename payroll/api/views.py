from datetime import date
import calendar
from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from core.models import *
from employees.models import EmployeeProfile
from attendance.models import DailyAttendance
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from payroll.models import *
from departments.models import Department
from .serializers import *

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
    Uses strict Calendar Year logic (Jan-Dec).
    - ABSENT, unmarked days, and Leave Without Pay (LWP) are immediate Loss of Pay.
    - EL, SL, CL, ESL draw from their respective Calendar Year / Half-Year allowances.
    - Any leave taken beyond the strict allowance is converted to LOP.
    - Statutory Deductions (EPF, ESIC, TDS) are calculated on the Base Honorarium.
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

        # Determine Calendar Year boundaries (Jan 1 to Dec 31)
        cy_start_date = date(year, 1, 1)
        h1_start = date(year, 1, 1)
        h2_start = date(year, 7, 1)

        # Determine end of previous month for historical YTD count
        if month == 1:
            last_month_end = None # No history in this calendar year yet
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
            
            # Safe __in queries to handle both model enum formats (CASUAL vs CASUAL_LEAVE)
            cl_days = att_records.filter(status__in=['CASUAL', 'CASUAL_LEAVE']).count()
            sl_days = att_records.filter(status__in=['SICK', 'SICK_LEAVE']).count()
            el_days = att_records.filter(status__in=['EARNED', 'EARNED_LEAVE', 'PAID_LEAVE']).count()
            esl_days = att_records.filter(status__in=['ESL', 'EXTRAORDINARY_SICK_LEAVE']).count()
            lwp_days = att_records.filter(status__in=['LWP', 'LEAVE_WITHOUT_PAY']).count()
            absent_db = att_records.filter(status='ABSENT').count()
            
            remaining_days = 0
            if today.year == year and today.month == month and today.day < total_days_in_month:
                remaining_days = total_days_in_month - today.day
            
            explicit_days = prs_days + weekends + holidays + cl_days + sl_days + el_days + esl_days + lwp_days + absent_db + remaining_days
            unmarked_past_days = max(0, total_days_in_month - explicit_days)
            
            # Base Loss of Pay (Absences without approval + LWP)
            base_lop_days = absent_db + unmarked_past_days + lwp_days

            # 2. Historical Leave Usage (Calendar Year bounds up to end of previous month)
            hist_cl = 0
            hist_el = 0
            hist_sl = 0
            hist_esl = 0

            if last_month_end:
                hist_qs = DailyAttendance.objects.filter(
                    employee=emp,
                    date__lte=last_month_end,
                    is_active=True
                )
                
                # EL, SL, ESL evaluate against the entire Calendar Year YTD
                hist_el = hist_qs.filter(date__gte=cy_start_date, status__in=['EARNED', 'EARNED_LEAVE', 'PAID_LEAVE']).count()
                hist_sl = hist_qs.filter(date__gte=cy_start_date, status__in=['SICK', 'SICK_LEAVE']).count()
                hist_esl = hist_qs.filter(date__gte=cy_start_date, status__in=['ESL', 'EXTRAORDINARY_SICK_LEAVE']).count()
                
                # CL strictly evaluates against its isolated 6-month window (H1 or H2)
                if month <= 6:
                    hist_cl = hist_qs.filter(date__gte=h1_start, status__in=['CASUAL', 'CASUAL_LEAVE']).count()
                else:
                    hist_cl = hist_qs.filter(date__gte=h2_start, status__in=['CASUAL', 'CASUAL_LEAVE']).count()

            # 3. Leave Rule Validation & Pro-ration Logic
            
            # CL Rule: Max 5 days every 6 months. No carry forward to H2 or next year.
            cl_remaining = max(0, 5 - hist_cl)
            excess_cl = max(0, cl_days - cl_remaining)
            
            # EL Rule: Max 5 days H1, 10 days YTD. Carries forward internally to H2.
            el_annual_limit = 5 if month <= 6 else 10
            el_remaining = max(0, el_annual_limit - hist_el)
            excess_el = max(0, el_days - el_remaining)
            
            # SL Rule: Max 10 days per Calendar Year.
            sl_remaining = max(0, 10 - hist_sl)
            excess_sl = max(0, sl_days - sl_remaining)
            
            # ESL Rule: Max 60 days per Calendar Year.
            esl_remaining = max(0, 60 - hist_esl)
            excess_esl = max(0, esl_days - esl_remaining)
            
            # Sum up all deductible days (Base LOP + Extrapolated excesses)
            total_deductible_days = base_lop_days + excess_cl + excess_el + excess_sl + excess_esl
            effective_days = max(0, total_days_in_month - total_deductible_days)

            base_gross = float(emp.monthly_honorarium or 0)
            per_day_pay = base_gross / total_days_in_month if total_days_in_month else 0
            
            # Calculate Loss of Pay (LOP) financial amount
            lop_amount = round(total_deductible_days * per_day_pay, 2)

            # Gross pay is Base Honorarium minus LOP
            pro_rated_gross = max(0.0, round(base_gross - lop_amount, 2))

            # 4. Calculate Statutory Deductions
            
            # Get the first day of the payroll month
            payroll_month_start = date(year, month, 1)
            
            # Look for an active custom structure valid for this payroll month
            custom_structure = CustomSalaryStructure.objects.filter(
                employee=emp,
                is_active=True,
                effective_from__lte=payroll_month_start
            ).filter(
                models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=payroll_month_start)
            ).order_by('-effective_from').first()

            # First, calculate the standard amounts based on Designation rules & Dept rates
            epf_rate = float(structure.epf_rate) if rule and rule.applies_epf else 0
            esic_rate = float(structure.esic_rate) if rule and rule.applies_esic else 0
            tds_rate = float(structure.tds_rate) if rule and rule.applies_tds else 0

            epf_amt = round(pro_rated_gross * (epf_rate / 100), 2)
            esic_amt = round(pro_rated_gross * (esic_rate / 100), 2)
            tds_amt = round(pro_rated_gross * (tds_rate / 100), 2)

            # Override standard amounts ONLY IF the custom structure explicitly defines a non-zero value
            # (Assuming a defined custom amount > 0 implies an override. If 0 is a valid override, 
            # you might need to check for None, but Django DecimalFields default to 0.00).
            if custom_structure:
                if custom_structure.epf_amount > 0:
                    epf_amt = float(custom_structure.epf_amount)
                if custom_structure.esic_amount > 0:
                    esic_amt = float(custom_structure.esic_amount)
                if custom_structure.tds_amount > 0:
                    tds_amt = float(custom_structure.tds_amount)
            
            emp_total_ded = epf_amt + esic_amt + tds_amt
            
            # Net Pay = Pro-rated Gross - Statutory Deductions
            net_pay = round(pro_rated_gross - emp_total_ded, 2)
            net_pay = max(0.0, net_pay) # Prevent negative salary

            # 5. Save/Overwrite Payroll Record for Employee
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

        # Update Master Run Totals
        run.total_gross = total_gross
        run.total_deductions = total_deductions
        run.total_net = total_net
        run.status = 'COMPLETED'
        run.save()

        return Response({"detail": f"Calculated payroll for {records_created} employees."}, status=status.HTTP_200_OK)