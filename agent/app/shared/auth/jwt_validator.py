"""
JWT Validator for Auth0 tokens

This module provides utilities for validating Auth0 JWT tokens.
"""

import json
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from fastapi import HTTPException, status

from app.shared.logger import get_logger
from app.shared.config import get_settings
from app.shared.exceptions import ValidationException, create_error_context
from .models import Auth0Claims

logger = get_logger(__name__)

# Cache for JWKS
_jwks_cache: Optional[Dict[str, Any]] = None
_jwks_cache_expiry: Optional[datetime] = None


async def get_jwks(domain: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Get JWKS (JSON Web Key Set) from Auth0 with caching.
    
    Args:
        domain: Auth0 domain
        force_refresh: Force refresh of cached JWKS
        
    Returns:
        JWKS dictionary
        
    Raises:
        ValidationException: If JWKS cannot be fetched
    """
    global _jwks_cache, _jwks_cache_expiry
    
    settings = get_settings()
    now = datetime.utcnow()
    cache_ttl = timedelta(seconds=settings.auth0.jwks_cache_ttl)
    
    # Check if we need to refresh the cache
    if (force_refresh or 
        _jwks_cache is None or 
        _jwks_cache_expiry is None or 
        now > _jwks_cache_expiry):
        
        jwks_url = f"https://{domain}/.well-known/jwks.json"
        
        try:
            logger.info(f"Fetching JWKS from: {jwks_url}")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(jwks_url)
                response.raise_for_status()
                
            _jwks_cache = response.json()
            _jwks_cache_expiry = now + cache_ttl
            
            logger.info("JWKS fetched and cached successfully")
            
        except httpx.TimeoutException:
            logger.error(f"Timeout fetching JWKS from {jwks_url}")
            if _jwks_cache is None:
                raise ValidationException(
                    "Failed to fetch JWKS: Timeout",
                    details=create_error_context(
                        operation="get_jwks",
                        component="jwt_validator",
                        jwks_url=jwks_url,
                        error_type="TimeoutException"
                    )
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching JWKS: {e.response.status_code}")
            if _jwks_cache is None:
                raise ValidationException(
                    f"Failed to fetch JWKS: HTTP {e.response.status_code}",
                    details=create_error_context(
                        operation="get_jwks",
                        component="jwt_validator",
                        jwks_url=jwks_url,
                        error_type="HTTPStatusError",
                        status_code=e.response.status_code
                    )
                )
        except Exception as e:
            logger.error(f"Unexpected error fetching JWKS: {str(e)}")
            if _jwks_cache is None:
                raise ValidationException(
                    f"Failed to fetch JWKS: {str(e)}",
                    details=create_error_context(
                        operation="get_jwks",
                        component="jwt_validator",
                        jwks_url=jwks_url,
                        error_type=type(e).__name__,
                        error_message=str(e)
                    )
                )
    
    return _jwks_cache


def get_rsa_key_from_jwks(token: str, jwks: Dict[str, Any]) -> Any:
    """
    Get RSA public key from JWKS for token validation.
    
    Args:
        token: JWT token
        jwks: JWKS dictionary
        
    Returns:
        RSA public key
        
    Raises:
        ValidationException: If key cannot be found or extracted
    """
    try:
        # Get the key ID from token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            raise ValidationException(
                "Token missing key ID (kid) in header",
                details=create_error_context(
                    operation="get_rsa_key_from_jwks",
                    component="jwt_validator",
                    error_type="MissingKid"
                )
            )
        
        # Find the matching key in JWKS
        keys = jwks.get("keys", [])
        matching_key = None
        
        for key in keys:
            if key.get("kid") == kid and key.get("kty") == "RSA":
                matching_key = key
                break
        
        if not matching_key:
            raise ValidationException(
                f"No RSA key found with kid: {kid}",
                details=create_error_context(
                    operation="get_rsa_key_from_jwks",
                    component="jwt_validator",
                    error_type="KeyNotFound",
                    kid=kid,
                    available_kids=[key.get("kid") for key in keys]
                )
            )
        
        # Convert JWK to RSA public key with better error handling
        try:
            # Ensure the key has required components
            if not all(key in matching_key for key in ["n", "e"]):
                raise ValidationException(
                    f"JWK missing required components: {matching_key}",
                    details=create_error_context(
                        operation="get_rsa_key_from_jwks",
                        component="jwt_validator",
                        error_type="InvalidJWK",
                        kid=kid
                    )
                )
            
            # Convert using PyJWT's built-in method
            rsa_key = RSAAlgorithm.from_jwk(matching_key)
            return rsa_key
            
        except (ValueError, TypeError) as e:
            # Try alternative approach for key conversion
            logger.warning(f"Standard JWK conversion failed, trying alternative method: {str(e)}")
            try:
                rsa_key = RSAAlgorithm.from_jwk(json.dumps(matching_key))
                return rsa_key
            except Exception as e2:
                raise ValidationException(
                    f"Failed to convert JWK to RSA key: {str(e2)}",
                    details=create_error_context(
                        operation="get_rsa_key_from_jwks",
                        component="jwt_validator",
                        error_type="JWKConversionError",
                        kid=kid,
                        original_error=str(e),
                        secondary_error=str(e2)
                    )
                )
        
    except ValidationException:
        raise
    except jwt.InvalidTokenError as e:
        raise ValidationException(
            f"Invalid token format: {str(e)}",
            details=create_error_context(
                operation="get_rsa_key_from_jwks",
                component="jwt_validator",
                error_type="InvalidTokenFormat",
                error_message=str(e)
            )
        )
    except Exception as e:
        raise ValidationException(
            f"Failed to extract RSA key: {str(e)}",
            details=create_error_context(
                operation="get_rsa_key_from_jwks",
                component="jwt_validator",
                error_type=type(e).__name__,
                error_message=str(e)
            )
        )


async def debug_jwt_token(token: str) -> Dict[str, Any]:
    """
    Debug utility to analyze JWT token structure.
    
    Args:
        token: JWT token to analyze
        
    Returns:
        Debug information about the token
    """
    debug_info = {
        "token_valid": False,
        "header": None,
        "payload": None,
        "error": None
    }
    
    try:
        # Check if token has proper format (3 parts separated by dots)
        parts = token.split('.')
        debug_info["parts_count"] = len(parts)
        
        if len(parts) != 3:
            debug_info["error"] = f"Invalid JWT format: expected 3 parts, got {len(parts)}"
            return debug_info
        
        # Try to decode header
        try:
            header = jwt.get_unverified_header(token)
            debug_info["header"] = header
        except Exception as e:
            debug_info["header_error"] = str(e)
        
        # Try to decode payload (without verification)
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            debug_info["payload"] = payload
        except Exception as e:
            debug_info["payload_error"] = str(e)
        
        debug_info["token_valid"] = True
        
    except Exception as e:
        debug_info["error"] = str(e)
    
    return debug_info


async def validate_auth0_token(token: str) -> Auth0Claims:
    """
    Validate Auth0 JWT token and return claims.
    
    Args:
        token: JWT token to validate
        
    Returns:
        Auth0Claims object with validated claims
        
    Raises:
        ValidationException: If token is invalid or validation fails
    """
    try:
        settings = get_settings()
        auth_settings = settings.auth0
        
        # Debug token if in development
        if settings.environment == "development":
            debug_info = await debug_jwt_token(token)
            logger.debug(f"JWT Debug Info: {debug_info}")
        
        # Get JWKS for key validation
        jwks = await get_jwks(auth_settings.domain)
        
        # Extract RSA key from JWKS
        rsa_key = get_rsa_key_from_jwks(token, jwks)
        
        # Validate token
        payload = jwt.decode(
            token,
            key=rsa_key,
            algorithms=["RS256"],
            audience=auth_settings.audience,
            issuer=f"https://{auth_settings.domain}/",
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iat": True,
                "verify_exp": True,
                "verify_iss": True
            }
        )
        
        # Create claims object
        claims = Auth0Claims(**payload)
        
        logger.info(f"Token validated successfully for user: {claims.sub}")
        return claims
        
    except jwt.ExpiredSignatureError:
        raise ValidationException(
            "Token has expired",
            details=create_error_context(
                operation="validate_auth0_token",
                component="jwt_validator",
                error_type="ExpiredToken"
            )
        )
    except jwt.InvalidAudienceError:
        raise ValidationException(
            "Invalid token audience",
            details=create_error_context(
                operation="validate_auth0_token",
                component="jwt_validator",
                error_type="InvalidAudience",
                expected_audience=auth_settings.audience
            )
        )
    except jwt.InvalidIssuerError:
        raise ValidationException(
            "Invalid token issuer",
            details=create_error_context(
                operation="validate_auth0_token",
                component="jwt_validator",
                error_type="InvalidIssuer",
                expected_issuer=f"https://{auth_settings.domain}/"
            )
        )
    except jwt.InvalidTokenError as e:
        raise ValidationException(
            f"Invalid JWT token: {str(e)}",
            details=create_error_context(
                operation="validate_auth0_token",
                component="jwt_validator",
                error_type="InvalidToken",
                error_message=str(e)
            )
        )
    except ValidationException:
        # Re-raise our custom validation exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error validating token: {str(e)}")
        raise ValidationException(
            f"Token validation failed: {str(e)}",
            details=create_error_context(
                operation="validate_auth0_token",
                component="jwt_validator",
                error_type=type(e).__name__,
                error_message=str(e)
            )
        )
