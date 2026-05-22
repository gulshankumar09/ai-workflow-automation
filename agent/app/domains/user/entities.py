"""
User Domain Entities

This module contains the core entities for user management, context tracking,
and user preferences within the ai-workflow-automation system. Following DDD principles,
these entities encapsulate business logic and maintain data integrity.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum
import uuid

from app.shared.exceptions import ValidationException


class SessionType(Enum):
    """Types of user sessions"""
    ANONYMOUS = "anonymous"
    AUTHENTICATED = "authenticated"
    WEBSOCKET = "websocket"
    EXECUTION = "execution"


class UserRole(Enum):
    """User roles in the system"""
    USER = "user"
    ADMIN = "admin"
    DEVELOPER = "developer"
    GUEST = "guest"


@dataclass
class UserPreferences:
    """User preferences and settings"""
    
    ui_theme: str = "light"
    language: str = "en"
    timezone: str = "UTC"
    notification_settings: Dict[str, bool] = field(default_factory=lambda: {
        "email_notifications": True,
        "push_notifications": True,
        "workflow_updates": True,
        "system_alerts": True
    })
    workflow_settings: Dict[str, Any] = field(default_factory=lambda: {
        "auto_save": True,
        "default_timeout": 300,
        "preferred_tools": [],
        "default_provider": "gemini"
    })
    privacy_settings: Dict[str, bool] = field(default_factory=lambda: {
        "share_usage_data": False,
        "track_analytics": True,
        "store_conversation_history": True
    })
    custom_preferences: Dict[str, Any] = field(default_factory=dict)
    
    def update_preference(self, category: str, key: str, value: Any) -> None:
        """Update a preference value"""
        if hasattr(self, category):
            category_dict = getattr(self, category)
            if isinstance(category_dict, dict):
                category_dict[key] = value
            else:
                # For non-dict attributes, set the attribute directly
                setattr(self, category, value)
        else:
            self.custom_preferences[f"{category}.{key}"] = value
    
    def get_preference(self, category: str, key: str, default: Any = None) -> Any:
        """Get a preference value"""
        if hasattr(self, category):
            category_dict = getattr(self, category)
            if isinstance(category_dict, dict):
                return category_dict.get(key, default)
            else:
                # For non-dict attributes, return the attribute value directly
                return getattr(self, category, default)
        else:
            return self.custom_preferences.get(f"{category}.{key}", default)


@dataclass
class WorkflowPattern:
    """User workflow usage pattern"""
    
    pattern_name: str
    usage_count: int = 0
    success_rate: float = 0.0
    last_used: Optional[datetime] = None
    average_execution_time: float = 0.0
    preferred_tools: List[str] = field(default_factory=list)
    common_parameters: Dict[str, Any] = field(default_factory=dict)
    
    def update_usage(self, success: bool, execution_time: float, parameters: Dict[str, Any] = None):
        """Update pattern usage statistics"""
        self.usage_count += 1
        self.last_used = datetime.utcnow()
        
        # Update success rate
        old_successes = self.success_rate * (self.usage_count - 1)
        new_successes = old_successes + (1 if success else 0)
        self.success_rate = new_successes / self.usage_count
        
        # Update average execution time
        old_total_time = self.average_execution_time * (self.usage_count - 1)
        new_total_time = old_total_time + execution_time
        self.average_execution_time = new_total_time / self.usage_count
        
        # Update common parameters
        if parameters:
            for key, value in parameters.items():
                if key in self.common_parameters:
                    # Keep track of parameter frequency
                    if isinstance(self.common_parameters[key], dict) and "count" in self.common_parameters[key]:
                        self.common_parameters[key]["count"] += 1
                    else:
                        self.common_parameters[key] = {"value": value, "count": 1}
                else:
                    self.common_parameters[key] = {"value": value, "count": 1}


@dataclass
class ToolUsage:
    """User tool usage statistics"""
    
    tool_name: str
    usage_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_execution_time: float = 0.0
    last_used: Optional[datetime] = None
    favorite: bool = False
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.usage_count == 0:
            return 0.0
        return self.success_count / self.usage_count
    
    @property
    def average_execution_time(self) -> float:
        """Calculate average execution time"""
        if self.usage_count == 0:
            return 0.0
        return self.total_execution_time / self.usage_count
    
    def record_usage(self, success: bool, execution_time: float, error_message: str = None):
        """Record a tool usage event"""
        self.usage_count += 1
        self.last_used = datetime.utcnow()
        self.total_execution_time += execution_time
        
        if success:
            self.success_count += 1
        else:
            self.error_count += 1


@dataclass
class ChatMessage:
    """Individual chat message"""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    role: str = "user"  # "user", "assistant", "system"
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "context": self.context
        }


@dataclass
class ChatSession:
    """Chat session containing multiple messages"""
    
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    title: str = "New Chat"
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    session_type: str = "workflow_assistance"  # "workflow_assistance", "general", "debugging"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None) -> ChatMessage:
        """Add a new message to the session"""
        message = ChatMessage(
            user_id=self.user_id,
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        
        # Update title based on first user message
        if len(self.messages) == 1 and role == "user":
            self.title = content[:50] + "..." if len(content) > 50 else content
        
        return message
    
    def get_context_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages for context"""
        recent_messages = self.messages[-limit:] if limit > 0 else self.messages
        return [msg.to_dict() for msg in recent_messages]
    
    def get_conversation_summary(self) -> str:
        """Generate a brief summary of the conversation"""
        if not self.messages:
            return "Empty conversation"
        
        user_messages = [msg for msg in self.messages if msg.role == "user"]
        if not user_messages:
            return "No user messages"
        
        # Return the first user message as a summary
        return user_messages[0].content[:100] + "..." if len(user_messages[0].content) > 100 else user_messages[0].content


