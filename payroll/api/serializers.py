from rest_framework import serializers
from payroll.models import DesignationPayrollRule, PayrollRun, PayrollRecord

class DesignationPayrollRuleSerializer(serializers.ModelSerializer):
    designation_name = serializers.CharField(source='designation.name', read_only=True)
    department_id = serializers.IntegerField(source='designation.department_id', read_only=True)

    class Meta:
        model = DesignationPayrollRule
        fields = [
            'id', 'designation', 'designation_name', 'department_id', 
            'applies_tds', 'applies_epf', 'applies_esic', 'remarks', 'is_active'
        ]
        read_only_fields = [
            'is_active', 'th_urid', 'created_at', 'updated_at', 
            'deleted_at', 'created_by', 'updated_by', 'deleted_by'
        ]

class PayrollRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollRun
        fields = [
            'id', 'department', 'pay_month', 'pay_year', 'salary_structure', 
            'status', 'total_gross', 'total_deductions', 'total_net', 
            'processed_at', 'approved_by', 'approved_at', 'remarks', 'is_active'
        ]
        read_only_fields = [
            'department', 'total_gross', 'total_deductions', 'total_net', 
            'processed_at', 'approved_by', 'approved_at', 'is_active', 
            'th_urid', 'created_at', 'updated_at', 'deleted_at', 
            'created_by', 'updated_by', 'deleted_by'
        ]

class PayrollRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.user.get_full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.user.employee_code', read_only=True)

    class Meta:
        model = PayrollRecord
        fields = [
            'id', 'payroll_run', 'employee', 'employee_name', 'employee_code', 
            'attendance_record', 'designation_snapshot', 'total_working_days', 
            'days_present', 'days_absent', 'monthly_honorarium', 'gross_pay', 
            'tds_amount', 'epf_amount', 'esic_amount', 'other_deductions', 
            'total_deductions', 'net_pay', 'status', 'remarks', 'is_active'
        ]
        read_only_fields = [
            'payroll_run', 'is_active', 'th_urid', 'created_at', 'updated_at', 
            'deleted_at', 'created_by', 'updated_by', 'deleted_by'
        ]