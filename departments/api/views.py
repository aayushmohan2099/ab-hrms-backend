from rest_framework import generics, permissions
from rest_framework.pagination import PageNumberPagination
from departments.models import Department
from .serializers import DepartmentSerializer

# =====================================================
# PAGINATION
# =====================================================
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# =====================================================
# DEPARTMENT VIEWS
# =====================================================

class DepartmentListView(generics.ListAPIView):
    """1) List all active departments (Paginated)."""
    queryset = Department.objects.filter(is_active=True).order_by('name')
    serializer_class = DepartmentSerializer
    pagination_class = StandardResultsSetPagination


class DepartmentDetailView(generics.RetrieveAPIView):
    """2) Retrieve details of a specific department."""
    queryset = Department.objects.filter(is_active=True)
    serializer_class = DepartmentSerializer
    lookup_field = 'id'


class DepartmentCreateView(generics.CreateAPIView):
    """3) Create a new department."""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer

    def perform_create(self, serializer):
        # Attach the currently logged-in user to the 'created_by' field
        serializer.save(created_by=self.request.user)


class DepartmentUpdateView(generics.UpdateAPIView):
    """6) Update a department (accepts PATCH for partial updates)."""
    queryset = Department.objects.filter(is_active=True)
    serializer_class = DepartmentSerializer
    lookup_field = 'id'

    def perform_update(self, serializer):
        # Attach the currently logged-in user to the 'updated_by' field
        serializer.save(updated_by=self.request.user)


class DepartmentDeleteView(generics.DestroyAPIView):
    """5) Soft delete a department."""
    queryset = Department.objects.filter(is_active=True)
    lookup_field = 'id'

    def perform_destroy(self, instance):
        # Utilizes the custom delete() method from SoftDeleteMixin
        instance.delete(by_user=self.request.user)