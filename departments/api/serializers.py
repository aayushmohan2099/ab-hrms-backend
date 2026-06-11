from rest_framework import serializers
from departments.models import Department

class DepartmentSerializer(serializers.ModelSerializer):
    """
    Serializer for retrieving, listing, creating, and updating departments.
    """
    # Read-only field to easily display the department head's name in the UI
    head_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Department
        fields = [
            'id', 'name', 'code', 'description', 'head', 'head_name', 
            'is_active', 'created_at', 'updated_at'
        ]
        # Prevent the user from manually injecting audit/system fields
        read_only_fields = [
            'is_active', 'th_urid', 'created_at', 'updated_at', 
            'deleted_at', 'created_by', 'updated_by', 'deleted_by'
        ]

    def get_head_name(self, obj):
        if obj.head:
            # Fallback to username if first/last names aren't populated
            full_name = f"{obj.head.first_name} {obj.head.last_name}".strip()
            return full_name if full_name else obj.head.username
        return None
    
    def validate_head(self, value):
        if not value:
            return value

        qs = Department.objects.filter(
            head=value,
            is_active=True
        )

        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                "This employee is already assigned as head of another department."
            )

        return value    