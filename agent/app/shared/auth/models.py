"""
Auth0 Models for ai-workflow-automation Core

This module defines data models for Auth0 authentication.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class Auth0Claims(BaseModel):
    """Auth0 JWT token claims"""
    sub: str = Field(..., description="Auth0 user ID")
    email: Optional[str] = Field(None, description="User email")
    email_verified: Optional[bool] = Field(None, description="Email verification status")
    name: Optional[str] = Field(None, description="User name")
    picture: Optional[str] = Field(None, description="User picture URL")
    nickname: Optional[str] = Field(None, description="User nickname")
    aud: List[str] = Field(default_factory=list, description="Token audience")
    iss: str = Field(..., description="Token issuer")
    scope: Optional[str] = Field(None, description="Token scope")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    iat: Optional[int] = Field(None, description="Issued at timestamp")
    exp: Optional[int] = Field(None, description="Expiration timestamp")
    
    @property
    def user_id(self) -> str:
        """Get Auth0 user ID"""
        return self.sub
    
    @property
    def is_email_verified(self) -> bool:
        """Check if email is verified"""
        return self.email_verified or False
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        return permission in self.permissions
    
    def has_scope(self, scope: str) -> bool:
        """Check if token has specific scope"""
        if not self.scope:
            return False
        token_scopes = self.scope.split()
        return scope in token_scopes


class Auth0User(BaseModel):
    """Auth0 authenticated user model"""
    auth_id: str = Field(..., description="Auth0 user ID")
    email: Optional[str] = Field(None, description="User email")
    name: Optional[str] = Field(None, description="User name")
    picture: Optional[str] = Field(None, description="User picture URL")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    scope: Optional[str] = Field(None, description="Token scope")
    
    # Database user information (if exists)
    db_user_id: Optional[str] = Field(None, description="Database user ID")
    exists_in_db: bool = Field(False, description="Whether user exists in database")
    
    @property
    def user_id(self) -> Optional[str]:
        """Get database user ID if available, otherwise Auth0 ID"""
        return self.db_user_id or self.auth_id
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        return permission in self.permissions
    
    def has_scope(self, scope: str) -> bool:
        """Check if token has specific scope"""
        if not self.scope:
            return False
        token_scopes = self.scope.split()
        return scope in token_scopes


class AuthContext(BaseModel):
    """Authentication context for requests"""
    user: Auth0User
    correlation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
