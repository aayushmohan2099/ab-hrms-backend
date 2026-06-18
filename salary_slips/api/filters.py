# salary_slips/api/filters.py
from django_filters import rest_framework as filters
from salary_slips.models import SalarySlip

class SalarySlipFilter(filters.FilterSet):
    # Cross-relational filter to filter by the employee's actual department ID
    department_id = filters.NumberFilter(field_name='employee__department_id')
    
    class Meta:
        model = SalarySlip
        fields = ['department_id', 'slip_month', 'slip_year', 'status']