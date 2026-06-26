# departments/api/urls.py

from rest_framework.routers import DefaultRouter
from .newsboard import NewsViewSet

router = DefaultRouter()

router.register(
    "news",
    NewsViewSet,
    basename="news"
)

urlpatterns = router.urls