@dataclass
class ChatHistory:
    """User's complete chat history management"""
    
    user_id: str
    sessions: Dict[str, ChatSession] = field(default_factory=dict)
    active_session_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def create_session(self, session_type: str = "workflow_assistance") -> ChatSession:
        """Create a new chat session"""
        session = ChatSession(
            user_id=self.user_id,
            session_type=session_type
        )
        self.sessions[session.session_id] = session
        self.active_session_id = session.session_id
        self.updated_at = datetime.utcnow()
        return session
    
    def get_active_session(self) -> Optional[ChatSession]:
        """Get the currently active session"""
        if self.active_session_id and self.active_session_id in self.sessions:
            return self.sessions[self.active_session_id]
        return None
    
    def add_message_to_active_session(self, role: str, content: str, metadata: Dict[str, Any] = None) -> ChatMessage:
        """Add message to active session, create one if none exists"""
        active_session = self.get_active_session()
        if not active_session:
            active_session = self.create_session()
        
        message = active_session.add_message(role, content, metadata)
        self.updated_at = datetime.utcnow()
        return message
    
    def get_recent_sessions(self, limit: int = 10) -> List[ChatSession]:
        """Get recent chat sessions"""
        sorted_sessions = sorted(
            self.sessions.values(),
            key=lambda s: s.updated_at,
            reverse=True
        )
        return sorted_sessions[:limit]
    
    def search_messages(self, query: str, limit: int = 20) -> List[ChatMessage]:
        """Search for messages containing specific text"""
        matching_messages = []
        for session in self.sessions.values():
            for message in session.messages:
                if query.lower() in message.content.lower():
                    matching_messages.append(message)
        
        # Sort by timestamp, most recent first
        matching_messages.sort(key=lambda m: m.timestamp, reverse=True)
        return matching_messages[:limit]
    
    def get_conversation_context(self, session_id: str = None, message_limit: int = 10) -> List[Dict[str, Any]]:
        """Get conversation context for AI prompt"""
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
        else:
            session = self.get_active_session()
        
        if not session:
            return []
        
        return session.get_context_messages(message_limit)
    
    def cleanup_old_sessions(self, days: int = 30) -> int:
        """Remove sessions older than specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        old_session_ids = [
            session_id for session_id, session in self.sessions.items()
            if session.updated_at < cutoff_date and not session.is_active
        ]
        
        for session_id in old_session_ids:
            del self.sessions[session_id]
        
        # Reset active session if it was deleted
        if self.active_session_id in old_session_ids:
            self.active_session_id = None
        
        self.updated_at = datetime.utcnow()
        return len(old_session_ids)


@dataclass
class UserContext:
    """Rich user context including preferences, patterns, and usage history"""
    
    user_id: str
    preferences: UserPreferences = field(default_factory=UserPreferences)
    workflow_patterns: Dict[str, WorkflowPattern] = field(default_factory=dict)
    tool_usage: Dict[str, ToolUsage] = field(default_factory=dict)
    chat_history: Optional[ChatHistory] = None
    session_context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Initialize chat history if not provided"""
        if self.chat_history is None:
            self.chat_history = ChatHistory(user_id=self.user_id)
    
    def add_workflow_pattern(self, pattern_name: str, success: bool, execution_time: float, parameters: Dict[str, Any] = None):
        """Add or update a workflow pattern"""
        if pattern_name not in self.workflow_patterns:
            self.workflow_patterns[pattern_name] = WorkflowPattern(pattern_name=pattern_name)
        
        self.workflow_patterns[pattern_name].update_usage(success, execution_time, parameters)
        self.updated_at = datetime.utcnow()
    
    def record_tool_usage(self, tool_name: str, success: bool, execution_time: float, error_message: str = None):
        """Record tool usage"""
        if tool_name not in self.tool_usage:
            self.tool_usage[tool_name] = ToolUsage(tool_name=tool_name)
        
        self.tool_usage[tool_name].record_usage(success, execution_time, error_message)
        self.updated_at = datetime.utcnow()
    
    def get_preferred_tools(self, limit: int = 5) -> List[str]:
        """Get user's most frequently used tools"""
        sorted_tools = sorted(
            self.tool_usage.values(),
            key=lambda t: (t.success_rate, t.usage_count),
            reverse=True
        )
        return [tool.tool_name for tool in sorted_tools[:limit]]
    
    def get_workflow_recommendations(self) -> List[str]:
        """Get recommended workflow patterns based on usage"""
        sorted_patterns = sorted(
            self.workflow_patterns.values(),
            key=lambda p: (p.success_rate, p.usage_count),
            reverse=True
        )
        return [pattern.pattern_name for pattern in sorted_patterns[:3]]


