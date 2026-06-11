from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from core.models import SalaryStructure
from departments.models import Department
from .serializers import SalaryStructureSerializer

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