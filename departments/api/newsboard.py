# departments/api/newsboard.py
from rest_framework import serializers
from django.utils import timezone
from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.http import FileResponse, Http404
from django.db.models import Q

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny

from departments.models import News


# Serializers
class NewsSerializer(serializers.ModelSerializer):

    file_url = serializers.SerializerMethodField()

    class Meta:
        model = News
        fields = [
            "th_urid",
            "title",
            "news_file",
            "file_url",
            "has_attachment",
            "publish_date",
            "expiry_date",
            "is_pinned",
            "is_active",
        ]

        read_only_fields = [
            "th_urid",
            "publish_date",
            "has_attachment",
            "file_url",
        ]

    def get_file_url(self, obj):

        request = self.context.get("request")

        if obj.news_file:
            return request.build_absolute_uri(obj.news_file.url)

        return None

    def validate(self, attrs):

        expiry = attrs.get(
            "expiry_date",
            getattr(self.instance, "expiry_date", None)
        )

        if expiry and expiry < timezone.now():
            raise serializers.ValidationError(
                {
                    "expiry_date": "Expiry date cannot be in the past."
                }
            )

        return attrs
    
# Custom Permissions
class NewsPublicReadPermission(BasePermission):

    def has_permission(self, request, view):

        if request.method in SAFE_METHODS:
            return True

        return request.user.is_authenticated
    
# Views
class NewsViewSet(viewsets.ModelViewSet):

    serializer_class = NewsSerializer
    lookup_field = "th_urid"

    permission_classes = [NewsPublicReadPermission]

    def get_queryset(self):

        queryset = News.objects.filter(
            is_active=True
        )

        if self.request.method == "GET":

            queryset = queryset.filter(
                Q(expiry_date__isnull=True) |
                Q(expiry_date__gte=timezone.now())
            )

        return queryset

    def perform_create(self, serializer):

        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user,
            is_active=True,
        )

    def perform_update(self, serializer):

        serializer.save(
            updated_by=self.request.user
        )

    def perform_destroy(self, instance):

        instance.delete(
            by_user=self.request.user
        )

    @action(
        detail=True,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="download",
    )
    def download(self, request, th_urid=None):

        news = self.get_object()

        if not news.news_file:
            raise Http404

        return FileResponse(
            news.news_file.open("rb"),
            as_attachment=True,
            filename=news.news_file.name.split("/")[-1],
        )