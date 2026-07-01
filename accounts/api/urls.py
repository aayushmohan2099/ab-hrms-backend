# /accounts/api/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # 1) List users (Paginated, Role-based)
    path('list/', views.UserListView.as_view(), name='user-list'),
    
    # 3) Create user (Multipart, Auto-generate code & password)
    path('create/', views.UserCreateView.as_view(), name='user-create'),
    
    # 2) Retrieve user details
    path('<int:id>/', views.UserDetailView.as_view(), name='user-detail'),
    
    # 6) Update user (PATCH mapping for partial updates)
    path('<int:id>/update/', views.UserUpdateView.as_view(), name='user-update'),
    path('<int:id>/change-password/', views.UserChangePasswordView.as_view(), name='user-change-password'),
    
    # 5) Delete user (Soft Delete)
    path('<int:id>/delete/', views.UserDeleteView.as_view(), name='user-delete'),
    
    # 4) Reset user password
    path('<int:id>/reset-password/', views.UserPasswordResetView.as_view(), name='user-password-reset'),
]