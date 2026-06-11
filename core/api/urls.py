from django.urls import path
from . import views

urlpatterns = [
    path('<int:dept_id>/salary-structures/list/', views.SalaryStructureListView.as_view()),
    path('<int:dept_id>/salary-structures/create/', views.SalaryStructureCreateView.as_view()),
    path('<int:dept_id>/salary-structures/<int:id>/update/', views.SalaryStructureUpdateView.as_view()),
    path('<int:dept_id>/salary-structures/<int:id>/delete/', views.SalaryStructureDeleteView.as_view()),
]