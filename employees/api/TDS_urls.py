from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .TDSForm_views import TDSFormViewSet

router = DefaultRouter()
router.register(r'tds-forms', TDSFormViewSet, basename='tds-forms')

# Automatically includes:
# GET/POST    -> /tds-forms/
# GET/PUT/DEL -> /tds-forms/{th_urid}/
# GET         -> /tds-forms/{th_urid}/download/
# POST        -> /tds-forms/bulk-upload-zip/

urlpatterns = [
    path('', include(router.urls)),
]