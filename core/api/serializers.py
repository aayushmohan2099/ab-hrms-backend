from rest_framework import serializers
from core.models import *

class SalaryStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryStructure
        fields = [
            'id', 'department', 'tds_rate', 'epf_rate', 'esic_rate', 
            'effective_from', 'effective_to', 'remarks', 'is_active'
        ]
        read_only_fields = [
            'department', 'is_active', 'th_urid', 'created_at', 
            'updated_at', 'deleted_at', 'created_by', 'updated_by', 'deleted_by'
        ]

class CustomSalaryStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomSalaryStructure
        fields = [
            'id', 'employee', 'tds_amount', 'epf_amount', 'esic_amount', 
            'effective_from', 'effective_to', 'remarks', 'is_active'
        ]
        read_only_fields = [
            'employee', 'is_active', 'th_urid', 'created_at', 
            'updated_at', 'deleted_at', 'created_by', 'updated_by', 'deleted_by'
        ]

class BulkCustomSalaryStructureSerializer(serializers.Serializer):
    employee_codes = serializers.ListField(
        child=serializers.CharField(max_length=50),
        allow_empty=False,
        help_text="List of employee codes to assign the custom structure."
    )
    tds_amount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    epf_amount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    esic_amount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)        

class DepartmentCustomSalaryStructureSerializer(serializers.ModelSerializer):
    """
    Serializer for listing all Custom Salary Structures in a department.
    Includes Employee Code, Name, and Designation for frontend grouping/display.
    """
    employee_code = serializers.CharField(source='employee.user.employee_code', read_only=True)
    employee_name = serializers.CharField(source='employee.user.get_full_name', read_only=True)
    designation_name = serializers.CharField(source='employee.designation.name', read_only=True)

    class Meta:
        model = CustomSalaryStructure
        fields = [
            'id', 'employee', 'employee_code', 'employee_name', 'designation_name',
            'tds_amount', 'epf_amount', 'esic_amount', 
            'effective_from', 'effective_to', 'remarks', 'is_active'
        ]

class BulkCustomSalaryStructureDeleteSerializer(serializers.Serializer):
    """
    Serializer to validate the incoming array of employee codes for bulk deletion.
    """
    employee_codes = serializers.ListField(
        child=serializers.CharField(max_length=50),
        allow_empty=False,
        help_text="List of employee codes whose custom structures should be deleted."
    )    