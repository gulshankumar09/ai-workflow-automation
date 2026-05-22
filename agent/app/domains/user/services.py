"""
User Domain Services

Core business logic services for user management, session handling,
context management, and tool connections. These services implement
the business rules and coordinate between entities and repositories.
"""

import asyncio
import structlog
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import base64
import json

from .entities import (
    User, UserContext, UserSession, UserToolConnection, 
    SessionType, UserRole, UserPreferences
)
from .repositories import (
    UserRepository, UserContextRepository, 
    UserSessionRepository, UserToolConnectionRepository,
    SessionPersistenceRepository, ChatHistoryRepository
)
from app.shared.exceptions import (
    NotFoundException, ValidationException, AuthenticationException,
    AuthorizationException, DatabaseException
)
from app.infrastructure.cache.factory import CacheProviderFactory

logger = get_logger(__name__)


class UserService:
    """Core user management service"""
    
    def __init__(
        self,
        user_repo: UserRepository,
        context_repo: UserContextRepository,
        cache_provider=None
    ):
        self.user_repo = user_repo
        self.context_repo = context_repo
        self.cache = cache_provider or CacheProviderFactory.create_provider("memory")
        self.cache_ttl = 1800  # 30 minutes
    
    async def create_user(self, email: str, role: UserRole = UserRole.USER) -> User:
        """
        Create a new user
        
        Args:
            email: User email address
            role: User role
            
        Returns:
            Created user entity
            
        Raises:
            ValidationException: If email is invalid or already exists
            DatabaseException: If creation fails
        """
        try:
            # Check if user already exists
            existing_user = await self.user_repo.find_by_email(email)
            if existing_user:
                raise ValidationException(
                    f"User with email {email} already exists",
                    details={"email": email}
                )
            
            # Create new user
            user = User.create_new(email, role)
            user_id = await self.user_repo.save(user)
            user.id = user_id
            
            # Create user context
            await self.context_repo.save(user.context)
            
            # Cache user data
            await self._cache_user(user)
            
            logger.info("Created new user", user_id=user.id, email=email)
            return user
            
        except Exception as e:
            logger.error("Failed to create user", email=email, error=str(e))
            raise
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """
        Get user by ID with caching
        
        Args:
            user_id: User identifier
            
        Returns:
            User entity or None if not found
        """
        try:
            # Check cache first
            cache_key = f"user:{user_id}"
            cached_user = await self.cache.get(cache_key)
            if cached_user:
                return User(**cached_user)
            
            # Load from repository
            user = await self.user_repo.find_by_id(user_id)
            if user:
                # Load context
                context = await self.context_repo.find_by_user_id(user_id)
                if context:
                    user.context = context
                
                # Cache user
                await self._cache_user(user)
            
            return user
            
        except Exception as e:
            logger.error("Failed to get user", user_id=user_id, error=str(e))
            raise
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address
        
        Args:
            email: User email address
            
        Returns:
            User entity or None if not found
        """
        try:
            user = await self.user_repo.find_by_email(email)
            if user:
                # Load context
                context = await self.context_repo.find_by_user_id(user.id)
                if context:
                    user.context = context
            
            return user
            
        except Exception as e:
            logger.error("Failed to get user by email", email=email, error=str(e))
            raise
    
    async def update_user(self, user: User) -> bool:
        """
        Update user entity
        
        Args:
            user: User entity with updates
            
        Returns:
            True if update was successful
        """
        try:
            # Update in repository
            success = await self.user_repo.update(user)
            
            if success:
                # Update context if present
                if user.context:
                    await self.context_repo.save(user.context)
                
                # Update cache
                await self._cache_user(user)
                
                logger.info("Updated user", user_id=user.id)
            
            return success
            
        except Exception as e:
            logger.error("Failed to update user", user_id=user.id, error=str(e))
            raise
    
    async def authenticate_user(self, email: str) -> User:
        """
        Authenticate user by email
        
        Args:
            email: User email address
            
        Returns:
            Authenticated user entity
            
        Raises:
            AuthenticationException: If user not found or inactive
        """
        try:
            user = await self.get_user_by_email(email)
            if not user:
                raise AuthenticationException(
                    "User not found",
                    details={"email": email}
                )
            
            if not user.is_active:
                raise AuthenticationException(
                    "User account is inactive",
                    details={"email": email, "user_id": user.id}
                )
            
            # Update login timestamp
            user.update_login()
            await self.update_user(user)
            
            return user
            
        except Exception as e:
            logger.error("Authentication failed", email=email, error=str(e))
            raise
    
    async def deactivate_user(self, user_id: str) -> bool:
        """
        Deactivate user account
        
        Args:
            user_id: User identifier
            
        Returns:
            True if deactivation was successful
        """
        try:
            user = await self.get_user(user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")
            
            user.deactivate()
            success = await self.update_user(user)
            
            if success:
                # Clear user from cache
                await self.cache.delete(f"user:{user_id}")
                logger.info("Deactivated user", user_id=user_id)
            
            return success
            
        except Exception as e:
            logger.error("Failed to deactivate user", user_id=user_id, error=str(e))
            raise
    
    async def _cache_user(self, user: User) -> None:
        """Cache user data"""
        try:
            cache_key = f"user:{user.id}"
            user_dict = {
                "id": user.id,
                "email": user.email,
                "role": user.role.value,
                "is_active": user.is_active,
                "timezone": user.timezone,
                "locale": user.locale,
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None
            }
            await self.cache.set(cache_key, user_dict, ttl=self.cache_ttl)
        except Exception as e:
            logger.warning("Failed to cache user", user_id=user.id, error=str(e))


class UserContextService:
    """Service for managing user context and preferences"""
    
    def __init__(
        self,
        context_repo: UserContextRepository,
        cache_provider=None
    ):
        self.context_repo = context_repo
        self.cache = cache_provider or CacheProviderFactory.create_provider("memory")
        self.cache_ttl = 1800  # 30 minutes
    
    async def get_user_context(self, user_id: str) -> Optional[UserContext]:
        """
        Get user context with caching
        
        Args:
            user_id: User identifier
            
        Returns:
            UserContext entity or None if not found
        """
        try:
            # Check cache first
            cache_key = f"user_context:{user_id}"
            cached_context = await self.cache.get(cache_key)
            if cached_context:
                return self._deserialize_context(cached_context)
            
            # Load from repository
            context = await self.context_repo.find_by_user_id(user_id)
            if context:
                await self._cache_context(context)
            
            return context
            
        except Exception as e:
            logger.error("Failed to get user context", user_id=user_id, error=str(e))
            raise
    
    async def update_preferences(
        self, 
        user_id: str, 
        category: str, 
        preferences: Dict[str, Any]
    ) -> bool:
        """
        Update user preferences
        
        Args:
            user_id: User identifier
            category: Preference category
            preferences: Preference updates
            
        Returns:
            True if update was successful
        """
        try:
            context = await self.get_user_context(user_id)
            if not context:
                # Create new context
                context = UserContext(user_id=user_id)
                await self.context_repo.save(context)
            
            # Update preferences
            for key, value in preferences.items():
                context.preferences.update_preference(category, key, value)
            
            context.updated_at = datetime.utcnow()
            
            # Save to repository
            success = await self.context_repo.save(context)
            
            if success:
                # Update cache
                await self._cache_context(context)
                logger.info("Updated user preferences", user_id=user_id, category=category)
            
            return success
            
        except Exception as e:
            logger.error("Failed to update preferences", user_id=user_id, error=str(e))
            raise
    
    async def record_workflow_pattern(
        self,
        user_id: str,
        pattern_name: str,
        success: bool,
        parameters: Dict[str, Any] = None
    ) -> bool:
        """
        Record workflow pattern usage
        
        Args:
            user_id: User identifier
            pattern_name: Pattern name
            success: Whether execution was successful
            parameters: Workflow parameters
            
        Returns:
            True if recording was successful
        """
        try:
            context = await self.get_user_context(user_id)
            if not context:
                context = UserContext(user_id=user_id)
            
            # Add or update pattern
            pattern = context.add_workflow_pattern(pattern_name, parameters)
            pattern.record_usage(success, parameters)
            
            # Save context
            success = await self.context_repo.save(context)
            
            if success:
                await self._cache_context(context)
                logger.info("Recorded workflow pattern", 
                          user_id=user_id, pattern=pattern_name)
            
            return success
            
        except Exception as e:
            logger.error("Failed to record workflow pattern", 
                        user_id=user_id, pattern=pattern_name, error=str(e))
            raise
    
    async def record_tool_usage(
        self,
        user_id: str,
        tool_name: str,
        success: bool,
        execution_time: float,
        error_message: str = None
    ) -> bool:
        """
        Record tool usage statistics
        
        Args:
            user_id: User identifier
            tool_name: Tool name
            success: Whether execution was successful
            execution_time: Execution time in seconds
            error_message: Error message if failed
            
        Returns:
            True if recording was successful
        """
        try:
            context = await self.get_user_context(user_id)
            if not context:
                context = UserContext(user_id=user_id)
            
            # Record tool usage
            context.record_tool_usage(tool_name, success, execution_time, error_message)
            
            # Save context
            success = await self.context_repo.save(context)
            
            if success:
                await self._cache_context(context)
                logger.info("Recorded tool usage", 
                          user_id=user_id, tool=tool_name, success=success)
            
            return success
            
        except Exception as e:
            logger.error("Failed to record tool usage", 
                        user_id=user_id, tool=tool_name, error=str(e))
            raise
    
    async def get_workflow_recommendations(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get workflow recommendations based on user patterns
        
        Args:
            user_id: User identifier
            
        Returns:
            List of workflow recommendations
        """
        try:
            context = await self.get_user_context(user_id)
            if not context:
                return []
            
            return context.get_workflow_recommendations()
            
        except Exception as e:
            logger.error("Failed to get recommendations", user_id=user_id, error=str(e))
            return []
    
    async def _cache_context(self, context: UserContext) -> None:
        """Cache user context"""
        try:
            cache_key = f"user_context:{context.user_id}"
            context_dict = self._serialize_context(context)
            await self.cache.set(cache_key, context_dict, ttl=self.cache_ttl)
        except Exception as e:
            logger.warning("Failed to cache context", user_id=context.user_id, error=str(e))
    
    def _serialize_context(self, context: UserContext) -> Dict[str, Any]:
        """Serialize context for caching"""
        return {
            "user_id": context.user_id,
            "preferences": {
                "default_tools": context.preferences.default_tools,
                "workflow_settings": context.preferences.workflow_settings,
                "notification_preferences": context.preferences.notification_preferences,
                "ui_preferences": context.preferences.ui_preferences,
                "privacy_settings": context.preferences.privacy_settings
            },
            "workflow_patterns": {
                name: {
                    "pattern_name": pattern.pattern_name,
                    "frequency": pattern.frequency,
                    "success_rate": pattern.success_rate,
                    "common_parameters": pattern.common_parameters,
                    "last_used": pattern.last_used.isoformat() if pattern.last_used else None,
                    "created_at": pattern.created_at.isoformat()
                }
                for name, pattern in context.workflow_patterns.items()
            },
            "tool_usage_stats": {
                name: {
                    "tool_name": usage.tool_name,
                    "total_uses": usage.total_uses,
                    "success_rate": usage.success_rate,
                    "avg_execution_time": usage.avg_execution_time,
                    "last_used": usage.last_used.isoformat() if usage.last_used else None,
                    "error_patterns": usage.error_patterns
                }
                for name, usage in context.tool_usage_stats.items()
            },
            "recent_activity": context.recent_activity,
            "personalization": context.personalization,
            "created_at": context.created_at.isoformat(),
            "updated_at": context.updated_at.isoformat()
        }
    
    def _deserialize_context(self, data: Dict[str, Any]) -> UserContext:
        """Deserialize context from cache"""
        # This is a simplified deserialization
        # In practice, you'd want more robust handling
        context = UserContext(user_id=data["user_id"])
        
        # Restore preferences
        prefs_data = data.get("preferences", {})
        context.preferences.default_tools = prefs_data.get("default_tools", {})
        context.preferences.workflow_settings = prefs_data.get("workflow_settings", {})
        context.preferences.notification_preferences = prefs_data.get("notification_preferences", {})
        context.preferences.ui_preferences = prefs_data.get("ui_preferences", {})
        context.preferences.privacy_settings = prefs_data.get("privacy_settings", {})
        
        # Note: Full deserialization of workflow patterns and tool usage
        # would require more complex logic. For now, this provides the
        # basic structure.
        
        return context


