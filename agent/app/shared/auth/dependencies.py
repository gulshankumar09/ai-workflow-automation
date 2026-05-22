"""
FastAPI Dependencies for Auth0 Authentication

This module provides FastAPI dependencies for Auth0 authentication.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.shared.logger import get_logger
from app.shared.exceptions import ValidationException
from app.application.user_service import UserService
from app.shared.dependency_injection import get_dependency_container
from .jwt_validator import validate_auth0_token
from .models import Auth0User, Auth0Claims

logger = get_logger(__name__)

# Security scheme for OpenAPI/Swagger
security = HTTPBearer()


async def get_token_from_header(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Extract JWT token from Authorization header.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        JWT token string
        
    Raises:
        HTTPException: If token format is invalid
    """
    if not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return credentials.credentials


async def get_token_from_header_optional(
    authorization: Optional[str] = Header(None)
) -> Optional[str]:
    """
    Extract JWT token from Authorization header (optional).
    
    Args:
        authorization: Authorization header value
        
    Returns:
        JWT token string or None
    """
    if not authorization:
        return None
    
    if not authorization.startswith("Bearer "):
        return None
    
    return authorization[7:]  # Remove "Bearer " prefix


async def get_auth0_claims(token: str = Depends(get_token_from_header)) -> Auth0Claims:
    """
    Validate Auth0 token and return claims.
    
    Args:
        token: JWT token string
        
    Returns:
        Auth0Claims object
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        claims = await validate_auth0_token(token)
        return claims
    except ValidationException as e:
        logger.warning(f"Token validation failed: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Unexpected error validating token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user(
    claims: Auth0Claims = Depends(get_auth0_claims),
    request: Request = None
) -> Auth0User:
    """
    Get current authenticated user.
    
    Args:
        claims: Auth0 token claims
        request: FastAPI request object
        
    Returns:
        Auth0User object with database information if available
        
    Raises:
        HTTPException: If user validation fails
    """
    try:
        # Create base user from claims
        user = Auth0User(
            auth_id=claims.sub,
            email=claims.email,
            name=claims.name,
            picture=claims.picture,
            permissions=claims.permissions,
            scope=claims.scope,
            exists_in_db=False
        )
        
        # Try to get user from database
        try:
            container = get_dependency_container()
            user_service = UserService(dependency_container=container)
            
            # Look up user by Auth0 ID
            db_user = await user_service.get_user_by_auth_id(claims.sub)
            if db_user:
                user.db_user_id = db_user.get("id")
                user.exists_in_db = True
                
                # Update user info from database if available
                if db_user.get("email"):
                    user.email = db_user["email"]
                if db_user.get("name"):
                    user.name = db_user["name"]
                
                logger.debug(f"User found in database: {user.db_user_id}")
            else:
                logger.debug(f"User not found in database: {claims.sub}")
                
        except Exception as e:
            logger.warning(f"Could not fetch user from database: {str(e)}")
            # Continue without database user info
        
        # Store user in request state for later access
        if request:
            request.state.current_user = user
        
        return user
        
    except Exception as e:
        logger.error(f"Error creating user object: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User authentication failed"
        )


async def get_current_user_optional(
    request: Request,
    token: Optional[str] = Depends(get_token_from_header_optional)
) -> Optional[Auth0User]:
    """
    Get current user if authenticated, otherwise return None.
    
    Args:
        request: FastAPI request object
        token: Optional JWT token
        
    Returns:
        Auth0User object or None
    """
    if not token:
        return None
    
    try:
        claims = await validate_auth0_token(token)
        return await get_current_user(claims, request)
    except Exception:
        # Silently ignore authentication errors for optional auth
        return None


async def require_user_in_db(
    user: Auth0User = Depends(get_current_user)
) -> Auth0User:
    """
    Require that the authenticated user exists in the database.
    
    Args:
        user: Current authenticated user
        
    Returns:
        Auth0User object
        
    Raises:
        HTTPException: If user doesn't exist in database
    """
    if not user.exists_in_db:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account not found in database. Please complete account setup."
        )
    
    return user


def require_permission(permission: str):
    """
    Create a dependency that requires a specific permission.
    
    Args:
        permission: Required permission string
        
    Returns:
        FastAPI dependency function
    """
    async def permission_checker(user: Auth0User = Depends(get_current_user)) -> Auth0User:
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' is required"
            )
        return user
    
    return permission_checker


def require_scope(scope: str):
    """
    Create a dependency that requires a specific scope.
    
    Args:
        scope: Required scope string
        
    Returns:
        FastAPI dependency function
    """
    async def scope_checker(user: Auth0User = Depends(get_current_user)) -> Auth0User:
        if not user.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{scope}' is required"
            )
        return user
    
    return scope_checker


# Convenience alias for backward compatibility
require_auth = get_current_user
