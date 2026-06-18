from django.urls import path
from . import views

urlpatterns = [
    # Designation Rules
    path('<int:dept_id>/rules/list/', views.DesignationRuleListView.as_view()),
    path('<int:dept_id>/rules/create/', views.DesignationRuleCreateView.as_view()),
    path('<int:dept_id>/rules/<int:id>/update/', views.DesignationRuleUpdateView.as_view()),
    path('<int:dept_id>/rules/<int:id>/delete/', views.DesignationRuleDeleteView.as_view()),

    # Payroll Runs
    path('<int:dept_id>/runs/list/', views.PayrollRunListView.as_view()),
    path('<int:dept_id>/runs/create/', views.PayrollRunCreateView.as_view()),
    path('<int:dept_id>/runs/<int:id>/update/', views.PayrollRunUpdateView.as_view()),
    path('<int:dept_id>/runs/<int:id>/delete/', views.PayrollRunDeleteView.as_view()),

    # Payroll Calculation Engine
    path('<int:dept_id>/runs/<int:run_id>/generate/', views.GeneratePayrollRecordsView.as_view()),

    # Payroll Records (Nested under Runs)
    path('<int:dept_id>/runs/<int:run_id>/records/list/', views.PayrollRecordListView.as_view()),
    path('<int:dept_id>/runs/<int:run_id>/records/create/', views.PayrollRecordCreateView.as_view()),
    path('<int:dept_id>/runs/<int:run_id>/records/<int:id>/update/', views.PayrollRecordUpdateView.as_view()),
    path('<int:dept_id>/runs/<int:run_id>/records/<int:id>/delete/', views.PayrollRecordDeleteView.as_view()),
]