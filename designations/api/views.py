from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from designations.models import Designation
from departments.models import Department
from .serializers import DesignationSerializer

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class DesignationListView(generics.ListAPIView):
    """List designations belonging to a specific department."""
    serializer_class = DesignationSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        return Designation.objects.filter(department_id=dept_id, is_active=True).order_by('name')

class DesignationCreateView(generics.CreateAPIView):
    """Create a designation under a specific department."""
    serializer_class = DesignationSerializer

    def perform_create(self, serializer):
        dept_id = self.kwargs.get('dept_id')
        department = get_object_or_404(Department, id=dept_id, is_active=True)
        serializer.save(created_by=self.request.user, department=department)

class DesignationUpdateView(generics.UpdateAPIView):
    """Update a designation under a specific department."""
    serializer_class = DesignationSerializer
    lookup_field = 'id'

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        return Designation.objects.filter(department_id=dept_id, is_active=True)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

class DesignationDeleteView(generics.DestroyAPIView):
    """Soft delete a designation under a specific department."""
    lookup_field = 'id'

    def get_queryset(self):
        dept_id = self.kwargs.get('dept_id')
        return Designation.objects.filter(department_id=dept_id, is_active=True)

    def perform_destroy(self, instance):
        instance.delete(by_user=self.request.user)