# salary_slips/api/serializers.py
from rest_framework import serializers
from salary_slips.models import SalarySlip

class SalarySlipListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing Salary Slips with relevant tracking and employee data.
    """
    employee_code = serializers.CharField(source='employee_code_snapshot', read_only=True)
    employee_name = serializers.CharField(source='employee_name_snapshot', read_only=True)
    department_name = serializers.CharField(source='department_snapshot', read_only=True)
    generated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SalarySlip
        fields = [
            'id', 
            'slip_number', 
            'slip_month', 
            'slip_year',
            'employee_code', 
            'employee_name', 
            'department_name',
            'net_pay', 
            'status', 
            'generated_at', 
            'generated_by_name'
        ]

    def get_generated_by_name(self, obj):
        if obj.generated_by:
            return obj.generated_by.get_full_name() or obj.generated_by.username
        return "System"