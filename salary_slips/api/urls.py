# salary_slips/api/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.SalarySlipListView.as_view(), name='salary-slip-list'),
    path('generate/<str:employee_code>/<int:year>/<int:month>/', 
         views.GenerateSalarySlipView.as_view(), name='generate-salary-slip'),
]