@dataclass
class UserSession:
    """User session management"""
    
    session_id: str
    user_id: str
    session_type: SessionType
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=1))
    is_active: bool = True
    connection_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create_new(
        cls,
        user_id: str,
        session_type: SessionType,
        connection_id: str = None,
        ttl_seconds: int = 3600
    ) -> "UserSession":
        """Create a new session"""
        session_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        
        return cls(
            session_id=session_id,
            user_id=user_id,
            session_type=session_type,
            connection_id=connection_id,
            expires_at=expires_at
        )
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at
    
    def extend_session(self, ttl_seconds: int = 3600) -> None:
        """Extend session expiration"""
        self.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        self.last_activity = datetime.utcnow()
    
    def update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()


@dataclass
class UserToolConnection:
    """User's tool connection and credentials"""
    
    user_id: str
    tool_name: str
    server_name: str
    encrypted_credentials: str
    scopes: List[str] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_last_used(self) -> None:
        """Update last used timestamp"""
        self.last_used = datetime.utcnow()
        self.updated_at = datetime.utcnow()


@dataclass
class User:
    """Main user entity"""
    
    id: Optional[str] = None
    email: str = ""
    role: UserRole = UserRole.USER
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    context: Optional[UserContext] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize user context if not provided"""
        if self.context is None and self.id:
            self.context = UserContext(user_id=self.id)
    
    @classmethod
    def create_new(cls, email: str, role: UserRole = UserRole.USER) -> "User":
        """Create a new user"""
        if not email or "@" not in email:
            raise ValidationException(
                "Invalid email address",
                details={"email": email}
            )
        
        user_id = str(uuid.uuid4())
        user = cls(
            id=user_id,
            email=email.lower().strip(),
            role=role
        )
        
        # Initialize context
        user.context = UserContext(user_id=user_id)
        
        return user
    
    def update_login(self) -> None:
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def deactivate(self) -> None:
        """Deactivate user account"""
        self.is_active = False
        self.updated_at = datetime.utcnow()
    
    def activate(self) -> None:
        """Activate user account"""
        self.is_active = True
        self.updated_at = datetime.utcnow()
    
    def update_preferences(self, category: str, preferences: Dict[str, Any]) -> None:
        """Update user preferences"""
        if not self.context:
            self.context = UserContext(user_id=self.id)
        
        for key, value in preferences.items():
            self.context.preferences.update_preference(category, key, value)
        
        self.updated_at = datetime.utcnow()


@dataclass
class ChatMessage:
    """Individual chat message"""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    role: str = "user"  # "user", "assistant", "system"
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "context": self.context
        }


@dataclass
class ChatSession:
    """Chat session containing multiple messages"""
    
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    title: str = "New Chat"
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    session_type: str = "workflow_assistance"  # "workflow_assistance", "general", "debugging"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None) -> ChatMessage:
        """Add a new message to the session"""
        message = ChatMessage(
            user_id=self.user_id,
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        
        # Update title based on first user message
        if len(self.messages) == 1 and role == "user":
            self.title = content[:50] + "..." if len(content) > 50 else content
        
        return message
    
    def get_context_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages for context"""
        recent_messages = self.messages[-limit:] if limit > 0 else self.messages
        return [msg.to_dict() for msg in recent_messages]
    
    def get_conversation_summary(self) -> str:
        """Generate a brief summary of the conversation"""
        if not self.messages:
            return "Empty conversation"
        
        user_messages = [msg for msg in self.messages if msg.role == "user"]
        if not user_messages:
            return "No user messages"
        
        # Return the first user message as a summary
        return user_messages[0].content[:100] + "..." if len(user_messages[0].content) > 100 else user_messages[0].content


