# accounts/api/login_view.py
import random
import string
import io
import base64
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

# Cookie name for storing refresh token (httpOnly)
REFRESH_COOKIE_NAME = 'hrms_refresh'

def _get_refresh_cookie_max_age():
    delta = getattr(settings, 'SIMPLE_JWT', {}).get('REFRESH_TOKEN_LIFETIME', None)
    if delta:
        try:
            return int(delta.total_seconds())
        except Exception:
            pass
    return 7 * 24 * 3600


class CaptchaView(APIView):
    permission_classes = (permissions.AllowAny,)
    CAPTCHA_SESSION_KEY = "login_captcha"
    CAPTCHA_EXPIRY_SECONDS = 180  # 3 minutes

    def get(self, request):
        captcha_text = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )

        request.session[self.CAPTCHA_SESSION_KEY] = {
            "value": captcha_text,
            "expires": (
                timezone.now() + timedelta(seconds=self.CAPTCHA_EXPIRY_SECONDS)
            ).timestamp(),
        }

        width, height = 300, 100
        image = Image.new("RGB", (width, height), (255, 255, 255))
        draw = ImageDraw.Draw(image)

        font_paths = [
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/fira-code/FiraCode-Bold.ttf",
        ]
        
        font = None
        for path in font_paths:
            try:
                font = ImageFont.truetype(path, 54)
                break
            except IOError:
                continue
                
        if not font:
            font = ImageFont.load_default()

        char_width = width // 8
        x = 25

        for char in captcha_text:
            y_offset = random.randint(-5, 5)
            
            # Use 'L' mode mask to prevent black box bug
            mask = Image.new('L', (80, 80), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.text((10, 5), char, font=font, fill=255)

            # Match reference rotation bounds (-15, 15)
            rotated_mask = mask.rotate(random.randint(-15, 15), expand=1)

            text_color = (20, 20, 20)
            image.paste(text_color, (x, 15 + y_offset), rotated_mask)

            x += char_width

        # Match reference dots
        for _ in range(150):
            draw.point(
                (random.randint(0, width), random.randint(0, height)),
                fill=(180, 180, 180),
            )

        # Match reference exact single strike-through line
        draw.line(
            (0, random.randint(30, 70), width, random.randint(30, 70)),
            fill=(200, 200, 200),
            width=2,
        )
        
        image = image.filter(ImageFilter.SMOOTH)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return Response({"image": f"data:image/png;base64,{img_str}"})
    

class LoginView(APIView):
    permission_classes = (permissions.AllowAny,)

    @staticmethod
    def get_client_ip(request):
        """Accurately extract client IP, handling proxies like Nginx."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def post(self, request):
        payload = request.data
        
        username = payload.get("username")
        password = payload.get("password")
        captcha_input = payload.get("captcha")

        # ---------------------------------
        # 1. Captcha Validation
        # ---------------------------------
        captcha_data = request.session.get("login_captcha")

        if not captcha_input or not captcha_data:
            return Response(
                {"detail": "Captcha required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if timezone.now().timestamp() > captcha_data.get("expires", 0):
            return Response(
                {"detail": "Captcha expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if captcha_input.strip().upper() != captcha_data.get("value"):
            return Response(
                {"detail": "Invalid captcha"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Clear captcha after successful validation
        request.session.pop("login_captcha", None)

        # ---------------------------------
        # 2. Credentials Validation
        # ---------------------------------
        if not username or not password:
            return Response(
                {"detail": "Username and password required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)

        if not user:
            return Response(
                {"detail": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"detail": "Account inactive"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ---------------------------------
        # 3. Issue JWT tokens
        # ---------------------------------
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token

        # ---------------------------------
        # 4. Format Safe User Response
        # ---------------------------------
        user_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "employee_code": user.employee_code,
            "phone_number": user.phone_number,
            "employee_type": user.employee_type,
            "role_code": user.role.code if user.role else None,
            "role_name": user.role.name if user.role else None,
            "is_active": user.is_active,
            "th_urid": user.th_urid,
        }

        response = Response(
            {
                "message": "Login successful",
                "access": str(access_token),
                "refresh": str(refresh), 
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )

        response.set_cookie(
            REFRESH_COOKIE_NAME,
            str(refresh),
            max_age=_get_refresh_cookie_max_age(),
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            path="/",
        )

        return response


class RefreshTokenView(APIView):
    """
    Obtain a new access token by reading the refresh token from an HttpOnly cookie.
    """
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        refresh_token = (
            request.COOKIES.get(REFRESH_COOKIE_NAME)
            or request.data.get("refresh")
        )
        
        if not refresh_token:
            return Response({'detail': 'Missing refresh token'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(refresh_token)
        except TokenError:
            return Response({'detail': 'Invalid or expired refresh token'}, status=status.HTTP_401_UNAUTHORIZED)

        access = refresh.access_token
        return Response({'access': str(access)}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist() 
            except TokenError:
                pass # Token already expired or invalid

        response = Response({"detail": "Logged out successfully"}, status=status.HTTP_200_OK)
        response.delete_cookie(
            REFRESH_COOKIE_NAME,
            path="/",
        )
        return response