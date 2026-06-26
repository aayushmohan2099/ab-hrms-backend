import os
import zipfile
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import serializers, viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from django.http import FileResponse, Http404
from django_filters.rest_framework import DjangoFilterBackend

from accounts.models import User
from employees.models import TDSForm

# ---------------------------------------------------------
# Serializers
# ---------------------------------------------------------
class TDSFormSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    employee_name = serializers.CharField(source="employee.get_full_name", read_only=True)
    
    # Write-only field allowing Admin to upload by typing the employee_code manually
    upload_employee_code = serializers.CharField(write_only=True, required=False)
    
    # Clean download link for the frontend
    download_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TDSForm
        fields = [
            "th_urid", "employee_code", "employee_name", "upload_employee_code", 
            "financial_year", "quarter", "form_pdf", "download_url", "created_at"
        ]
        read_only_fields = ["th_urid", "created_at"]

    def get_download_url(self, obj):
        request = self.context.get("request")
        if obj.form_pdf and request:
            return request.build_absolute_uri(f"/api/v1/tds-forms/{obj.th_urid}/download/")
        return None

    def validate_upload_employee_code(self, value):
        if value:
            try:
                user = User.objects.get(employee_code=value, is_active=True)
                return user
            except User.DoesNotExist:
                raise serializers.ValidationError("Active employee with this code does not exist.")
        return value

    def create(self, validated_data):
        user = validated_data.pop('upload_employee_code', None)
        if user:
            validated_data['employee'] = user
        
        # Explicit validation for unique_together before hitting DB integrity error
        if TDSForm.objects.filter(
            employee=validated_data.get('employee'), 
            financial_year=validated_data.get('financial_year'), 
            quarter=validated_data.get('quarter'), 
            is_active=True
        ).exists():
            raise serializers.ValidationError(
                "A TDS Form for this Quarter and Financial Year already exists for this employee."
            )
            
        return super().create(validated_data)


# ---------------------------------------------------------
# Permissions
# ---------------------------------------------------------
class IsAdminOrOwnerReadOnly(BasePermission):
    """
    Custom permission:
    - Admins (is_staff) have full CRUD access.
    - Employees have Read-Only access (SAFE_METHODS).
    - Object-level: Employees can only access objects they own.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        # SAFE_METHODS are GET, HEAD, OPTIONS
        if request.method in SAFE_METHODS:
            return True
        # For POST, PUT, PATCH, DELETE, must be admin
        return request.user.is_staff or request.user.is_superuser

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        return request.method in SAFE_METHODS and obj.employee == request.user


# ---------------------------------------------------------
# Views
# ---------------------------------------------------------
class TDSFormViewSet(viewsets.ModelViewSet):
    """
    API for Quarterly TDS Forms.
    Admins: Upload (Single/Bulk), View All, Delete.
    Employees: View Own, Download Own.
    """
    serializer_class = TDSFormSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOwnerReadOnly]
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = "th_urid"
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['financial_year', 'quarter']
    search_fields = ['employee__employee_code', 'employee__first_name', 'employee__last_name']
    ordering_fields = ['created_at', 'financial_year', 'quarter']

    def get_queryset(self):
        user = self.request.user
        queryset = TDSForm.objects.select_related('employee').filter(is_active=True)
        
        # Admins see everything
        if user.is_staff or user.is_superuser:
            return queryset
            
        # Regular employees ONLY see their own records
        return queryset.filter(employee=user)

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        instance.delete(by_user=self.request.user)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, th_urid=None):
        tds_form = self.get_object() 
        
        if not tds_form.form_pdf:
            raise Http404("PDF file not found on the server.")
        
        filename = f"TDS_{tds_form.employee.employee_code}_{tds_form.financial_year}_{tds_form.quarter}.pdf"
        
        return FileResponse(
            tds_form.form_pdf.open("rb"),
            as_attachment=True,
            filename=filename
        )

    @action(detail=False, methods=["post"], url_path="bulk-upload-zip", parser_classes=[MultiPartParser, FormParser])
    def bulk_upload_zip(self, request):
        """
        Accepts a ZIP file containing PDFs. The filename (without .pdf) must match the employee_code.
        Requires: zip_file, financial_year, quarter.
        """
        zip_file = request.FILES.get('zip_file')
        financial_year = request.data.get('financial_year')
        quarter = request.data.get('quarter')

        if not zip_file or not financial_year or not quarter:
            return Response(
                {"error": "Fields 'zip_file', 'financial_year', and 'quarter' are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        if not zip_file.name.lower().endswith('.zip'):
            return Response(
                {"error": "The uploaded file must be a .zip archive."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        valid_quarters = dict(TDSForm.QUARTER_CHOICES).keys()
        if quarter not in valid_quarters:
            return Response(
                {"error": f"Invalid quarter. Choices are: {', '.join(valid_quarters)}."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        success_count = 0
        errors = []

        try:
            with zipfile.ZipFile(zip_file, 'r') as archive:
                for item in archive.infolist():
                    # Skip directories and macOS hidden index files
                    if item.is_dir() or '__MACOSX' in item.filename or os.path.basename(item.filename).startswith('._'):
                        continue

                    filename = os.path.basename(item.filename)
                    if not filename.lower().endswith('.pdf'):
                        continue

                    # Extract employee_code from filename
                    emp_code = os.path.splitext(filename)[0].strip()

                    try:
                        user = User.objects.get(employee_code=emp_code, is_active=True)
                    except User.DoesNotExist:
                        errors.append(f"[{filename}] Error: Active employee with code '{emp_code}' not found.")
                        continue

                    # Prevent duplicate uploads
                    if TDSForm.objects.filter(employee=user, financial_year=financial_year, quarter=quarter, is_active=True).exists():
                        errors.append(f"[{filename}] Error: TDS Form for {financial_year} {quarter} already exists for '{emp_code}'.")
                        continue

                    # Read PDF bytes from ZIP and wrap it in Django's SimpleUploadedFile
                    file_content = archive.read(item.filename)
                    pdf_file = SimpleUploadedFile(
                        name=filename, 
                        content=file_content, 
                        content_type='application/pdf'
                    )

                    # Save to Database
                    TDSForm.objects.create(
                        employee=user,
                        financial_year=financial_year,
                        quarter=quarter,
                        form_pdf=pdf_file,
                        created_by=request.user,
                        updated_by=request.user
                    )
                    success_count += 1

        except zipfile.BadZipFile:
            return Response(
                {"error": "The uploaded file is corrupt or not a valid ZIP archive."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"An unexpected error occurred during extraction: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        response_status = status.HTTP_201_CREATED if success_count > 0 else status.HTTP_400_BAD_REQUEST
        return Response({
            "message": f"Processed bulk upload. {success_count} forms successfully created.",
            "success_count": success_count,
            "errors": errors
        }, status=response_status)