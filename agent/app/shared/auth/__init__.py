"""
Authentication module for ai-workflow-automation Core
"""

from .models import Auth0User, Auth0Claims
from .jwt_validator import validate_auth0_token, get_jwks
from .dependencies import (
    get_current_user, 
    get_current_user_optional, 
    require_auth,
    require_user_in_db,
    require_permission,
    require_scope
)

__all__ = [
    "Auth0User",
    "Auth0Claims", 
    "validate_auth0_token",
    "get_jwks",
    "get_current_user",
    "get_current_user_optional",
    "require_auth",
    "require_user_in_db",
    "require_permission",
    "require_scope"
]