class SessionService:
    """Service for managing user sessions with persistence and recovery"""
    
    def __init__(
        self,
        session_repo: UserSessionRepository,
        persistence_repo: SessionPersistenceRepository,
        cache_provider=None
    ):
        self.session_repo = session_repo
        self.persistence_repo = persistence_repo
        self.cache = cache_provider or CacheProviderFactory.create_provider("memory")
        self.session_configs = {
            SessionType.ANONYMOUS: {"ttl": 900, "auto_extend": False},      # 15 minutes
            SessionType.AUTHENTICATED: {"ttl": 3600, "auto_extend": True},   # 60 minutes
            SessionType.WEBSOCKET: {"ttl": 14400, "auto_extend": True},     # 4 hours max
            SessionType.EXECUTION: {"ttl": 7200, "auto_extend": True}       # 2 hours max
        }
    
    async def create_session(
        self,
        user_id: str,
        session_type: SessionType,
        connection_id: str = None,
        ip_address: str = None,
        user_agent: str = None
    ) -> UserSession:
        """
        Create a new user session
        
        Args:
            user_id: User identifier
            session_type: Type of session
            connection_id: Connection identifier for WebSocket sessions
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            Created session entity
        """
        try:
            config = self.session_configs[session_type]
            
            session = UserSession.create_new(
                user_id=user_id,
                session_type=session_type,
                connection_id=connection_id,
                ttl_seconds=config["ttl"]
            )
            
            session.ip_address = ip_address
            session.user_agent = user_agent
            
            # Save session
            session_id = await self.session_repo.save(session)
            session.session_id = session_id
            
            # Cache session
            await self._cache_session(session)
            
            logger.info("Created session", 
                       session_id=session.session_id, 
                       user_id=user_id, 
                       type=session_type.value)
            
            return session
            
        except Exception as e:
            logger.error("Failed to create session", 
                        user_id=user_id, 
                        session_type=session_type.value, 
                        error=str(e))
            raise
    
    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """
        Get session by ID
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session entity or None if not found/expired
        """
        try:
            # Check cache first
            cache_key = f"session:{session_id}"
            cached_session = await self.cache.get(cache_key)
            if cached_session:
                session = self._deserialize_session(cached_session)
                if not session.is_expired():
                    return session
                else:
                    # Remove expired session from cache
                    await self.cache.delete(cache_key)
            
            # Load from repository
            session = await self.session_repo.find_by_session_id(session_id)
            if session and not session.is_expired() and session.is_active:
                await self._cache_session(session)
                return session
            
            return None
            
        except Exception as e:
            logger.error("Failed to get session", session_id=session_id, error=str(e))
            raise
    
    async def update_session_activity(self, session_id: str) -> bool:
        """
        Update session activity and extend if configured
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if update was successful
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False
            
            session.update_activity()
            
            # Auto-extend if configured
            config = self.session_configs[session.session_type]
            if config["auto_extend"]:
                session.extend_session(config["ttl"] // 2)
            
            # Update in repository
            success = await self.session_repo.update_activity(session_id)
            
            if success:
                await self._cache_session(session)
            
            return success
            
        except Exception as e:
            logger.error("Failed to update session activity", 
                        session_id=session_id, error=str(e))
            raise
    
    async def close_session(self, session_id: str) -> bool:
        """
        Close session
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was closed
        """
        try:
            success = await self.session_repo.close_session(session_id)
            
            if success:
                # Remove from cache
                await self.cache.delete(f"session:{session_id}")
                logger.info("Closed session", session_id=session_id)
            
            return success
            
        except Exception as e:
            logger.error("Failed to close session", session_id=session_id, error=str(e))
            raise
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions
        
        Returns:
            Number of sessions cleaned up
        """
        try:
            count = await self.session_repo.cleanup_expired_sessions()
            # Also cleanup old session states
            state_count = await self.persistence_repo.cleanup_old_session_states(hours=24)
            logger.info("Cleaned up expired sessions", 
                       session_count=count, 
                       state_count=state_count)
            return count
            
        except Exception as e:
            logger.error("Failed to cleanup expired sessions", error=str(e))
            raise

    async def save_session_state(self, session_id: str, state_data: Dict[str, Any]) -> bool:
        """
        Save session state for recovery
        
        Args:
            session_id: Session identifier
            state_data: State data to persist
            
        Returns:
            True if save was successful
        """
        try:
            success = await self.persistence_repo.save_session_state(session_id, state_data)
            if success:
                logger.info("Saved session state", session_id=session_id)
            return success
            
        except Exception as e:
            logger.error("Failed to save session state", 
                        session_id=session_id, error=str(e))
            raise

    async def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get saved session state
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session state data or None if not found
        """
        try:
            state_data = await self.persistence_repo.get_session_state(session_id)
            return state_data
            
        except Exception as e:
            logger.error("Failed to get session state", 
                        session_id=session_id, error=str(e))
            raise

    async def find_recoverable_sessions(self, user_id: str, hours: int = 1) -> List[Dict[str, Any]]:
        """
        Find sessions that can be recovered for the user
        
        Args:
            user_id: User identifier
            hours: Hours back to look for recoverable sessions
            
        Returns:
            List of recoverable session data
        """
        try:
            recoverable = await self.persistence_repo.find_recoverable_sessions(user_id, hours)
            logger.info("Found recoverable sessions", 
                       user_id=user_id, 
                       count=len(recoverable))
            return recoverable
            
        except Exception as e:
            logger.error("Failed to find recoverable sessions", 
                        user_id=user_id, error=str(e))
            raise

    async def recover_session(self, user_id: str, old_session_id: str) -> Optional[UserSession]:
        """
        Recover session from saved state
        
        Args:
            user_id: User identifier
            old_session_id: Previous session ID to recover from
            
        Returns:
            New session with recovered state or None if recovery failed
        """
        try:
            # Get saved state
            saved_state = await self.get_session_state(old_session_id)
            if not saved_state:
                return None
            
            # Create new session
            session_type = SessionType(saved_state.get("session_type", "authenticated"))
            new_session = await self.create_session(
                user_id=user_id,
                session_type=session_type,
                connection_id=saved_state.get("connection_id")
            )
            
            # Restore context from saved state
            if "context" in saved_state:
                await self.save_session_state(new_session.session_id, {
                    "context": saved_state["context"],
                    "recovered_from": old_session_id,
                    "recovery_time": datetime.utcnow().isoformat()
                })
            
            logger.info("Recovered session", 
                       user_id=user_id, 
                       old_session_id=old_session_id, 
                       new_session_id=new_session.session_id)
            
            return new_session
            
        except Exception as e:
            logger.error("Failed to recover session", 
                        user_id=user_id, 
                        old_session_id=old_session_id, 
                        error=str(e))
            raise
    
    async def _cache_session(self, session: UserSession) -> None:
        """Cache session data"""
        try:
            cache_key = f"session:{session.session_id}"
            session_dict = self._serialize_session(session)
            
            # Calculate TTL based on session expiry
            if session.expires_at:
                ttl = int((session.expires_at - datetime.utcnow()).total_seconds())
                ttl = max(ttl, 60)  # Minimum 1 minute
            else:
                ttl = 3600  # Default 1 hour
            
            await self.cache.set(cache_key, session_dict, ttl=ttl)
        except Exception as e:
            logger.warning("Failed to cache session", 
                          session_id=session.session_id, error=str(e))
    
    def _serialize_session(self, session: UserSession) -> Dict[str, Any]:
        """Serialize session for caching"""
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "session_type": session.session_type.value,
            "connection_id": session.connection_id,
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
            "is_active": session.is_active,
            "context_snapshot": session.context_snapshot,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "expires_at": session.expires_at.isoformat() if session.expires_at else None
        }
    
    def _deserialize_session(self, data: Dict[str, Any]) -> UserSession:
        """Deserialize session from cache"""
        session = UserSession(
            session_id=data["session_id"],
            user_id=data["user_id"],
            session_type=SessionType(data["session_type"]),
            connection_id=data.get("connection_id"),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            is_active=data["is_active"],
            context_snapshot=data.get("context_snapshot", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
        )
        return session


class UserToolService:
    """Service for managing user tool connections"""
    
    def __init__(
        self,
        tool_connection_repo: UserToolConnectionRepository,
        cache_provider=None
    ):
        self.tool_connection_repo = tool_connection_repo
        self.cache = cache_provider or CacheProviderFactory.create_provider("memory")
        self.cache_ttl = 600  # 10 minutes
        # In production, this should be loaded from secure configuration
        self.encryption_key = Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
    
    async def connect_user_tool(
        self,
        user_id: str,
        tool_name: str,
        server_name: str,
        credentials: Dict[str, Any],
        scopes: List[str] = None
    ) -> bool:
        """
        Connect a tool for a user
        
        Args:
            user_id: User identifier
            tool_name: Tool name
            server_name: MCP server name
            credentials: Tool credentials
            scopes: Access scopes
            
        Returns:
            True if connection was successful
        """
        try:
            # Encrypt credentials
            encrypted_creds = await self._encrypt_credentials(credentials)
            
            # Create connection entity
            connection = UserToolConnection(
                user_id=user_id,
                tool_name=tool_name,
                server_name=server_name,
                credentials_encrypted=encrypted_creds,
                scopes=scopes or []
            )
            
            # Save connection
            success = await self.tool_connection_repo.save(connection)
            
            if success:
                # Clear user tools cache
                await self.cache.delete(f"user_tools:{user_id}")
                logger.info("Connected user tool", 
                          user_id=user_id, tool_name=tool_name)
            
            return success
            
        except Exception as e:
            logger.error("Failed to connect user tool", 
                        user_id=user_id, tool_name=tool_name, error=str(e))
            raise
    
    async def get_user_available_tools(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get tools available to user
        
        Args:
            user_id: User identifier
            
        Returns:
            List of available tool information
        """
        try:
            # Check cache first
            cache_key = f"user_tools:{user_id}"
            cached_tools = await self.cache.get(cache_key)
            if cached_tools:
                return cached_tools
            
            # Load from repository
            tools = await self.tool_connection_repo.get_user_available_tools(user_id)
            
            if tools:
                # Cache tools
                await self.cache.set(cache_key, tools, ttl=self.cache_ttl)
            
            return tools
            
        except Exception as e:
            logger.error("Failed to get user tools", user_id=user_id, error=str(e))
            raise
    
    async def get_user_tool_credentials(
        self, 
        user_id: str, 
        tool_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get decrypted credentials for user tool
        
        Args:
            user_id: User identifier
            tool_name: Tool name
            
        Returns:
            Decrypted credentials or None if not found
        """
        try:
            connection = await self.tool_connection_repo.find_by_user_and_tool(
                user_id, tool_name
            )
            
            if not connection or not connection.is_active:
                return None
            
            # Decrypt credentials
            credentials = await self._decrypt_credentials(connection.credentials_encrypted)
            
            # Update usage
            await self.tool_connection_repo.update_usage(user_id, tool_name)
            
            return credentials
            
        except Exception as e:
            logger.error("Failed to get tool credentials", 
                        user_id=user_id, tool_name=tool_name, error=str(e))
            raise
    
    async def validate_user_tool_access(self, user_id: str, tool_name: str) -> bool:
        """
        Check if user has access to specific tool
        
        Args:
            user_id: User identifier
            tool_name: Tool name
            
        Returns:
            True if user has access
        """
        try:
            connection = await self.tool_connection_repo.find_by_user_and_tool(
                user_id, tool_name
            )
            
            return connection is not None and connection.is_active
            
        except Exception as e:
            logger.error("Failed to validate tool access", 
                        user_id=user_id, tool_name=tool_name, error=str(e))
            return False
    
    async def deactivate_tool_connection(self, user_id: str, tool_name: str) -> bool:
        """
        Deactivate tool connection
        
        Args:
            user_id: User identifier
            tool_name: Tool name
            
        Returns:
            True if deactivation was successful
        """
        try:
            success = await self.tool_connection_repo.deactivate_connection(
                user_id, tool_name
            )
            
            if success:
                # Clear user tools cache
                await self.cache.delete(f"user_tools:{user_id}")
                logger.info("Deactivated tool connection", 
                          user_id=user_id, tool_name=tool_name)
            
            return success
            
        except Exception as e:
            logger.error("Failed to deactivate tool connection", 
                        user_id=user_id, tool_name=tool_name, error=str(e))
            raise
    
    async def _encrypt_credentials(self, credentials: Dict[str, Any]) -> str:
        """Encrypt credentials"""
        try:
            credentials_json = json.dumps(credentials)
            encrypted_data = self.cipher.encrypt(credentials_json.encode())
            return base64.b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error("Failed to encrypt credentials", error=str(e))
            raise
    
    async def _decrypt_credentials(self, encrypted_credentials: str) -> Dict[str, Any]:
        """Decrypt credentials"""
        try:
            encrypted_data = base64.b64decode(encrypted_credentials.encode())
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error("Failed to decrypt credentials", error=str(e))
            raise


class ChatHistoryService:
    """Service for managing chat history persistence and recovery"""
    
    def __init__(
        self,
        chat_history_repo: ChatHistoryRepository,
        cache_provider=None
    ):
        self.chat_history_repo = chat_history_repo
        self.cache = cache_provider or CacheProviderFactory.create_provider("memory")
    
    async def save_chat_history(self, user_id: str, chat_history: Dict[str, Any]) -> bool:
        """
        Save complete chat history for user
        
        Args:
            user_id: User identifier
            chat_history: Chat history data to save
            
        Returns:
            True if save was successful
        """
        try:
            success = await self.chat_history_repo.save_chat_history(user_id, chat_history)
            if success:
                # Update cache
                cache_key = f"chat_history:{user_id}"
                await self.cache.set(cache_key, chat_history, ttl=1800)  # 30 minutes
                logger.info("Saved chat history", user_id=user_id)
            return success
            
        except Exception as e:
            logger.error("Failed to save chat history", user_id=user_id, error=str(e))
            raise
    
    async def get_chat_history(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user's chat history with caching
        
        Args:
            user_id: User identifier
            
        Returns:
            Chat history data or None if not found
        """
        try:
            # Check cache first
            cache_key = f"chat_history:{user_id}"
            cached_history = await self.cache.get(cache_key)
            if cached_history:
                return cached_history
            
            # Load from repository
            chat_history = await self.chat_history_repo.get_chat_history(user_id)
            if chat_history:
                # Cache for future access
                await self.cache.set(cache_key, chat_history, ttl=1800)
            
            return chat_history
            
        except Exception as e:
            logger.error("Failed to get chat history", user_id=user_id, error=str(e))
            raise
    
    async def save_chat_session(self, user_id: str, session_id: str, session_data: Dict[str, Any]) -> bool:
        """
        Save individual chat session
        
        Args:
            user_id: User identifier
            session_id: Chat session identifier
            session_data: Chat session data
            
        Returns:
            True if save was successful
        """
        try:
            success = await self.chat_history_repo.save_chat_session(user_id, session_id, session_data)
            if success:
                # Invalidate user's chat history cache
                cache_key = f"chat_history:{user_id}"
                await self.cache.delete(cache_key)
                logger.info("Saved chat session", user_id=user_id, session_id=session_id)
            return success
            
        except Exception as e:
            logger.error("Failed to save chat session", 
                        user_id=user_id, session_id=session_id, error=str(e))
            raise
    
    async def get_chat_session(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get individual chat session
        
        Args:
            user_id: User identifier
            session_id: Chat session identifier
            
        Returns:
            Chat session data or None if not found
        """
        try:
            session_data = await self.chat_history_repo.get_chat_session(user_id, session_id)
            return session_data
            
        except Exception as e:
            logger.error("Failed to get chat session", 
                        user_id=user_id, session_id=session_id, error=str(e))
            raise
    
    async def update_active_session(self, user_id: str, session_id: str) -> bool:
        """
        Update user's active chat session
        
        Args:
            user_id: User identifier
            session_id: Session to mark as active
            
        Returns:
            True if update was successful
        """
        try:
            success = await self.chat_history_repo.update_active_session(user_id, session_id)
            if success:
                # Invalidate cache to ensure fresh data
                cache_key = f"chat_history:{user_id}"
                await self.cache.delete(cache_key)
                logger.info("Updated active chat session", user_id=user_id, session_id=session_id)
            return success
            
        except Exception as e:
            logger.error("Failed to update active session", 
                        user_id=user_id, session_id=session_id, error=str(e))
            raise
    
    async def cleanup_old_chat_sessions(self, user_id: str, days: int = 30) -> int:
        """
        Remove old chat sessions for user
        
        Args:
            user_id: User identifier
            days: Age threshold in days
            
        Returns:
            Number of cleaned up sessions
        """
        try:
            count = await self.chat_history_repo.cleanup_old_chat_sessions(user_id, days)
            if count > 0:
                # Invalidate cache after cleanup
                cache_key = f"chat_history:{user_id}"
                await self.cache.delete(cache_key)
                logger.info("Cleaned up old chat sessions", user_id=user_id, count=count)
            return count
            
        except Exception as e:
            logger.error("Failed to cleanup old chat sessions", 
                        user_id=user_id, error=str(e))
            raise 