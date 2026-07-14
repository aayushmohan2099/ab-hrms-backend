from django.urls import path
from . import views

urlpatterns = [
    path('<int:dept_id>/salary-structures/list/', views.SalaryStructureListView.as_view()),
    path('<int:dept_id>/salary-structures/create/', views.SalaryStructureCreateView.as_view()),
    path('<int:dept_id>/salary-structures/<int:id>/update/', views.SalaryStructureUpdateView.as_view()),
    path('<int:dept_id>/salary-structures/<int:id>/delete/', views.SalaryStructureDeleteView.as_view()),
    path('<int:emp_id>/custom-salary-structures/list/', views.CustomSalaryStructureListView.as_view()),
    path('<int:emp_id>/custom-salary-structures/create/', views.CustomSalaryStructureCreateView.as_view()),
    path('<int:emp_id>/custom-salary-structures/<int:id>/update/', views.CustomSalaryStructureUpdateView.as_view()),
    path('<int:emp_id>/custom-salary-structures/<int:id>/delete/', views.CustomSalaryStructureDeleteView.as_view()),

    # --- Bulk Custom Salary Structures (Must be above <int:emp_id>) ---
    path('custom-salary-structures/bulk-create/', views.BulkCustomSalaryStructureCreateView.as_view()),
    path('custom-salary-structures/bulk-delete/', views.BulkCustomSalaryStructureDeleteView.as_view()),

    # --- Department-wide Custom Salary Structures ---
    path('<int:dept_id>/custom-salary-structures/all/', views.DepartmentCustomSalaryStructureListView.as_view()),
]