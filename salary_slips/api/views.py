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
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib import colors

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

def num2words(num):
    """Simple Indian numbering system word converter for net pay"""
    num = int(float(num)) # Ensure it handles floats by truncating to int
    if num == 0:
        return "Zero Rupees Only"
    
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    
    def convert_below_1000(n):
        if n == 0:
            return ""
        elif n < 20:
            return ones[n]
        elif n < 100:
            return tens[n // 10] + (" " + ones[n % 10] if n % 10 != 0 else "")
        else:
            return ones[n // 100] + " Hundred" + (" and " + convert_below_1000(n % 100) if n % 100 != 0 else "")

    words = ""
    if num >= 10000000:
        words += convert_below_1000(num // 10000000) + " Crore "
        num %= 10000000
    if num >= 100000:
        words += convert_below_1000(num // 100000) + " Lakh "
        num %= 100000
    if num >= 1000:
        words += convert_below_1000(num // 1000) + " Thousand "
        num %= 1000
    if num > 0:
        words += convert_below_1000(num)
        
    return words.strip() + " Rupees Only"

def format_inr(value):
    """Formats a float/Decimal to Indian Rupee string format.
       Uses 'Rs.' instead of the Rupee symbol (₹) to prevent 
       font encoding issues (black squares) in ReportLab PDFs.
    """
    if value is None:
        return "Rs. 0.00"
    try:
        val = float(value)
        # Format to 2 decimal places
        formatted = f"{val:.2f}"
        parts = formatted.split('.')
        integer_part = parts[0]
        decimal_part = parts[1]
        
        # Indian comma separation logic
        if len(integer_part) > 3:
            last_three = integer_part[-3:]
            remaining = integer_part[:-3]
            # Split remaining into chunks of 2
            chunks = [remaining[max(0, i-2):i] for i in range(len(remaining), 0, -2)]
            chunks.reverse()
            integer_part = ",".join(chunks) + "," + last_three
            
        return f"Rs. {integer_part}.{decimal_part}"
    except (ValueError, TypeError):
        return "Rs. 0.00"


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
            # Pass the employee object to generate_pdf to access live department description and theme
            return self.generate_pdf(slip, emp)

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
            "monthly_honorarium": format_inr(slip.monthly_honorarium),
            "gross_pay": format_inr(slip.gross_pay),
            "epf_amount": format_inr(slip.epf_amount),
            "esic_amount": format_inr(slip.esic_amount),
            "tds_amount": format_inr(slip.tds_amount),
            "total_deductions": format_inr(slip.total_deductions),
            "net_pay": format_inr(slip.net_pay),
            "net_pay_words": num2words(slip.net_pay),
            "department_description": emp.department.description if emp.department.description else "NA",
            "employee_theme": emp.theme if emp.theme else "NA"
        }

        return Response(slip_data, status=status.HTTP_200_OK)

    def generate_pdf(self, slip, emp):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()
        
        # Define some custom styles for a more beautiful slip
        title_style = ParagraphStyle(
            'Title', 
            parent=styles['Heading2'], 
            alignment=TA_CENTER, 
            fontSize=16, 
            spaceAfter=20,
            textColor=colors.HexColor("#1e3a8a") # Dark blue title
        )
        
        bold_style = ParagraphStyle('Bold', parent=styles['Normal'], fontName='Helvetica-Bold')
        right_align_style = ParagraphStyle('RightAlign', parent=styles['Normal'], alignment=TA_RIGHT)
        
        # ---------------------------------------------------------
        # HEADER IMAGE LOGIC
        # ---------------------------------------------------------
        # Calculate proportional height to perfectly fit A4 width
        # A4 width = 595.27 points. Left margin (30) + Right margin (30) = 60.
        # Max available width = 535 points.
        # Original Aspect Ratio: 278 (H) / 2318 (W) = ~0.1199
        img_max_width = 535
        img_calculated_height = img_max_width * (278 / 2318)
        
        header_image_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'header.png')
        
        # Check if file exists so the PDF doesn't break if the image is missing
        if os.path.exists(header_image_path):
            header_img = Image(header_image_path, width=img_max_width, height=img_calculated_height)
            elements.append(header_img)
            elements.append(Spacer(1, 20)) # Space between image and text
        # ---------------------------------------------------------

        elements.append(Paragraph(f"WAGE SLIP FOR THE MONTH OF {calendar.month_name[slip.slip_month].upper()} {slip.slip_year}", title_style))
        
        dept_desc = emp.department.description if emp.department.description else "NA"
        theme = emp.theme if emp.theme else "NA"

        # Information Section (More structured formatting)
        info_data = [
            [Paragraph('<b>Company Name</b>', styles['Normal']), ':', Paragraph('<b>A B ENTERPRISE</b>', styles['Normal']), 
             Paragraph('<b>Work Place</b>', styles['Normal']), ':', Paragraph(slip.department_snapshot, styles['Normal'])],
            
            [Paragraph('<b>Employee Name</b>', styles['Normal']), ':', Paragraph(slip.employee_name_snapshot, styles['Normal']),
             Paragraph('<b>Address</b>', styles['Normal']), ':', Paragraph(dept_desc, styles['Normal'])],
             
            [Paragraph('<b>Designation</b>', styles['Normal']), ':', Paragraph(slip.designation_snapshot, styles['Normal']),
             Paragraph('<b>Theme</b>', styles['Normal']), ':', Paragraph(theme, styles['Normal'])],
             
            [Paragraph('<b>UAN No.</b>', styles['Normal']), ':', Paragraph(slip.uan_snapshot or 'NA', styles['Normal']),
             Paragraph('<b>ESIC No.</b>', styles['Normal']), ':', Paragraph('NA', styles['Normal'])],
             
            [Paragraph('<b>Date Generated</b>', styles['Normal']), ':', Paragraph(date.today().strftime("%d.%m.%Y"), styles['Normal']),
             '', '', '']
        ]
        
        # Adjust column widths for the new 6-column layout
        table_info = Table(info_data, colWidths=[90, 10, 160, 80, 10, 180])
        table_info.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(table_info)
        elements.append(Spacer(1, 20))

        # Wage Slip Table
        data = [
            # Header Row
            [Paragraph('<b>Days</b>', styles['Normal']), 
             Paragraph('<b>Count</b>', right_align_style), 
             Paragraph('<b>Allowance</b>', styles['Normal']), 
             Paragraph('<b>Gross</b>', right_align_style), 
             Paragraph('<b>Deduction</b>', styles['Normal']), 
             Paragraph('<b>Amount</b>', right_align_style), 
             Paragraph('<b>Net Pay</b>', right_align_style)],
             
            # Row 1
            ['Present Days', str(slip.days_present), 'Basic', format_inr(slip.monthly_honorarium), 'P. Fund (12%)', format_inr(slip.epf_amount), ''],
            
            # Row 2
            ['', '', '', '', 'ESIC (0.75%)', format_inr(slip.esic_amount), ''],
            
            # Row 3
            ['', '', '', '', 'TDS (10%)', format_inr(slip.tds_amount), ''],
            
            # Totals Row
            [Paragraph('<b>Total Days</b>', styles['Normal']), 
             Paragraph(f'<b>{slip.total_working_days}</b>', right_align_style), 
             Paragraph('<b>Total Earnings</b>', styles['Normal']), 
             Paragraph(f'<b>{format_inr(slip.gross_pay)}</b>', right_align_style), 
             Paragraph('<b>Total Ded.</b>', styles['Normal']), 
             Paragraph(f'<b>{format_inr(slip.total_deductions)}</b>', right_align_style), 
             Paragraph(f'<b>{format_inr(slip.net_pay)}</b>', right_align_style)]
        ]
        
        table = Table(data, colWidths=[70, 42, 85, 80, 85, 80, 80]) 
        table.setStyle(TableStyle([
            # Table Borders
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            
            # Header Styling
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('TOPPADDING', (0,0), (-1,0), 10),
            
            # Alignment for all cells
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (1,1), (1,-1), 'RIGHT'), # Days count
            ('ALIGN', (3,1), (3,-1), 'RIGHT'), # Gross col
            ('ALIGN', (5,1), (5,-1), 'RIGHT'), # Ded amount col
            ('ALIGN', (6,1), (6,-1), 'RIGHT'), # Net Pay col
            
            # Spanning for empty cells in Net Pay column
            ('SPAN', (6,0), (6,3)),
            
            # Totals Row Styling
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#f8fafc")),
            ('TOPPADDING', (0,-1), (-1,-1), 8),
            ('BOTTOMPADDING', (0,-1), (-1,-1), 8),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 15))

        # Net Pay in Words (Styled nicely)
        words_style = ParagraphStyle(
            'WordsStyle', 
            parent=styles['Normal'], 
            backColor=colors.HexColor("#f0fdf4"), # Light green bg
            borderColor=colors.HexColor("#bbf7d0"),
            borderWidth=1,
            borderPadding=10,
            borderRadius=4
        )
        elements.append(Paragraph(f"<b>Net Pay in words:</b> {num2words(slip.net_pay)}", words_style))
        elements.append(Spacer(1, 30))
        
        # System-generated note
        note_style = ParagraphStyle(
            'NoteStyle',
            parent=styles['Italic'],
            fontSize=8,
            textColor=colors.gray,
            alignment=TA_CENTER
        )
        elements.append(Paragraph("This is a system-generated salary slip and does not require a signature.", note_style))

        doc.build(elements)
        buffer.seek(0)
        return HttpResponse(buffer, content_type='application/pdf')