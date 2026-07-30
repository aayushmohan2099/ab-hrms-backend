# attendance/api/urls.py
from django.urls import path
from . import views, manager_views

urlpatterns = [
    # 1) Calendar / Monthly Listing
    path('department/<int:dept_id>/monthly/', views.DepartmentMonthlyAttendanceView.as_view(), name='att-dept-monthly'),

    # 2) Leave Applications
    path('leaves/apply/', views.LeaveApplyView.as_view(), name='leave-apply'),
    path('leaves/manager/list/', views.ManagerLeaveApplicationListView.as_view(), name='leave-manager-list'),
    path('leaves/manager/<int:leave_id>/detail/', views.LeaveApplicationDetailView.as_view(), name='leave-manager-detail'),
    path('leaves/<int:leave_id>/<str:action>/', views.LeaveActionView.as_view(), name='leave-action'),

    # 3) Mark Absent
    path('mark-absent/', views.MarkAbsentView.as_view(), name='att-mark-absent'),

    # 4) Bulk Upload
    path('bulk-upload/', views.BulkAttendanceUploadView.as_view(), name='att-bulk-upload'),

    # 5) Employee leave history
    path('leaves/my-history/', views.MyLeaveApplicationListView.as_view(), name='leave-my-history'),

    # 6) Employee leave history
    path('holiday-pattern/', views.BulkMarkHolidaysView.as_view(), name='holiday-pattern'),

    # 7) Dept Manager Dashboard
    path('manager/dashboard-stats/', manager_views.ManagerDashboardStatsView.as_view(), name='manager-dashboard-stats'),

    # 8) Employee Balance
    path('leave-balance/<str:employee_code>/', views.EmployeeLeaveBalanceView.as_view(), name='leave-balance'),

    # 9) Employee Calendar view,
    path('emp/monthly-attendance/<str:emp_code>/<int:year>/<int:month>/', views.EmployeeMonthlyAttendanceView.as_view(), name='employee-calendar'),
]