@dataclass
class ChatHistory:
    """User's complete chat history management"""
    
    user_id: str
    sessions: Dict[str, ChatSession] = field(default_factory=dict)
    active_session_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def create_session(self, session_type: str = "workflow_assistance") -> ChatSession:
        """Create a new chat session"""
        session = ChatSession(
            user_id=self.user_id,
            session_type=session_type
        )
        self.sessions[session.session_id] = session
        self.active_session_id = session.session_id
        self.updated_at = datetime.utcnow()
        return session
    
    def get_active_session(self) -> Optional[ChatSession]:
        """Get the currently active session"""
        if self.active_session_id and self.active_session_id in self.sessions:
            return self.sessions[self.active_session_id]
        return None
    
    def add_message_to_active_session(self, role: str, content: str, metadata: Dict[str, Any] = None) -> ChatMessage:
        """Add message to active session, create one if none exists"""
        active_session = self.get_active_session()
        if not active_session:
            active_session = self.create_session()
        
        message = active_session.add_message(role, content, metadata)
        self.updated_at = datetime.utcnow()
        return message
    
    def get_recent_sessions(self, limit: int = 10) -> List[ChatSession]:
        """Get recent chat sessions"""
        sorted_sessions = sorted(
            self.sessions.values(),
            key=lambda s: s.updated_at,
            reverse=True
        )
        return sorted_sessions[:limit]
    
    def search_messages(self, query: str, limit: int = 20) -> List[ChatMessage]:
        """Search for messages containing specific text"""
        matching_messages = []
        for session in self.sessions.values():
            for message in session.messages:
                if query.lower() in message.content.lower():
                    matching_messages.append(message)
        
        # Sort by timestamp, most recent first
        matching_messages.sort(key=lambda m: m.timestamp, reverse=True)
        return matching_messages[:limit]
    
    def get_conversation_context(self, session_id: str = None, message_limit: int = 10) -> List[Dict[str, Any]]:
        """Get conversation context for AI prompt"""
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
        else:
            session = self.get_active_session()
        
        if not session:
            return []
        
        return session.get_context_messages(message_limit)
    
    def cleanup_old_sessions(self, days: int = 30) -> int:
        """Remove sessions older than specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        old_session_ids = [
            session_id for session_id, session in self.sessions.items()
            if session.updated_at < cutoff_date and not session.is_active
        ]
        
        for session_id in old_session_ids:
            del self.sessions[session_id]
        
        # Reset active session if it was deleted
        if self.active_session_id in old_session_ids:
            self.active_session_id = None
        
        self.updated_at = datetime.utcnow()
        return len(old_session_ids) 