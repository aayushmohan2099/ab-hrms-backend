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