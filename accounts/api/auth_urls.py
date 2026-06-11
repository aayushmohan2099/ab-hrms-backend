# accounts/api/auth_urls.py
from django.urls import path
from . import login_view as auth_views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path("captcha/", auth_views.CaptchaView.as_view()),
    path('refresh/', auth_views.RefreshTokenView.as_view(), name='token_refresh'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]