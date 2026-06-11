from rest_framework import serializers
from core.models import SalaryStructure

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