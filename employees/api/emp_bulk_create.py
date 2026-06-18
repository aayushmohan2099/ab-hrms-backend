# employees/api/emp_bulk_create.py
import csv
import json
import openpyxl
import datetime
from django.db import transaction
from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated

from .serializers import EmployeeOneShotSerializer 

class BulkEmployeeCreateStreamView(APIView):
    """
    Accepts a CSV or Excel file, processes each row to create an employee,
    and streams the progress and generated credentials back to the client.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        
        if not file_obj:
            return self._error_response("No file provided in the request.")

        filename = file_obj.name.lower()
        rows = []

        # 1. Parse the uploaded file into a list of dictionaries
        try:
            if filename.endswith('.csv'):
                decoded_file = file_obj.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                for row in reader:
                    rows.append(row)
            elif filename.endswith('.xlsx'):
                wb = openpyxl.load_workbook(file_obj, data_only=True)
                sheet = wb.active
                headers = [str(cell.value).strip() for cell in sheet[1] if cell.value]
                for row in sheet.iter_rows(min_row=2, values_only=True):
                    if any(row):  # Skip entirely empty rows
                        row_dict = dict(zip(headers, row))
                        rows.append(row_dict)
            else:
                return self._error_response("Unsupported file format. Please upload .csv or .xlsx")
        except Exception as e:
            return self._error_response(f"Error reading file: {str(e)}")

        # 2. Define the generator function for the streaming response
        def event_stream():
            # Send initial state with total count
            yield json.dumps({"status": "start", "total": len(rows)}) + "\n"

            for index, row_data in enumerate(rows):
                cleaned_data = {}
                for k, v in row_data.items():
                    if k:
                        if v is None:
                            continue
                            
                        # FIX: Handle Excel datetime objects
                        if isinstance(v, (datetime.datetime, datetime.date)):
                            val = v.strftime('%Y-%m-%d')
                        else:
                            val = str(v).strip()
                            
                            # FIX: Handle CSV string dates like DD-MM-YYYY or DD/MM/YYYY
                            if val and k in ['date_of_joining', 'date_of_birth', 'date_of_leaving']:
                                sep = '/' if '/' in val else '-'
                                if sep in val:
                                    parts = val.split(sep)
                                    # If the format looks like DD-MM-YYYY (parts[2] is year, parts[0] is day)
                                    if len(parts) == 3 and len(parts[2]) == 4 and len(parts[0]) <= 2:
                                        val = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"

                        if val != "":
                            cleaned_data[k] = val

                # Map foreign key ID columns from standard template to serializer expectations
                serializer_data = cleaned_data.copy()
                if 'department_id' in serializer_data:
                    serializer_data['department'] = serializer_data.pop('department_id')
                if 'designation_id' in serializer_data:
                    serializer_data['designation'] = serializer_data.pop('designation_id')

                # Execute individual atomic transaction per row
                try:
                    with transaction.atomic():
                        serializer = EmployeeOneShotSerializer(
                            data=serializer_data, 
                            context={'request': request}
                        )
                        
                        if serializer.is_valid():
                            employee = serializer.save()
                            yield json.dumps({
                                "status": "progress",
                                "row_index": index,
                                "success": True,
                                "username": employee.user.username,
                                "password": employee._plain_password,
                                "row_data": row_data
                            }) + "\n"
                        else:
                            # Rollback triggered automatically by exiting atomic block on error
                            yield json.dumps({
                                "status": "progress",
                                "row_index": index,
                                "success": False,
                                "error": str(serializer.errors),
                                "row_data": row_data
                            }) + "\n"
                except Exception as e:
                    yield json.dumps({
                        "status": "progress",
                        "row_index": index,
                        "success": False,
                        "error": str(e),
                        "row_data": row_data
                    }) + "\n"

            # Signal completion
            yield json.dumps({"status": "complete"}) + "\n"

        # Return streaming response using NDJSON (Newline Delimited JSON)
        return StreamingHttpResponse(event_stream(), content_type='application/x-ndjson')

    def _error_response(self, message):
        return StreamingHttpResponse(
            iter([json.dumps({"error": message}) + "\n"]), 
            content_type='application/x-ndjson'
        )