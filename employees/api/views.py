# employees/api/views.py
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction

from employees.models import EmployeeProfile
from accounts.models import User
from .serializers import EmployeeProfileSerializer, EmployeeOneShotSerializer
from .filters import EmployeeProfileFilter

class EmployeePagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 100

# =====================================================
# STANDARD CRUD (List, Detail, Create, Update, Delete)
# =====================================================

class EmployeeProfileListView(generics.ListAPIView):
    """
    1) List API (Paginated to 15) with dynamic searching and extensive filtering.
    """
    serializer_class = EmployeeProfileSerializer
    pagination_class = EmployeePagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EmployeeProfileFilter
    
    search_fields = ['user__first_name', 'user__last_name', 'user__phone_number', 'user__employee_code', 'pincode', 'city', 'state']
    ordering_fields = ['date_of_joining', 'user__first_name', 'department__name']

    def get_queryset(self):
        return EmployeeProfile.objects.select_related(
            'user', 'department', 'designation'
        ).filter(is_active=True).order_by('-created_at')


class EmployeeProfileDetailView(generics.RetrieveAPIView):
    """
    1.1) Detail endpoint retrieving all info via unique employee_code.
    """
    serializer_class = EmployeeProfileSerializer
    lookup_field = 'user__employee_code'
    lookup_url_kwarg = 'emp_code'

    def get_queryset(self):
        return EmployeeProfile.objects.select_related(
            'user', 'department', 'designation'
        ).filter(is_active=True)


class EmployeeOneShotCreateView(generics.CreateAPIView):
    """
    2) One-Shot Create API. Handles both User and Employee profile.
    Automatically formats username, employee_code, and password. Role ID is forced to 3.
    """
    serializer_class = EmployeeOneShotSerializer
    parser_classes = [MultiPartParser, FormParser]


class EmployeeOneShotUpdateView(generics.UpdateAPIView):
    """
    3) One-Shot Update API (Single). Updates fields in both User and Employee models.
    """
    serializer_class = EmployeeOneShotSerializer
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = 'user__employee_code'
    lookup_url_kwarg = 'emp_code'

    def get_queryset(self):
        return EmployeeProfile.objects.select_related('user').filter(is_active=True)


class EmployeeOneShotDeleteView(generics.DestroyAPIView):
    """
    4) One-Shot Delete API (Single). Soft-deletes both the User and Employee Profile.
    """
    lookup_field = 'user__employee_code'
    lookup_url_kwarg = 'emp_code'

    def get_queryset(self):
        return EmployeeProfile.objects.filter(is_active=True)

    @transaction.atomic
    def perform_destroy(self, instance):
        request_user = self.request.user
        
        # Soft delete the linked User account
        user = instance.user
        user.delete(by_user=request_user)
        
        # Soft delete the Employee Profile
        instance.delete(by_user=request_user)


# =====================================================
# BULK OPERATIONS (Update, Delete)
# =====================================================

class EmployeeBulkUpdateView(APIView):
    """
    3.1) Bulk Update API. 
    Accepts JSON array: {"updates": [{"employee_code": "AB-IT-001", "first_name": "New"}, ...]}
    """
    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        updates = request.data.get('updates', [])
        if not isinstance(updates, list):
            return Response({"detail": "Expected a list of updates under 'updates' key."}, status=status.HTTP_400_BAD_REQUEST)

        updated_codes = []
        user_fields = ['first_name', 'last_name', 'email', 'phone_number', 'employee_type', 'reporting_manager']

        for item in updates:
            emp_code = item.get('employee_code')
            if not emp_code:
                continue

            try:
                emp_profile = EmployeeProfile.objects.select_related('user').get(user__employee_code=emp_code, is_active=True)
                
                # Update User
                user_updated = False
                for f in user_fields:
                    if f in item:
                        setattr(emp_profile.user, f, item[f])
                        user_updated = True
                
                if user_updated:
                    emp_profile.user.updated_by = request.user
                    emp_profile.user.save()

                # Update EmployeeProfile
                emp_updated = False
                for k, v in item.items():
                    if k not in user_fields and k != 'employee_code' and hasattr(emp_profile, k):
                        setattr(emp_profile, k, v)
                        emp_updated = True
                
                if emp_updated:
                    emp_profile.updated_by = request.user
                    emp_profile.save()

                updated_codes.append(emp_code)

            except EmployeeProfile.DoesNotExist:
                pass # Skip invalid codes

        return Response({"detail": f"Successfully updated {len(updated_codes)} employees.", "updated": updated_codes}, status=status.HTTP_200_OK)


class EmployeeBulkDeleteView(APIView):
    """
    4.1) Bulk Delete API.
    Accepts JSON array: {"employee_codes": ["AB-IT-001", "AB-HR-002"]}
    """
    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        codes = request.data.get('employee_codes', [])
        if not isinstance(codes, list) or not codes:
            return Response({"detail": "Provide a list of codes under 'employee_codes'."}, status=status.HTTP_400_BAD_REQUEST)

        employees = EmployeeProfile.objects.select_related('user').filter(user__employee_code__in=codes, is_active=True)
        count = employees.count()

        for emp in employees:
            emp.user.delete(by_user=request.user)
            emp.delete(by_user=request.user)

        return Response({"detail": f"Successfully soft-deleted {count} employees."}, status=status.HTTP_200_OK)