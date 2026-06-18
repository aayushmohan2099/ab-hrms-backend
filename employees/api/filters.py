# employees/api/filters.py
import django_filters
from employees.models import EmployeeProfile

class EmployeeProfileFilter(django_filters.FilterSet):
    """
    Custom FilterSet for robust date ranging and exact matches on relationships.
    """
    department = django_filters.NumberFilter(field_name='department_id')
    designation = django_filters.NumberFilter(field_name='designation_id')
    gender = django_filters.CharFilter(field_name='gender', lookup_expr='iexact')

    doj_after = django_filters.DateFilter(field_name="date_of_joining", lookup_expr='gte')
    doj_before = django_filters.DateFilter(field_name="date_of_joining", lookup_expr='lte')
    
    dob_after = django_filters.DateFilter(field_name="date_of_birth", lookup_expr='gte')
    dob_before = django_filters.DateFilter(field_name="date_of_birth", lookup_expr='lte')
    
    dol_after = django_filters.DateFilter(field_name="date_of_leaving", lookup_expr='gte')
    dol_before = django_filters.DateFilter(field_name="date_of_leaving", lookup_expr='lte')

    class Meta:
        model = EmployeeProfile
        fields = [
            'department', 'designation', 'gender', 
            'date_of_joining', 'date_of_birth', 'date_of_leaving'
        ]