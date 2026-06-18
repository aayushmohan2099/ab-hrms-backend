# hrms_bknd/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="AB-HRMS API",
      default_version='v1',
      description="API Directory for Different Apps in AB-HRMS System",
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include(('accounts.api.auth_urls', 'accounts_auth'), namespace='accounts_auth')),
    path('api/v1/users/', include(('accounts.api.urls', 'accounts_users'), namespace='accounts_users')),
    path('api/v1/employees/', include(('employees.api.urls', 'employees'), namespace='employees')),
    path('api/v1/attendance/', include(('attendance.api.urls', 'attendance'), namespace='attendance')),
    path('api/v1/departments/', include(('departments.api.urls', 'departments'), namespace='departments')),
    path('api/v1/salary-slips/', include(('salary_slips.api.urls', 'salary_slips'), namespace='salary_slips')),
    path(
        'api/v1/dept/design/',
        include(('designations.api.urls', 'designations'),
        namespace='designations')
    ),
    path(
        'api/v1/dept/design/',
        include(('core.api.urls', 'core'),
        namespace='core')
    ),
    path(
        'api/v1/dept/design/',
        include(('payroll.api.urls', 'payroll'),
        namespace='payroll')
    ),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]

urlpatterns += [
    path(
        "swagger.json",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    path(
        "swagger.yaml",
        schema_view.without_ui(cache_timeout=0),
        name="schema-yaml",
    ),
]