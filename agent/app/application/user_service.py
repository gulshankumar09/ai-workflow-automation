"""
User Service - Core Application Service for User Context and Preferences Management

This service implements user context management, preferences, session handling,
and user-specific tool access control.

Key Features:
- User context loading and persistence
- User preferences management
- Session management across multiple connection types
- User tool access control
- Context caching and optimization
- User personalization and learning
"""

import time
import uuid
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta, timezone
from enum import Enum
from app.shared import get_logger

from pydantic import BaseModel, Field

from app.shared.CustomBaseModel import CustomBaseModel
from app.shared.exceptions import (
    NotFoundException,
    ValidationException,
    AuthenticationException,
    AuthorizationException,
    DatabaseException
)
from app.shared.config import get_settings
from app.infrastructure.database.providers.factory import DatabaseProviderFactory
from app.infrastructure.cache.factory import CacheProviderFactory
from app.domains.mcp.services import MCPOperationsService

logger = get_logger(__name__)
class SessionType(Enum):
    """Session type enumeration"""
    ANONYMOUS = "anonymous"
    AUTHENTICATED = "authenticated" 
    WEBSOCKET = "websocket"
    EXECUTION = "execution"


class UserPreferences(CustomBaseModel):
    """User preferences model"""
    default_tools: Dict[str, str] = Field(default_factory=dict)
    workflow_settings: Dict[str, Any] = Field(default_factory=dict)
    notification_preferences: Dict[str, Any] = Field(default_factory=dict)
    ui_preferences: Dict[str, Any] = Field(default_factory=dict)
    privacy_settings: Dict[str, Any] = Field(default_factory=dict)


class UserContext(CustomBaseModel):
    """User context model"""
    user_id: str
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    workflow_patterns: List[Dict[str, Any]] = Field(default_factory=list)
    tool_usage_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    recent_activity: Dict[str, Any] = Field(default_factory=dict)
    personalization: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class UserSession(CustomBaseModel):
    """User session model"""
    session_id: str
    user_id: str
    session_type: SessionType
    connection_id: Optional[str] = None
    user_context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    last_activity: datetime
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UserToolConnection(CustomBaseModel):
    """User tool connection model"""
    user_id: str
    tool_name: str
    server_name: str
    credentials_encrypted: str
    scopes: List[str] = Field(default_factory=list)
    is_active: bool = True
    connected_at: datetime
    last_used_at: Optional[datetime] = None


