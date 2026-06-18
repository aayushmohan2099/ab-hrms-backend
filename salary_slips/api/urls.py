# salary_slips/api/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('generate/<str:employee_code>/<int:year>/<int:month>/', 
         views.GenerateSalarySlipView.as_view(), name='generate-salary-slip'),
]