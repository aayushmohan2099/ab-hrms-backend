from rest_framework import serializers
from designations.models import Designation
from departments.models import Department

class DesignationSerializer(serializers.ModelSerializer):
    """
    Serializer for Designations. 
    Department is read-only because it is injected by the view via the URL parameter.
    """
    class Meta:
        model = Designation
        fields = [
            'id', 'name', 'code', 'department', 'description', 
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'department', 'is_active', 'th_urid', 'created_at', 
            'updated_at', 'deleted_at', 'created_by', 'updated_by', 'deleted_by'
        ]