class UserService:
    """
    Core service for user context and preferences management
    
    This service provides comprehensive user management including context
    loading, preferences, sessions, and tool access control.
    """
    
    def __init__(
        self,
        database_provider_factory: Optional[DatabaseProviderFactory] = None,
        cache_provider_factory: Optional[CacheProviderFactory] = None,
        correlation_id: Optional[str] = None,
        dependency_container = None
    ):
        from app.shared.dependency_injection import get_dependency_container
        
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.settings = get_settings()
        
        # Use dependency injection container if provided
        if dependency_container:
            self.dependency_container = dependency_container
            self.database = dependency_container.create_database_provider()
            self.cache = dependency_container.create_cache_provider()
        else:
            # Fallback to manual factory creation with dependency injection
            container = get_dependency_container(self.correlation_id)
            self.database = container.create_database_provider()
            self.cache = container.create_cache_provider()
        
        # Session configuration
        self.session_configs = {
            SessionType.ANONYMOUS: {"ttl": 900, "auto_extend": False},      # 15 minutes
            SessionType.AUTHENTICATED: {"ttl": 3600, "auto_extend": True},   # 60 minutes
            SessionType.WEBSOCKET: {"ttl": 14400, "auto_extend": True},     # 4 hours max
            SessionType.EXECUTION: {"ttl": 7200, "auto_extend": True}       # 2 hours max
        }
        
        # Cache TTL settings
        self.context_cache_ttl = 1800  # 30 minutes
        self.preferences_cache_ttl = 3600  # 1 hour
        self.session_cache_ttl = 300  # 5 minutes
    
    # User Context Management
    
    async def get_user_context(
        self, 
        user_id: str,
        context_keys: Optional[List[str]] = None,
        correlation_id: Optional[str] = None
    ) -> UserContext:
        """
        Get user context with priority hierarchy caching
        
        Args:
            user_id: User identifier
            context_keys: Specific context keys to load (optional)
            
        Returns:
            User context object
        """
        try:
            # Check cache first
            cache_key = f"user_context:{user_id}"
            cached_context = await self.cache.get(cache_key)
            
            if cached_context:
                context = UserContext(**cached_context)
                # Filter to requested keys if specified
                if context_keys:
                    context = self._filter_context_keys(context, context_keys)
                return context
            
            # Load from database
            context_data = await self._load_context_from_database(user_id, context_keys)
            
            if not context_data:
                # Create default context
                context = await self._create_default_user_context(user_id)
            else:
                context = UserContext(**context_data)
            
            # Cache the full context
            await self.cache.set(cache_key, context.model_dump(), ttl=self.context_cache_ttl)
            
            return context
            
        except Exception as e:
            raise DatabaseException(
                f"Failed to get user context for {user_id}: {str(e)}",
                correlation_id=self.correlation_id,
                details={"user_id": user_id, "context_keys": context_keys}
            )
    
    async def update_user_context(
        self, 
        user_id: str, 
        context_updates: Dict[str, Any],
        merge: bool = True
    ) -> UserContext:
        """
        Update user context with new data
        
        Args:
            user_id: User identifier
            context_updates: Updates to apply
            merge: Whether to merge with existing context or replace
            
        Returns:
            Updated user context
        """
        try:
            if merge:
                # Get current context and merge updates
                current_context = await self.get_user_context(user_id)
                updated_data = current_context.model_dump()
                
                # Deep merge updates
                updated_data = self._deep_merge_dict(updated_data, context_updates)
            else:
                # Replace context
                updated_data = context_updates
            
            updated_data["user_id"] = user_id
            updated_data["updated_at"] = datetime.utcnow()
            
            # Validate context data
            updated_context = UserContext(**updated_data)
            
            # Update database
            await self.database.upsert(
                "user_contexts",
                {
                    "user_id": user_id,
                    "context_data": updated_context.model_dump(),
                    "updated_at": datetime.utcnow().isoformat()
                }
            )
            
            # Update cache
            cache_key = f"user_context:{user_id}"
            await self.cache.set(cache_key, updated_context.model_dump(), ttl=self.context_cache_ttl)
            
            return updated_context
            
        except Exception as e:
            raise DatabaseException(
                f"Failed to update user context for {user_id}: {str(e)}",
                correlation_id=self.correlation_id,
                details={"user_id": user_id, "updates": context_updates}
            )
    
    async def get_user_preferences(self, user_id: str) -> UserPreferences:
        """Get user preferences"""
        try:
            context = await self.get_user_context(user_id, ["preferences"])
            return context.preferences
            
        except Exception as e:
            raise DatabaseException(
                f"Failed to get user preferences for {user_id}: {str(e)}",
                correlation_id=self.correlation_id
            )
    
    async def update_user_preferences(
        self, 
        user_id: str, 
        preferences: Dict[str, Any]
    ) -> UserPreferences:
        """Update user preferences"""
        try:
            # Get current context
            context = await self.get_user_context(user_id)
            
            # Update preferences
            current_prefs = context.preferences.model_dump()
            updated_prefs = self._deep_merge_dict(current_prefs, preferences)
            
            # Validate preferences
            validated_prefs = UserPreferences(**updated_prefs)
            
            # Update context
            await self.update_user_context(user_id, {"preferences": validated_prefs.model_dump()})
            
            return validated_prefs
            
        except Exception as e:
            raise ValidationException(
                f"Failed to update user preferences for {user_id}: {str(e)}",
                correlation_id=self.correlation_id,
                details={"user_id": user_id, "preferences": preferences}
            )
    
    # Session Management
    
    async def create_session(
        self,
        user_id: str,
        session_type: SessionType,
        connection_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new user session"""
        try:
            session_id = f"session_{int(time.time())}_{user_id}_{str(uuid.uuid4())[:8]}"
            config = self.session_configs[session_type]
            
            # Load user context for session
            if user_id != "anonymous":
                user_context = await self.get_user_context(user_id)
                context_data = user_context.model_dump()
            else:
                context_data = {}
            
            # Create session object
            session = UserSession(
                session_id=session_id,
                user_id=user_id,
                session_type=session_type,
                connection_id=connection_id,
                user_context=context_data,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                metadata=metadata or {}
            )
            
            # Store in cache
            cache_key = f"session:{session_id}"
            await self.cache.set(cache_key, session.model_dump(), ttl=config["ttl"])
            
            # Track session for user
            await self._track_user_session(user_id, session_id, config["ttl"])
            
            # Store session record in database
            await self.database.insert("user_sessions", {
                "session_id": session_id,
                "user_id": user_id,
                "session_type": session_type.value,
                "connection_id": connection_id,
                "ip_address": metadata.get("ip_address") if metadata else None,
                "user_agent": metadata.get("user_agent") if metadata else None,
                "created_at": datetime.utcnow().isoformat()
            })
            
            return session_id
            
        except Exception as e:
            raise DatabaseException(
                f"Failed to create session for user {user_id}: {str(e)}",
                correlation_id=self.correlation_id,
                details={"user_id": user_id, "session_type": session_type.value}
            )
    
    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get session data"""
        try:
            cache_key = f"session:{session_id}"
            session_data = await self.cache.get(cache_key)
            
            if session_data and session_data.get("is_active"):
                session = UserSession(**session_data)
                
                # Update last activity
                await self._update_session_activity(session_id)
                
                return session
            
            return None
            
        except Exception as e:
            raise DatabaseException(
                f"Failed to get session {session_id}: {str(e)}",
                correlation_id=self.correlation_id
            )
    
    async def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session"""
        try:
            # Get session to find user
            session = await self.get_session(session_id)
            if not session:
                return False
            
            # Mark session as inactive
            session.is_active = False
            
            # Update cache
            cache_key = f"session:{session_id}"
            await self.cache.set(cache_key, session.model_dump(), ttl=60)  # Keep for 1 minute for cleanup
            
            # Update database
            await self.database.update(
                "user_sessions",
                {
                    "is_active": False,
                    "ended_at": datetime.utcnow().isoformat()
                },
                {"session_id": session_id}
            )
            
            return True
            
        except Exception as e:
            raise DatabaseException(
                f"Failed to invalidate session {session_id}: {str(e)}",
                correlation_id=self.correlation_id
            )
    
    # User Tool Management
    
    async def get_user_available_servers(self, user_id: str) -> Dict[str, Any]:
        """Get MCP servers available to specific user using new MCP domain implementation"""
        # Check cache first
        cache_key = f"user_mcp_servers:{user_id}"
        cached_servers = await self.cache.get(cache_key)
        if cached_servers:
            return cached_servers
        
        # Use MCP domain service to get available servers
        mcp_service = MCPOperationsService(
            correlation_id=self.correlation_id
        )
        
        # Get categorized servers for the user
        servers_response = await mcp_service.get_available_servers_for_user(user_id)
        
        # Convert to dictionary format for backward compatibility
        servers_dict = servers_response.model_dump()
        
        # Cache for 5 minutes default ttl
        await self.cache.set(key=cache_key, value=servers_dict)
        
        return servers_dict
    
    async def get_user_available_tools(self, user_id: str) -> List[Dict[str, Any]]:
        """Get tools available to specific user using new MCP domain implementation"""
        # Check cache first
        cache_key = f"user_tools:{user_id}"
        cached_tools = await self.cache.get(cache_key)
        if cached_tools:
            return cached_tools
        
        # Use MCP domain service to get available tools
        mcp_service = MCPOperationsService(
            correlation_id=self.correlation_id
        )
        
        # Get tools by user
        tools_response = await mcp_service.get_tools_by_user(user_id)
        
        # Convert to list format for backward compatibility
        tools_list = [tool.model_dump() for tool in tools_response.tools]
        
        # Cache for 5 minutes default ttl
        await self.cache.set(key=cache_key, value=tools_list)
        
        return tools_list

    async def get_user_by_auth_id(self, auth_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by Auth0 ID from database.
        
        Args:
            auth_id: Auth0 user ID (sub claim)
            
        Returns:
            User data dictionary or None if not found
            
        Raises:
            DatabaseException: If database query fails
        """
        try:
            logger.debug(f"Looking up user by auth_id: {auth_id}")
            
            # Query users table by auth_id
            result = await self.database.select(
                table="users",
                columns=["id", "name", "email", "avatar_url", "auth_id", "created_at", "updated_at"],
                filters={"auth_id": auth_id},
                limit=1
            )
            
            if result.get("data") and len(result["data"]) > 0:
                user_data = result["data"][0]
                logger.debug(f"User found: {user_data.get('id')}")
                return user_data
            else:
                logger.debug(f"No user found with auth_id: {auth_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get user by auth_id {auth_id}: {str(e)}")
            raise DatabaseException(
                f"Failed to get user by auth_id {auth_id}: {str(e)}",
                correlation_id=self.correlation_id
            )
    
    async def connect_user_tool(
        self,
        user_id: str,
        tool_name: str,
        credentials: Dict[str, Any],
        scopes: List[str] = None
    ) -> bool:
        """Connect a new tool for user"""
        try:
            # Encrypt credentials (mock implementation)
            encrypted_creds = await self._encrypt_credentials(user_id, credentials)
            
            # Determine server name from tool name
            server_name = tool_name.split("_")[0] if "_" in tool_name else tool_name
            
            # Store connection
            connection_data = {
                "user_id": user_id,
                "tool_name": tool_name,
                "server_name": server_name,
                "credentials_encrypted": encrypted_creds,
                "scopes": scopes or [],
                "is_active": True,
                "connected_at": datetime.utcnow().isoformat()
            }
            
            await self.database.upsert("user_tool_connections", connection_data)
            
            # Invalidate user tools cache
            cache_key = f"user_tools:{user_id}"
            await self.cache.delete(cache_key)
            
            # Update user activity
            await self._track_tool_connection_activity(user_id, tool_name)
            
            return True
            
        except Exception as e:
            raise DatabaseException(
                f"Failed to connect tool {tool_name} for user {user_id}: {str(e)}",
                correlation_id=self.correlation_id,
                details={"user_id": user_id, "tool_name": tool_name}
            )
    
    async def validate_user_tool_access(self, user_id: str, tool_name: str) -> bool:
        """Check if user has access to specific tool"""
        try:
            user_tools = await self.get_user_available_tools(user_id)
            return any(tool["name"] == tool_name for tool in user_tools)
            
        except Exception:
            # In case of error, deny access (fail closed)
            return False
    
    async def get_user_tool_credentials(
        self, 
        user_id: str, 
        tool_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get decrypted credentials for user's tool"""
        try:
            connection_result = await self.database.select(
                "user_tool_connections",
                filters={
                    "user_id": user_id,
                    "tool_name": tool_name,
                    "is_active": True
                }
            )
            
            if connection_result.get("data"):
                connection = connection_result["data"][0]
                encrypted_creds = connection["credentials_encrypted"]
                
                # Decrypt credentials
                decrypted_creds = await self._decrypt_credentials(user_id, encrypted_creds)
                return decrypted_creds
            
            return None
            
        except Exception as e:
            raise DatabaseException(
                f"Failed to get credentials for tool {tool_name}, user {user_id}: {str(e)}",
                correlation_id=self.correlation_id
            )
    
    # User Analytics and Learning
    
    async def track_user_activity(
        self,
        user_id: str,
        activity_type: str,
        activity_data: Dict[str, Any]
    ) -> None:
        """Track user activity for learning and personalization"""
        try:
            activity_record = {
                "user_id": user_id,
                "activity_type": activity_type,
                "activity_data": activity_data,
                "timestamp": datetime.utcnow().isoformat(),
                "correlation_id": self.correlation_id
            }
            
            # Store activity
            await self.database.insert("user_activity_logs", activity_record)
            
            # Update user context with recent activity
            await self._update_recent_activity(user_id, activity_type, activity_data)
            
        except Exception:
            # Don't fail if activity tracking fails
            pass
    
    async def get_user_workflow_patterns(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's workflow patterns for personalization"""
        try:
            context = await self.get_user_context(user_id, ["workflow_patterns"])
            return context.workflow_patterns
            
        except Exception:
            return []
    
    async def update_user_workflow_pattern(
        self,
        user_id: str,
        pattern_name: str,
        pattern_data: Dict[str, Any]
    ) -> None:
        """Update user workflow pattern"""
        try:
            context = await self.get_user_context(user_id)
            patterns = context.workflow_patterns
            
            # Find existing pattern or create new one
            pattern_found = False
            for pattern in patterns:
                if pattern.get("pattern") == pattern_name:
                    # Update existing pattern
                    pattern.update(pattern_data)
                    pattern["last_updated"] = datetime.utcnow().isoformat()
                    pattern_found = True
                    break
            
            if not pattern_found:
                # Add new pattern
                new_pattern = {
                    "pattern": pattern_name,
                    **pattern_data,
                    "created_at": datetime.utcnow().isoformat(),
                    "last_updated": datetime.utcnow().isoformat()
                }
                patterns.append(new_pattern)
            
            # Update context
            await self.update_user_context(user_id, {"workflow_patterns": patterns})
            
        except Exception:
            # Don't fail if pattern update fails
            pass
    
    # Helper Methods
    
    async def _load_context_from_database(
        self, 
        user_id: str, 
        context_keys: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Load user context from database"""
        try:
            result = await self.database.select(
                "user_contexts",
                filters={"user_id": user_id}
            )
            
            if result.get("data"):
                context_data = result["data"][0]["context_data"]
                
                # Filter to specific keys if requested
                if context_keys:
                    filtered_data = {}
                    for key in context_keys:
                        if key in context_data:
                            filtered_data[key] = context_data[key]
                    return filtered_data
                
                return context_data
            
            return None
            
        except Exception:
            return None
    
    async def _create_default_user_context(self, user_id: str) -> UserContext:
        """Create default user context"""
        default_context = UserContext(
            user_id=user_id,
            preferences=UserPreferences(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Save to database
        await self.database.insert("user_contexts", {
            "user_id": user_id,
            "context_data": default_context.model_dump(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        return default_context
    
    def _filter_context_keys(self, context: UserContext, keys: List[str]) -> UserContext:
        """Filter context to specific keys"""
        context_dict = context.model_dump()
        filtered_dict = {k: v for k, v in context_dict.items() if k in keys}
        # Ensure required fields are present
        filtered_dict.update({
            "user_id": context.user_id,
            "created_at": context.created_at,
            "updated_at": context.updated_at
        })
        return UserContext(**filtered_dict)
    
    def _deep_merge_dict(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = base.copy()
        
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge_dict(result[key], value)
            else:
                result[key] = value
        
        return result
    
    async def _update_session_activity(self, session_id: str) -> None:
        """Update session last activity timestamp"""
        try:
            cache_key = f"session:{session_id}"
            session_data = await self.cache.get(cache_key)
            
            if session_data:
                session_data["last_activity"] = datetime.utcnow().isoformat()
                
                # Extend TTL based on session type
                session_type = SessionType(session_data["session_type"])
                config = self.session_configs[session_type]
                
                if config["auto_extend"]:
                    await self.cache.set(cache_key, session_data, ttl=config["ttl"] // 2)
                else:
                    await self.cache.set(cache_key, session_data)
                    
        except Exception:
            pass
    
    async def _track_user_session(self, user_id: str, session_id: str, ttl: int) -> None:
        """Track session for user"""
        try:
            user_sessions_key = f"user_sessions:{user_id}"
            user_sessions = await self.cache.get(user_sessions_key) or []
            
            # Add new session and keep only last 5
            user_sessions.append(session_id)
            user_sessions = user_sessions[-5:]
            
            await self.cache.set(user_sessions_key, user_sessions, ttl=ttl)
            
        except Exception:
            pass
    
    async def _encrypt_credentials(self, user_id: str, credentials: Dict[str, Any]) -> str:
        """Encrypt user credentials (mock implementation)"""
        import json
        import base64
        
        # In real implementation, use proper encryption
        creds_json = json.dumps(credentials)
        encoded = base64.b64encode(creds_json.encode()).decode()
        return f"encrypted_{user_id}_{encoded}"
    
    async def _decrypt_credentials(self, user_id: str, encrypted_creds: str) -> Dict[str, Any]:
        """Decrypt user credentials (mock implementation)"""
        import json
        import base64
        
        # In real implementation, use proper decryption
        if encrypted_creds.startswith(f"encrypted_{user_id}_"):
            encoded = encrypted_creds.replace(f"encrypted_{user_id}_", "")
            decoded = base64.b64decode(encoded).decode()
            return json.loads(decoded)
        
        return {}
    
    async def _track_tool_connection_activity(self, user_id: str, tool_name: str) -> None:
        """Track tool connection activity"""
        await self.track_user_activity(user_id, "tool_connected", {
            "tool_name": tool_name,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _update_recent_activity(
        self, 
        user_id: str, 
        activity_type: str, 
        activity_data: Dict[str, Any]
    ) -> None:
        """Update user's recent activity in context"""
        try:
            context = await self.get_user_context(user_id)
            recent_activity = context.recent_activity
            
            # Update specific activity counters
            if activity_type == "workflow_created":
                recent_activity["last_workflow_created"] = datetime.utcnow().isoformat()
                recent_activity["total_workflows"] = recent_activity.get("total_workflows", 0) + 1
            elif activity_type == "workflow_executed":
                recent_activity["last_workflow_executed"] = datetime.utcnow().isoformat()
                recent_activity["total_executions"] = recent_activity.get("total_executions", 0) + 1
            elif activity_type == "tool_connected":
                recent_activity["last_tool_connected"] = datetime.utcnow().isoformat()
            
            # Update context
            await self.update_user_context(user_id, {"recent_activity": recent_activity})
            
        except Exception:
            pass 