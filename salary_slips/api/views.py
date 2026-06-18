# salary_slips/api/views.py
import os
from django.conf import settings
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from salary_slips.models import SalarySlip
from .serializers import SalarySlipListSerializer
from .pagination import SalarySlipPagination
from .filters import SalarySlipFilter
import calendar
from datetime import date
from io import BytesIO
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from payroll.models import *
from salary_slips.models import *
from employees.models import *

# Required: pip install reportlab
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER

class SalarySlipListView(generics.ListAPIView):
    """
    API View to list Salary Slips.
    - Paginated to 15 items per page.
    - Filters available: department_id, slip_month, slip_year, status.
    - Displays employee details, generation time, and the user who generated it.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SalarySlipListSerializer
    pagination_class = SalarySlipPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = SalarySlipFilter

    def get_queryset(self):
        # Optimize queries using select_related for foreign keys
        return SalarySlip.objects.select_related(
            'employee', 
            'generated_by'
        ).all().order_by('-generated_at')

class GenerateSalarySlipView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_code, year, month):
        # 1. Locate record (Assuming PayrollRecord exists for this run)
        emp = get_object_or_404(EmployeeProfile, user__employee_code=employee_code, is_active=True)
        record = PayrollRecord.objects.filter(
            employee=emp, 
            payroll_run__pay_month=month, 
            payroll_run__pay_year=year
        ).first()

        if not record:
            return Response({"detail": "Payroll record not found for this month."}, status=status.HTTP_404_NOT_FOUND)

        # 2. Check if SalarySlip already exists (Snapshot)
        slip, created = SalarySlip.objects.get_or_create(
            payroll_record=record,
            defaults={
                'employee': emp,
                'slip_month': month,
                'slip_year': year,
                'employee_code_snapshot': emp.user.employee_code,
                'employee_name_snapshot': emp.user.get_full_name(),
                'designation_snapshot': record.designation_snapshot,
                'department_snapshot': emp.department.name,
                'bank_name_snapshot': emp.bank_name,
                'bank_account_snapshot': emp.bank_account_number,
                'bank_ifsc_snapshot': emp.bank_ifsc,
                'pan_snapshot': emp.pan_number,
                'uan_snapshot': emp.uan_number,
                'total_working_days': record.total_working_days,
                'days_present': record.days_present,
                'days_absent': record.days_absent,
                'monthly_honorarium': record.monthly_honorarium,
                'gross_pay': record.gross_pay,
                'tds_amount': record.tds_amount,
                'epf_amount': record.epf_amount,
                'esic_amount': record.esic_amount,
                'total_deductions': record.total_deductions,
                'net_pay': record.net_pay,
                'status': 'GENERATED',
                'generated_at': timezone.now(),
                'generated_by': request.user
            }
        )

        # 3. Handle PDF Download Request
        if request.query_params.get('download') == 'true':
            return self.generate_pdf(slip)

        # 4. Handle Frontend Display Request (Return full serialized data)
        slip_data = {
            "id": slip.id,
            "slip_number": slip.slip_number,
            "employee_name_snapshot": slip.employee_name_snapshot,
            "uan_snapshot": slip.uan_snapshot,
            "department_snapshot": slip.department_snapshot,
            "designation_snapshot": slip.designation_snapshot,
            "days_present": str(slip.days_present),
            "total_working_days": slip.total_working_days,
            "monthly_honorarium": str(slip.monthly_honorarium),
            "gross_pay": str(slip.gross_pay),
            "epf_amount": str(slip.epf_amount),
            "esic_amount": str(slip.esic_amount),
            "tds_amount": str(slip.tds_amount),
            "total_deductions": str(slip.total_deductions),
            "net_pay": str(slip.net_pay),
        }

        return Response(slip_data, status=status.HTTP_200_OK)

    def generate_pdf(self, slip):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Heading2'], alignment=TA_CENTER)

        elements.append(Paragraph(f"Wage Slip For the month of {calendar.month_name[slip.slip_month]}-{slip.slip_year}", title_style))
        
        info_data = [
            ['Company Name', ':', 'A B ENTERPRISE'],
            ['Employee Name', ':', slip.employee_name_snapshot],
            ['UAN No.', ':', slip.uan_snapshot or 'NA'],
            ['ESIC No.', ':', 'NA'], 
            ['Work Place', ':', slip.department_snapshot],
            ['Designation', ':', slip.designation_snapshot],
            ['Date', ':', date.today().strftime("%d.%m.%Y")],
        ]
        elements.append(Table(info_data, colWidths=[100, 20, 300]))
        elements.append(Spacer(1, 20))

        # Wage Slip Table
        data = [
            ['Days', '', 'Allowance', 'Rate', 'Gross', 'Deduction', '', 'Net Pay'],
            ['Prs. Days', str(slip.days_present), 'Basic', '', str(slip.monthly_honorarium), 'P. Fund (12%)', str(slip.epf_amount), ''],
            ['', '', '', '', '', 'ESIC (0.75%)', str(slip.esic_amount), ''],
            ['', '', '', '', '', 'TDS (10%)', str(slip.tds_amount), ''],
            ['Total Days', slip.total_working_days, 'Total Earnings', '', str(slip.gross_pay), 'Total Ded.', str(slip.total_deductions), str(slip.net_pay)]
        ]
        
        table = Table(data, colWidths=[80, 40, 80, 50, 60, 100, 60, 60])
        table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('SPAN', (0,0), (1,0)),
            ('SPAN', (5,0), (6,0)),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))
        
        # System-generated note
        elements.append(Paragraph("This is a system-generated salary slip and does not require signature.", styles['Normal']))

        # ---------------------------------------------------------
        # FOOTER IMAGE LOGIC
        # ---------------------------------------------------------
        # Calculate proportional height to perfectly fit A4 width
        # A4 width = 595.27 points. Left margin (30) + Right margin (30) = 60.
        # Max available width = 535 points.
        # Original Aspect Ratio: 219 (H) / 934 (W) = ~0.2344
        img_max_width = 535
        img_calculated_height = img_max_width * (219 / 934)
        
        # Path to your image (adjust folder structure if necessary)
        footer_image_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'footer.png')
        
        # Check if file exists so the PDF doesn't break if the image is missing
        if os.path.exists(footer_image_path):
            elements.append(Spacer(1, 20)) # Space between text and image
            footer_img = Image(footer_image_path, width=img_max_width, height=img_calculated_height)
            elements.append(footer_img)
        # ---------------------------------------------------------

        doc.build(elements)
        buffer.seek(0)
        return HttpResponse(buffer, content_type='application/pdf')