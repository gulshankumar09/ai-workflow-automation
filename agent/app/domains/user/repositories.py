"""
User Domain Repositories

Repository interfaces for user-related data access following the Repository pattern.
These abstract base classes define the contract for data persistence without
coupling to specific storage implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime

from .entities import User, UserContext, UserSession, UserToolConnection, SessionType
from app.shared.exceptions import NotFoundException, DatabaseException


class UserRepository(ABC):
    """Repository interface for User entities"""
    
    @abstractmethod
    async def save(self, user: User) -> str:
        """
        Save a user entity
        
        Args:
            user: User entity to save
            
        Returns:
            User ID
            
        Raises:
            DatabaseException: If save operation fails
        """
        pass
    
    @abstractmethod
    async def find_by_id(self, user_id: str) -> Optional[User]:
        """
        Find user by ID
        
        Args:
            user_id: User identifier
            
        Returns:
            User entity or None if not found
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[User]:
        """
        Find user by email address
        
        Args:
            email: User email address
            
        Returns:
            User entity or None if not found
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def find_active_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """
        Find active users with pagination
        
        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip
            
        Returns:
            List of active user entities
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def update(self, user: User) -> bool:
        """
        Update existing user
        
        Args:
            user: User entity with updated data
            
        Returns:
            True if update was successful
            
        Raises:
            NotFoundException: If user doesn't exist
            DatabaseException: If update fails
        """
        pass
    
    @abstractmethod
    async def delete(self, user_id: str) -> bool:
        """
        Delete user by ID
        
        Args:
            user_id: User identifier
            
        Returns:
            True if deletion was successful
            
        Raises:
            NotFoundException: If user doesn't exist
            DatabaseException: If deletion fails
        """
        pass
    
    @abstractmethod
    async def exists(self, user_id: str) -> bool:
        """
        Check if user exists
        
        Args:
            user_id: User identifier
            
        Returns:
            True if user exists
            
        Raises:
            DatabaseException: If query fails
        """
        pass


