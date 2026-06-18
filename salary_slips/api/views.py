# salary_slips/api/views.py
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

from payroll.models import PayrollRecord, PayrollRun
from salary_slips.models import SalarySlip
from employees.models import EmployeeProfile

# Required: pip install reportlab
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER

class GenerateSalarySlipView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_code, year, month):
        # 1. Locate record (Assuming PayrollRecord exists for this run)
        # We find the run for the specific month/year/dept
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

        if request.query_params.get('download') == 'true':
            return self.generate_pdf(slip)

        return Response({"detail": "Salary slip ready", "slip_number": slip.slip_number}, status=status.HTTP_200_OK)

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
            ['ESIC No.', ':', 'NA'], # Example mapping
            ['Work Place', ':', slip.department_snapshot],
            ['Designation', ':', slip.designation_snapshot],
            ['Date', ':', date.today().strftime("%d.%m.%Y")],
        ]
        elements.append(Table(info_data, colWidths=[100, 20, 300]))
        elements.append(Spacer(1, 20))

        # Wage Slip Table
        data = [
            ['Days', '', 'Allowance', 'Rate', 'Gross', 'Deduction', '', 'Net Pay'],
            ['Prs. Days', slip.days_present, 'Basic', '', slip.monthly_honorarium, 'P. Fund (12%)', slip.epf_amount, ''],
            ['', '', '', '', '', 'ESIC (0.75%)', slip.esic_amount, ''],
            ['', '', '', '', '', 'TDS (10%)', slip.tds_amount, ''],
            ['Total Days', slip.total_working_days, 'Total Earnings', '', slip.gross_pay, 'Total Ded.', slip.total_deductions, slip.net_pay]
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
        elements.append(Paragraph("This is a system-generated salary slip and does not require signature.", styles['Normal']))

        doc.build(elements)
        buffer.seek(0)
        return HttpResponse(buffer, content_type='application/pdf')