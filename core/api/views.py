from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from core.models import *
from departments.models import Department
from employees.models import EmployeeProfile
from .serializers import *
from rest_framework import status
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class SalaryStructureListView(generics.ListAPIView):
    serializer_class = SalaryStructureSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        return SalaryStructure.objects.filter(department_id=dept_id, is_active=True).order_by('-effective_from')

class SalaryStructureCreateView(generics.CreateAPIView):
    serializer_class = SalaryStructureSerializer

    def perform_create(self, serializer):
        dept_id = self.kwargs.get('dept_id')
        department = get_object_or_404(Department, id=dept_id, is_active=True)
        serializer.save(created_by=self.request.user, department=department)

class SalaryStructureUpdateView(generics.UpdateAPIView):
    serializer_class = SalaryStructureSerializer
    lookup_field = 'id'

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        return SalaryStructure.objects.filter(department_id=dept_id, is_active=True)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

class SalaryStructureDeleteView(generics.DestroyAPIView):
    lookup_field = 'id'

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        return SalaryStructure.objects.filter(department_id=dept_id, is_active=True)

    def perform_destroy(self, instance):
        instance.delete(by_user=self.request.user)

class CustomSalaryStructureListView(generics.ListAPIView):
    serializer_class = CustomSalaryStructureSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        emp_id = self.kwargs.get('emp_id')
        return CustomSalaryStructure.objects.filter(employee_id=emp_id, is_active=True).order_by('-effective_from')

class CustomSalaryStructureCreateView(generics.CreateAPIView):
    serializer_class = CustomSalaryStructureSerializer

    def perform_create(self, serializer):
        emp_id = self.kwargs.get('emp_id')
        employee = get_object_or_404(EmployeeProfile, id=emp_id, is_active=True)
        serializer.save(created_by=self.request.user, employee=employee)

class CustomSalaryStructureUpdateView(generics.UpdateAPIView):
    serializer_class = CustomSalaryStructureSerializer
    lookup_field = 'id'

    def get_queryset(self):
        emp_id = self.kwargs.get('emp_id')
        return CustomSalaryStructure.objects.filter(employee_id=emp_id, is_active=True)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

class CustomSalaryStructureDeleteView(generics.DestroyAPIView):
    lookup_field = 'id'

    def get_queryset(self):
        emp_id = self.kwargs.get('emp_id')
        return CustomSalaryStructure.objects.filter(employee_id=emp_id, is_active=True)

    def perform_destroy(self, instance):
        instance.delete(by_user=self.request.user)

class BulkCustomSalaryStructureCreateView(APIView):
    """
    Bulk creates CustomSalaryStructure rows for an array of employee_codes.
    Wrapped in a single atomic transaction.
    """
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = BulkCustomSalaryStructureSerializer(data=request.data)
        
        if serializer.is_valid():
            data = serializer.validated_data
            emp_codes = data.pop('employee_codes')
            
            # 1. Fetch valid, active employees matching the codes
            employees = EmployeeProfile.objects.filter(
                user__employee_code__in=emp_codes, 
                is_active=True
            )
            
            # 2. Verify all requested employees were actually found
            found_codes = set(employees.values_list('user__employee_code', flat=True))
            missing_codes = set(emp_codes) - found_codes
            
            if missing_codes:
                return Response({
                    "detail": f"The following employee codes were not found or are inactive: {', '.join(missing_codes)}"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 3. Create the records atomically
            created_count = 0
            for emp in employees:
                CustomSalaryStructure.objects.create(
                    employee=emp,
                    tds_amount=data.get('tds_amount', 0),
                    epf_amount=data.get('epf_amount', 0),
                    esic_amount=data.get('esic_amount', 0),
                    effective_from=data['effective_from'],
                    effective_to=data.get('effective_to'),
                    remarks=data.get('remarks', ''),
                    created_by=request.user
                )
                created_count += 1
            
            return Response({
                "detail": f"Successfully assigned custom salary structure to {created_count} employees."
            }, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)        
    
class DepartmentCustomSalaryStructureListView(generics.ListAPIView):
    """
    Lists all active Custom Salary Structures for ALL employees within a specific department.
    Useful for visualizing custom structures grouped by Designation.
    """
    serializer_class = DepartmentCustomSalaryStructureSerializer
    pagination_class = StandardResultsSetPagination # Assuming this exists from your previous code

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        return CustomSalaryStructure.objects.select_related(
            'employee__user', 'employee__designation'
        ).filter(
            employee__department_id=dept_id,
            is_active=True
        ).order_by('employee__designation__name', 'employee__user__employee_code', '-effective_from')


class BulkCustomSalaryStructureDeleteView(APIView):
    """
    Bulk deletes (soft delete) active CustomSalaryStructure rows for an array of employee_codes.
    Wrapped in a single atomic transaction.
    """
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = BulkCustomSalaryStructureDeleteSerializer(data=request.data)
        
        if serializer.is_valid():
            emp_codes = serializer.validated_data['employee_codes']
            
            # Fetch active custom structures for the given employee codes
            structures = CustomSalaryStructure.objects.filter(
                employee__user__employee_code__in=emp_codes,
                is_active=True
            )
            
            if not structures.exists():
                return Response({
                    "detail": "No active custom salary structures found for the provided employee codes."
                }, status=status.HTTP_404_NOT_FOUND)

            deleted_count = 0
            for struct in structures:
                # Triggering the SoftDeleteMixin delete method
                struct.delete(by_user=request.user)
                deleted_count += 1
                
            return Response({
                "detail": f"Successfully deleted {deleted_count} custom salary structure records."
            }, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)    