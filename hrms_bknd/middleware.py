"""
API JWT-aware middleware for HRMS.

Rules implemented:
- Allow all non-API paths through natively.
- Allow all /api/v1/auth/* (login, captcha, refresh) without headers.
- Require valid JWT Bearer token for all other /api/ endpoints.
"""
from django.http import JsonResponse, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model

from rest_framework_simplejwt.tokens import AccessToken, TokenError


class HRMSJwtAuthMiddleware(MiddlewareMixin):
    """
    Middleware that enforces JWT authentication globally on API routes, 
    bypassing the need for explicit permission classes on every single view.
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.get_response = get_response

    def _validate_access_token(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            return None, "Missing Authorization header"

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None, "Invalid Authorization header format. Expected 'Bearer <token>'"

        token_str = parts[1]
        try:
            access = AccessToken(token_str)
        except TokenError:
            return None, "Invalid or expired access token"

        user_id = access.payload.get("user_id")
        if not user_id:
            return None, "Access token missing user_id"

        User = get_user_model()
        try:
            user = User.objects.select_related('role').get(pk=int(user_id))
        except User.DoesNotExist:
            return None, "User not found for access token"

        if not getattr(user, "is_active", False):
            return None, "User account is inactive"
            
        if getattr(user, "deleted_at", None) is not None:
            return None, "User account has been deleted"

        return user, None

    def process_request(self, request):
        path = request.path or ""

        # ---------------------------------------------
        # Handle Preflight CORS Requests
        # ---------------------------------------------
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
            # Origin handling is typically done by corsheaders middleware, 
            # but we explicitly clear Allow headers here if needed.
            response.headers.pop("Allow", None)
            return response

        # Skip non-API paths entirely (Django Admin, Media, Static)
        if not path.startswith("/api/"):
            return None

        # Allow open access to Public endpoints
        if path.startswith("/api/v1/public/"):
            return None

        # Allow open access to Authentication endpoints (Login, Captcha, Refresh, Logout)
        if path.startswith("/api/v1/auth/"):
            return None

        # -------------------------------------------------
        # For all other /api/ routes -> Enforce JWT validation
        # -------------------------------------------------
        user, error_reason = self._validate_access_token(request)
        
        if not user:
            return JsonResponse({"detail": error_reason}, status=401)
            
        # Attach the resolved user and role to the request for downstream views/audit logs
        request.user = user
        request.role_code = user.role.code if user.role else None

        # If you wanted to do Route vs Role namespace checks in the future, 
        # you would add them right here based on request.role_code.
        
        return None

    def process_response(self, request, response):
        # Prevent Allowed Methods exposure 
        response.headers.pop("Allow", None)       
        return response