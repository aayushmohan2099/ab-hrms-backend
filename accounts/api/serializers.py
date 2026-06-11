# accounts/api/serializers.py
import random
from rest_framework import serializers
from accounts.models import User, Role
from departments.models import Department

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'code']

class UserSerializer(serializers.ModelSerializer):
    """Serializer for retrieving, listing, and updating user details."""
    role_detail = RoleSerializer(source='role', read_only=True)

    class Meta:
        model = User
        exclude = ['password', 'user_permissions', 'groups']
        read_only_fields = ['employee_code', 'th_urid', 'created_at', 'updated_at', 'deleted_at', 'created_by', 'updated_by', 'deleted_by']

class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer specifically for handling User Creation with auto-generation logic."""
    department_id = serializers.IntegerField(write_only=True)
    generated_password = serializers.SerializerMethodField(read_only=True)
    role_detail = RoleSerializer(source='role', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'phone_number', 'employee_type', 'role', 'reporting_manager', 
            'profile_picture', 'department_id', 'employee_code', 'generated_password', 'role_detail'
        ]
        read_only_fields = ['employee_code']
        extra_kwargs = {
            'reporting_manager': {'required': False, 'allow_null': True}
        }

    def get_generated_password(self, obj):
        # We attach this temporary attribute during the create() method
        return getattr(obj, '_plain_password', None)

    def create(self, validated_data):
        dept_id = validated_data.pop('department_id')
        
        try:
            dept = Department.objects.get(id=dept_id, is_active=True)
        except Department.DoesNotExist:
            raise serializers.ValidationError({"department_id": "Valid and active department ID is required."})

        # 1. Auto-generate employee_code: AB-<Department.code>-<auto_increment_numbers>
        prefix = f"AB-{dept.code}-"
        last_user = User.objects.filter(employee_code__startswith=prefix).order_by('-employee_code').first()
        
        if last_user and last_user.employee_code:
            try:
                # Extract the number from the last code (e.g., AB-IT-005 -> 5)
                last_num = int(last_user.employee_code.split('-')[-1])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
            
        validated_data['employee_code'] = f"{prefix}{new_num:03d}"

        # 2. Auto-generate password: <username>@<3 digit number>
        username = validated_data.get('username')
        random_digits = f"{random.randint(100, 999)}"
        raw_password = f"{username}@{random_digits}"

        # 3. Create user instance
        user = User(**validated_data)
        user.set_password(raw_password)
        user.save()

        # Attach the raw password temporarily so the response can display it
        user._plain_password = raw_password

        return user