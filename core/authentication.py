# core/authentication.py  ── FINAL VERSION
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings
from rest_framework.exceptions import AuthenticationFailed
from uuid import UUID
from core.models import User  # import your User model directly

class UUIDJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user_id_claim = api_settings.USER_ID_CLAIM
        user_id_str = validated_token.get(user_id_claim)

        if not user_id_str:
            raise AuthenticationFailed("Invalid token - no user_id claim")

        # Keep as STRING — do NOT convert to UUID object
        # Django UUIDField can query with string values perfectly

        try:
            # Optional: validate it's a valid UUID format
            UUID(user_id_str)
        except ValueError:
            raise AuthenticationFailed("Invalid user ID format in token")

        try:
            # Query with STRING value
            user = User.objects.get(id=user_id_str)
        except User.DoesNotExist:
            raise AuthenticationFailed("User not found")

        return user