# employees/api/urls.py
from django.urls import path
from . import views
from .emp_bulk_create import *

urlpatterns = [
    # Listing 
    path('list/', views.EmployeeProfileListView.as_view(), name='employee-list'),
    
    # Creation
    path('create/', views.EmployeeOneShotCreateView.as_view(), name='employee-create'),

    # Bulk Operations
    path('bulk-create/', BulkEmployeeCreateStreamView.as_view(), name='employee-bulk-create'),
    path('bulk-update/', views.EmployeeBulkUpdateView.as_view(), name='employee-bulk-update'),
    path('bulk-delete/', views.EmployeeBulkDeleteView.as_view(), name='employee-bulk-delete'),
    
    # Detail, Update, Delete (Scoped by unique employee_code)
    path('<str:emp_code>/', views.EmployeeProfileDetailView.as_view(), name='employee-detail'),
    path('<str:emp_code>/update/', views.EmployeeOneShotUpdateView.as_view(), name='employee-update'),
    path('<str:emp_code>/delete/', views.EmployeeOneShotDeleteView.as_view(), name='employee-delete'),
]