class UserContextRepository(ABC):
    """Repository interface for UserContext entities"""
    
    @abstractmethod
    async def save(self, context: UserContext) -> bool:
        """
        Save user context
        
        Args:
            context: UserContext entity to save
            
        Returns:
            True if save was successful
            
        Raises:
            DatabaseException: If save operation fails
        """
        pass
    
    @abstractmethod
    async def find_by_user_id(self, user_id: str) -> Optional[UserContext]:
        """
        Find user context by user ID
        
        Args:
            user_id: User identifier
            
        Returns:
            UserContext entity or None if not found
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def update_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """
        Update user preferences
        
        Args:
            user_id: User identifier
            preferences: Preferences data to update
            
        Returns:
            True if update was successful
            
        Raises:
            NotFoundException: If user context doesn't exist
            DatabaseException: If update fails
        """
        pass
    
    @abstractmethod
    async def update_workflow_patterns(self, user_id: str, patterns: Dict[str, Any]) -> bool:
        """
        Update user workflow patterns
        
        Args:
            user_id: User identifier
            patterns: Workflow patterns data
            
        Returns:
            True if update was successful
            
        Raises:
            NotFoundException: If user context doesn't exist
            DatabaseException: If update fails
        """
        pass
    
    @abstractmethod
    async def update_tool_usage(self, user_id: str, tool_usage: Dict[str, Any]) -> bool:
        """
        Update user tool usage statistics
        
        Args:
            user_id: User identifier
            tool_usage: Tool usage statistics
            
        Returns:
            True if update was successful
            
        Raises:
            NotFoundException: If user context doesn't exist
            DatabaseException: If update fails
        """
        pass
    
    @abstractmethod
    async def get_workflow_patterns(self, user_id: str) -> Dict[str, Any]:
        """
        Get user workflow patterns
        
        Args:
            user_id: User identifier
            
        Returns:
            Workflow patterns data
            
        Raises:
            NotFoundException: If user context doesn't exist
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def get_tool_usage_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get user tool usage statistics
        
        Args:
            user_id: User identifier
            
        Returns:
            Tool usage statistics
            
        Raises:
            NotFoundException: If user context doesn't exist
            DatabaseException: If query fails
        """
        pass


class UserSessionRepository(ABC):
    """Repository interface for UserSession entities"""
    
    @abstractmethod
    async def save(self, session: UserSession) -> str:
        """
        Save user session
        
        Args:
            session: UserSession entity to save
            
        Returns:
            Session ID
            
        Raises:
            DatabaseException: If save operation fails
        """
        pass
    
    @abstractmethod
    async def find_by_session_id(self, session_id: str) -> Optional[UserSession]:
        """
        Find session by session ID
        
        Args:
            session_id: Session identifier
            
        Returns:
            UserSession entity or None if not found
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def find_active_sessions_by_user(self, user_id: str) -> List[UserSession]:
        """
        Find active sessions for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            List of active UserSession entities
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def find_by_connection_id(self, connection_id: str) -> Optional[UserSession]:
        """
        Find session by connection ID (for WebSocket sessions)
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            UserSession entity or None if not found
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def update_activity(self, session_id: str) -> bool:
        """
        Update session last activity timestamp
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if update was successful
            
        Raises:
            NotFoundException: If session doesn't exist
            DatabaseException: If update fails
        """
        pass
    
    @abstractmethod
    async def extend_session(self, session_id: str, additional_seconds: int) -> bool:
        """
        Extend session expiration time
        
        Args:
            session_id: Session identifier
            additional_seconds: Seconds to add to expiration
            
        Returns:
            True if extension was successful
            
        Raises:
            NotFoundException: If session doesn't exist
            DatabaseException: If update fails
        """
        pass
    
    @abstractmethod
    async def close_session(self, session_id: str) -> bool:
        """
        Close/deactivate session
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was closed
            
        Raises:
            NotFoundException: If session doesn't exist
            DatabaseException: If update fails
        """
        pass
    
    @abstractmethod
    async def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions
        
        Returns:
            Number of sessions cleaned up
            
        Raises:
            DatabaseException: If cleanup fails
        """
        pass
    
    @abstractmethod
    async def find_sessions_by_type(self, session_type: SessionType, limit: int = 100) -> List[UserSession]:
        """
        Find sessions by type
        
        Args:
            session_type: Type of session to find
            limit: Maximum number of sessions to return
            
        Returns:
            List of UserSession entities
            
        Raises:
            DatabaseException: If query fails
        """
        pass


class UserToolConnectionRepository(ABC):
    """Repository interface for UserToolConnection entities"""
    
    @abstractmethod
    async def save(self, connection: UserToolConnection) -> bool:
        """
        Save user tool connection
        
        Args:
            connection: UserToolConnection entity to save
            
        Returns:
            True if save was successful
            
        Raises:
            DatabaseException: If save operation fails
        """
        pass
    
    @abstractmethod
    async def find_by_user_and_tool(self, user_id: str, tool_name: str) -> Optional[UserToolConnection]:
        """
        Find user tool connection by user ID and tool name
        
        Args:
            user_id: User identifier
            tool_name: Tool name
            
        Returns:
            UserToolConnection entity or None if not found
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def find_active_connections_by_user(self, user_id: str) -> List[UserToolConnection]:
        """
        Find active tool connections for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            List of active UserToolConnection entities
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def find_connections_by_server(self, server_name: str) -> List[UserToolConnection]:
        """
        Find all connections for a specific MCP server
        
        Args:
            server_name: MCP server name
            
        Returns:
            List of UserToolConnection entities
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def update_usage(self, user_id: str, tool_name: str) -> bool:
        """
        Update tool usage statistics
        
        Args:
            user_id: User identifier
            tool_name: Tool name
            
        Returns:
            True if update was successful
            
        Raises:
            NotFoundException: If connection doesn't exist
            DatabaseException: If update fails
        """
        pass
    
    @abstractmethod
    async def update_credentials(self, user_id: str, tool_name: str, encrypted_credentials: str) -> bool:
        """
        Update encrypted credentials for a tool connection
        
        Args:
            user_id: User identifier
            tool_name: Tool name
            encrypted_credentials: New encrypted credentials
            
        Returns:
            True if update was successful
            
        Raises:
            NotFoundException: If connection doesn't exist
            DatabaseException: If update fails
        """
        pass
    
    @abstractmethod
    async def deactivate_connection(self, user_id: str, tool_name: str) -> bool:
        """
        Deactivate a tool connection
        
        Args:
            user_id: User identifier
            tool_name: Tool name
            
        Returns:
            True if deactivation was successful
            
        Raises:
            NotFoundException: If connection doesn't exist
            DatabaseException: If update fails
        """
        pass
    
    @abstractmethod
    async def delete_connection(self, user_id: str, tool_name: str) -> bool:
        """
        Delete a tool connection
        
        Args:
            user_id: User identifier
            tool_name: Tool name
            
        Returns:
            True if deletion was successful
            
        Raises:
            NotFoundException: If connection doesn't exist
            DatabaseException: If deletion fails
        """
        pass
    
    @abstractmethod
    async def get_user_available_tools(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get list of tools available to user (active connections)
        
        Args:
            user_id: User identifier
            
        Returns:
            List of available tool information
            
        Raises:
            DatabaseException: If query fails
        """
        pass


class SessionPersistenceRepository(ABC):
    """Repository for session persistence and recovery"""
    
    @abstractmethod
    async def save_session_state(self, session_id: str, state_data: Dict[str, Any]) -> bool:
        """
        Save session state for recovery
        
        Args:
            session_id: Session identifier
            state_data: Session state data to persist
            
        Returns:
            True if save was successful
            
        Raises:
            DatabaseException: If save operation fails
        """
        pass
    
    @abstractmethod
    async def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get saved session state
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session state data or None if not found
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def find_recoverable_sessions(self, user_id: str, hours: int = 1) -> List[Dict[str, Any]]:
        """
        Find sessions that can be recovered for the user
        
        Args:
            user_id: User identifier
            hours: Hours back to look for recoverable sessions
            
        Returns:
            List of recoverable session data
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def delete_session_state(self, session_id: str) -> bool:
        """
        Delete persisted session state
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deletion was successful
            
        Raises:
            DatabaseException: If deletion fails
        """
        pass
    
    @abstractmethod
    async def cleanup_old_session_states(self, hours: int = 24) -> int:
        """
        Remove session states older than specified hours
        
        Args:
            hours: Age threshold in hours
            
        Returns:
            Number of cleaned up session states
            
        Raises:
            DatabaseException: If cleanup fails
        """
        pass


class ChatHistoryRepository(ABC):
    """Repository for chat history persistence"""
    
    @abstractmethod
    async def save_chat_history(self, user_id: str, chat_history: Dict[str, Any]) -> bool:
        """
        Save complete chat history for user
        
        Args:
            user_id: User identifier
            chat_history: Chat history data to save
            
        Returns:
            True if save was successful
            
        Raises:
            DatabaseException: If save operation fails
        """
        pass
    
    @abstractmethod
    async def get_chat_history(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user's chat history
        
        Args:
            user_id: User identifier
            
        Returns:
            Chat history data or None if not found
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def save_chat_session(self, user_id: str, session_id: str, session_data: Dict[str, Any]) -> bool:
        """
        Save individual chat session
        
        Args:
            user_id: User identifier
            session_id: Chat session identifier
            session_data: Chat session data
            
        Returns:
            True if save was successful
            
        Raises:
            DatabaseException: If save operation fails
        """
        pass
    
    @abstractmethod
    async def get_chat_session(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get individual chat session
        
        Args:
            user_id: User identifier
            session_id: Chat session identifier
            
        Returns:
            Chat session data or None if not found
            
        Raises:
            DatabaseException: If query fails
        """
        pass
    
    @abstractmethod
    async def update_active_session(self, user_id: str, session_id: str) -> bool:
        """
        Update user's active chat session
        
        Args:
            user_id: User identifier
            session_id: Session to mark as active
            
        Returns:
            True if update was successful
            
        Raises:
            DatabaseException: If update fails
        """
        pass
    
    @abstractmethod
    async def cleanup_old_chat_sessions(self, user_id: str, days: int = 30) -> int:
        """
        Remove old chat sessions for user
        
        Args:
            user_id: User identifier
            days: Age threshold in days
            
        Returns:
            Number of cleaned up sessions
            
        Raises:
            DatabaseException: If cleanup fails
        """
        pass 