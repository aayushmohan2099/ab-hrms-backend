# accounts/api/views.py
import random
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.models import User
from .serializers import UserSerializer, UserCreateSerializer

# =====================================================
# PAGINATION
# =====================================================
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# =====================================================
# USER VIEWS
# =====================================================

class UserListView(generics.ListAPIView):
    """
    1) List all users. 
    Administrator: Sees all users.
    Manager: Sees only users reporting to them.
    Employee: Not authorized.
    """
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination

    def list(self, request, *args, **kwargs):
        role_name = request.user.role.name if request.user.role else ""
        
        if role_name == "Employee" or not role_name:
            return Response(
                {"detail": "You do not have permission to view the users list."}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        role_name = user.role.name if user.role else ""

        if role_name == "Administrator":
            queryset = User.objects.filter(
                is_active=True
            ).order_by("-created_at")

        elif role_name == "Manager":
            queryset = User.objects.filter(
                is_active=True,
                reporting_manager=user
            ).order_by("-created_at")

        else:
            return User.objects.none()

        # Employee Code Filter
        employee_code = self.request.query_params.get("employee_code")

        if employee_code:
            queryset = queryset.filter(
                employee_code__icontains=employee_code.strip()
            )

        return queryset


class UserDetailView(generics.RetrieveAPIView):
    """2) Retrieve complete details of a specific user."""
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer
    lookup_field = 'id'


class UserCreateView(generics.CreateAPIView):
    """3) Create a new user (Multipart Form Data)."""
    queryset = User.objects.all()
    serializer_class = UserCreateSerializer
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        # Attach the user creating the record for the SoftDeleteMixin
        serializer.save(created_by=self.request.user)


class UserUpdateView(generics.UpdateAPIView):
    """6) Update a user (accepts PATCH for partial updates)."""
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = 'id'

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class UserChangePasswordView(APIView):
    """Dedicated endpoint for a user to safely change their own password."""
    
    def post(self, request, id):
        user = get_object_or_404(User, id=id, is_active=True)
        
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not old_password or not new_password:
            return Response(
                {"detail": "Both old and new passwords are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate the old password
        if not user.check_password(old_password):
            return Response(
                {"detail": "Incorrect current password."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Apply new password
        user.set_password(new_password)
        user.last_password_changed_at = timezone.now()
        user.save(update_fields=['password', 'last_password_changed_at'])

        return Response(
            {"detail": "Password successfully updated."}, 
            status=status.HTTP_200_OK
        )


class UserDeleteView(generics.DestroyAPIView):
    """5) Soft delete a user."""
    queryset = User.objects.filter(is_active=True)
    lookup_field = 'id'

    def perform_destroy(self, instance):
        # Utilizes the custom delete() method from SoftDeleteMixin
        instance.delete(by_user=self.request.user)


class UserPasswordResetView(APIView):
    """4) Reset a user's password to an auto-generated format."""
    
    def post(self, request, id):
        user = get_object_or_404(User, id=id, is_active=True)
        
        # Generate new password
        random_digits = f"{random.randint(100, 999)}"
        new_password = f"{user.username}@{random_digits}"
        
        # Apply and save
        user.set_password(new_password)
        user.save(update_fields=['password'])
        
        return Response(
            {
                "detail": "Password successfully reset.",
                "user_id": user.id,
                "username": user.username,
                "new_password": new_password
            }, 
            status=status.HTTP_200_OK
        )