# employees/api/serializers.py
import random
from rest_framework import serializers
from django.db import transaction

from employees.models import EmployeeProfile
from accounts.models import User, Role
from departments.models import Department
from designations.models import Designation

class EmployeeProfileSerializer(serializers.ModelSerializer):
    """
    Read-focused serializer for listing and detailing Employee Profiles.
    Flattens related User, Department, and Designation fields.
    """
    employee_code = serializers.CharField(source='user.employee_code', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    employee_type = serializers.CharField(source='user.employee_type', read_only=True)
    is_user_active = serializers.BooleanField(source='user.is_active', read_only=True)
    profile_picture = serializers.ImageField(source='user.profile_picture', read_only=True)

    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    designation_name = serializers.CharField(source='designation.name', read_only=True)
    designation_code = serializers.CharField(source='designation.code', read_only=True)

    class Meta:
        model = EmployeeProfile
        fields = [
            'id', 'employee_code', 'first_name', 'last_name', 'email', 
            'phone_number', 'employee_type', 'profile_picture', 'is_user_active',
            
            'department', 'department_name', 'department_code',
            'designation', 'designation_name', 'designation_code',

            'date_of_joining', 'date_of_birth', 'date_of_leaving', 'gender',
            'monthly_honorarium', 
            
            'bank_name', 'bank_account_number', 'bank_ifsc', 'bank_branch',
            'pan_number', 'uan_number', 'esic_ip_number', 'aadhaar_number',
            
            'address', 'city', 'state', 'pincode',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation',
            'job_seeker_id', 'theme',
            
            'is_active', 'created_at', 'updated_at'
        ]


class EmployeeOneShotSerializer(serializers.ModelSerializer):
    """
    Write-focused serializer handling simultaneous User & EmployeeProfile operations.
    """
    # User-specific fields MUST be write_only=True to prevent DRF from looking for them on EmployeeProfile during read phase
    first_name = serializers.CharField(max_length=150, write_only=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, write_only=True)
    email = serializers.EmailField(write_only=True)
    phone_number = serializers.CharField(max_length=15, required=False, allow_blank=True, write_only=True)
    employee_type = serializers.ChoiceField(choices=User.EMPLOYEE_TYPES, default="PERMANENT", write_only=True)
    reporting_manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True), required=False, allow_null=True, write_only=True
    )
    profile_picture = serializers.ImageField(required=False, allow_null=True, write_only=True)

    # Read-only outputs
    generated_password = serializers.SerializerMethodField(read_only=True)
    employee_code = serializers.CharField(source='user.employee_code', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = EmployeeProfile
        fields = [
            # Auto-generated responses
            'employee_code', 'username', 'generated_password',
            
            # User proxy inputs (now correctly write_only)
            'first_name', 'last_name', 'email', 'phone_number', 'employee_type', 
            'reporting_manager', 'profile_picture',

            # EmployeeProfile native inputs
            'department', 'designation', 'date_of_joining', 'date_of_birth', 
            'date_of_leaving', 'gender', 'monthly_honorarium', 
            'bank_name', 'bank_account_number', 'bank_ifsc', 'bank_branch',
            'pan_number', 'uan_number', 'esic_ip_number', 'aadhaar_number',
            'address', 'city', 'state', 'pincode',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation',
            'job_seeker_id', 'theme'
        ]

    def get_generated_password(self, obj):
        return getattr(obj, '_plain_password', None)

    def to_representation(self, instance):
        """
        Manually inject the User proxy fields back into the response data 
        since they were marked as write_only.
        """
        ret = super().to_representation(instance)
        ret['first_name'] = instance.user.first_name
        ret['last_name'] = instance.user.last_name
        ret['email'] = instance.user.email
        ret['phone_number'] = instance.user.phone_number
        ret['employee_type'] = instance.user.employee_type
        ret['reporting_manager'] = instance.user.reporting_manager_id
        
        request = self.context.get('request')
        if instance.user.profile_picture:
            if request:
                ret['profile_picture'] = request.build_absolute_uri(instance.user.profile_picture.url)
            else:
                ret['profile_picture'] = instance.user.profile_picture.url
        else:
            ret['profile_picture'] = None

        return ret

    @transaction.atomic
    def create(self, validated_data):
        # Extract User specific data
        user_data = {
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'email': validated_data.pop('email'),
            'phone_number': validated_data.pop('phone_number', ''),
            'employee_type': validated_data.pop('employee_type', 'PERMANENT'),
            # We don't pop reporting_manager here; we will override it based on the department
            'profile_picture': validated_data.pop('profile_picture', None)
        }
        
        department = validated_data.get('department')

        # 1. Generate unique employee code: AB-<Department.code>-<increment>
        prefix = f"AB-{department.code}-"
        last_user = User.objects.filter(employee_code__startswith=prefix).order_by('-employee_code').first()
        
        if last_user and last_user.employee_code:
            try:
                last_num = int(last_user.employee_code.split('-')[-1])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
            
        employee_code = f"{prefix}{new_num:03d}"
        
        # 2. Assign default Role ID 3
        try:
            role = Role.objects.get(id=3)
        except Role.DoesNotExist:
            raise serializers.ValidationError({"role": "Role ID 3 does not exist in the database. Please initialize roles."})

        # 3. Auto-assign Reporting Manager based on Department Head
        # If the department has a head, use their User ID. Otherwise, leave as None.
        reporting_manager = department.head if department.head else None

        # 4. Create User Account
        username = employee_code
        random_digits = f"{random.randint(100, 999)}"
        raw_password = f"{username}@{random_digits}"

        user = User.objects.create_user(
            username=username,
            email=user_data['email'],
            password=raw_password,
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            phone_number=user_data['phone_number'],
            employee_type=user_data['employee_type'],
            reporting_manager=reporting_manager,  # Assigned here
            profile_picture=user_data['profile_picture'],
            employee_code=employee_code,
            role=role,
            created_by=self.context['request'].user
        )

        # 5. Create Employee Profile
        employee_profile = EmployeeProfile.objects.create(
            user=user,
            created_by=self.context['request'].user,
            **validated_data
        )
        
        # Attach password for the response
        employee_profile._plain_password = raw_password

        return employee_profile

    @transaction.atomic
    def update(self, instance, validated_data):
        user = instance.user
        
        # Pop user fields and update User model if provided
        user_fields = ['first_name', 'last_name', 'email', 'phone_number', 'employee_type', 'reporting_manager', 'profile_picture']
        
        user_updated = False
        for field in user_fields:
            if field in validated_data:
                setattr(user, field, validated_data.pop(field))
                user_updated = True
        
        if user_updated:
            user.updated_by = self.context['request'].user
            user.save()

        # Update remaining EmployeeProfile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        instance.updated_by = self.context['request'].user
        instance.save()
        
        return instance