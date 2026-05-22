"""
gRPC User Handler for ai-workflow-automation Core Microservice.

This module implements the UserService gRPC interface,
providing user management and preferences capabilities.
"""

import logging
from typing import Optional, TYPE_CHECKING
from uuid import uuid4
from datetime import datetime

import grpc
from grpc import aio

from app.shared.exceptions import BaseAppException, NotFoundException, ValidationException
from app.application.user_service import UserService

# Import generated protobuf modules
if TYPE_CHECKING:
    from app.interfaces.grpc.protos import user_pb2, user_pb2_grpc
else:
    try:
        from app.interfaces.grpc.protos import user_pb2, user_pb2_grpc
    except ImportError as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to import protobuf modules: {e}")
        raise ImportError("Protobuf modules not available. Run 'make generate-protos' first.")

logger = logging.getLogger(__name__)


class UserHandler(user_pb2_grpc.UserServiceServicer):
    """
    gRPC handler for user operations.
    
    Implements the UserService interface defined in user.proto.
    """

    def __init__(self, dependency_container=None):
        self.dependency_container = dependency_container
        self.user_service = UserService(dependency_container=dependency_container)

    async def GetUserProfile(
        self,
        request: user_pb2.GetUserProfileRequest,
        context: aio.ServicerContext
    ) -> user_pb2.GetUserProfileResponse:
        """Get user profile and preferences."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Getting user profile: {request.user_id}")
            
            # Validate request
            if not request.user_id:
                raise ValidationException(
                    message="User ID is required",
                    code="MISSING_USER_ID",
                    correlation_id=correlation_id
                )

            # Get user profile
            profile = await self.user_service.get_user_profile(
                request.user_id,
                include_preferences=request.include_preferences,
                include_tools=request.include_tools,
                correlation_id=correlation_id
            )

            if not profile:
                raise NotFoundException(
                    message=f"User not found: {request.user_id}",
                    code="USER_NOT_FOUND",
                    correlation_id=correlation_id
                )

            # Convert to protobuf
            response = user_pb2.GetUserProfileResponse(
                profile=self._convert_to_user_profile_proto(profile),
                status=user_pb2.UserStatus.Value(profile.get("status", "USER_STATUS_ACTIVE"))
            )
            
            if request.include_preferences and profile.get("preferences"):
                response.preferences.CopyFrom(
                    self._convert_to_user_preferences_proto(profile["preferences"])
                )
                
            if request.include_tools and profile.get("tools"):
                response.tools.extend([
                    self._convert_to_user_tool_proto(tool)
                    for tool in profile["tools"]
                ])

            logger.info(f"[{correlation_id}] User profile retrieved successfully: {request.user_id}")
            return response

        except ValidationException as e:
            logger.warning(f"[{correlation_id}] Validation error: {e.message}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, e.message)
            
        except NotFoundException as e:
            logger.warning(f"[{correlation_id}] Resource not found: {e.message}")
            await context.abort(grpc.StatusCode.NOT_FOUND, e.message)
            
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            await context.abort(grpc.StatusCode.INTERNAL, e.message)
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, "An unexpected error occurred")

    async def UpdateUserPreferences(
        self,
        request: user_pb2.UpdateUserPreferencesRequest,
        context: aio.ServicerContext
    ) -> user_pb2.UpdateUserPreferencesResponse:
        """Update user preferences."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Updating user preferences: {request.user_id}")
            
            # Validate request
            if not request.user_id:
                raise ValidationException(
                    message="User ID is required",
                    code="MISSING_USER_ID",
                    correlation_id=correlation_id
                )

            # Convert preferences from protobuf
            preferences = self._convert_from_user_preferences_proto(request.preferences)
            
            # Update preferences
            updated_preferences = await self.user_service.update_user_preferences(
                user_id=request.user_id,
                preferences=preferences,
                merge_mode=request.merge_mode,
                correlation_id=correlation_id
            )

            # Convert response to protobuf
            response = user_pb2.UpdateUserPreferencesResponse(
                updated_preferences=self._convert_to_user_preferences_proto(updated_preferences),
                success=True,
                message="User preferences updated successfully"
            )

            logger.info(f"[{correlation_id}] User preferences updated successfully: {request.user_id}")
            return response

        except ValidationException as e:
            logger.warning(f"[{correlation_id}] Validation error: {e.message}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, e.message)
            
        except NotFoundException as e:
            logger.warning(f"[{correlation_id}] Resource not found: {e.message}")
            await context.abort(grpc.StatusCode.NOT_FOUND, e.message)
            
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            await context.abort(grpc.StatusCode.INTERNAL, e.message)
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, "An unexpected error occurred")

    async def GetUserContext(
        self,
        request: user_pb2.GetUserContextRequest,
        context: aio.ServicerContext
    ) -> user_pb2.GetUserContextResponse:
        """Get user context."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Getting user context: {request.user_id}")
            
            # Validate request
            if not request.user_id:
                raise ValidationException(
                    message="User ID is required",
                    code="MISSING_USER_ID",
                    correlation_id=correlation_id
                )

            # Get user context
            user_context = await self.user_service.get_user_context(
                user_id=request.user_id,
                session_id=request.session_id or None,
                context_keys=list(request.context_keys) if request.context_keys else None,
                correlation_id=correlation_id
            )

            response = user_pb2.GetUserContextResponse(
                context=user_context.get("context", {}),
                session_id=request.session_id,
                last_updated=user_context.get("last_updated", datetime.utcnow().isoformat())
            )

            logger.info(f"[{correlation_id}] User context retrieved successfully: {request.user_id}")
            return response

        except ValidationException as e:
            logger.warning(f"[{correlation_id}] Validation error: {e.message}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, e.message)
            
        except NotFoundException as e:
            logger.warning(f"[{correlation_id}] Resource not found: {e.message}")
            await context.abort(grpc.StatusCode.NOT_FOUND, e.message)
            
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            await context.abort(grpc.StatusCode.INTERNAL, e.message)
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, "An unexpected error occurred")

    async def UpdateUserContext(
        self,
        request: user_pb2.UpdateUserContextRequest,
        context: aio.ServicerContext
    ) -> user_pb2.UpdateUserContextResponse:
        """Update user context."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Updating user context: {request.user_id}")
            
            # Validate request
            if not request.user_id:
                raise ValidationException(
                    message="User ID is required",
                    code="MISSING_USER_ID",
                    correlation_id=correlation_id
                )

            # Update user context
            updated_context = await self.user_service.update_user_context(
                user_id=request.user_id,
                session_id=request.session_id or None,
                context_updates=dict(request.context_updates) if request.context_updates else {},
                merge_mode=request.merge_mode,
                correlation_id=correlation_id
            )

            response = user_pb2.UpdateUserContextResponse(
                updated_context=updated_context.get("context", {}),
                success=True,
                message="User context updated successfully"
            )

            logger.info(f"[{correlation_id}] User context updated successfully: {request.user_id}")
            return response

        except ValidationException as e:
            logger.warning(f"[{correlation_id}] Validation error: {e.message}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, e.message)
            
        except NotFoundException as e:
            logger.warning(f"[{correlation_id}] Resource not found: {e.message}")
            await context.abort(grpc.StatusCode.NOT_FOUND, e.message)
            
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            await context.abort(grpc.StatusCode.INTERNAL, e.message)
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, "An unexpected error occurred")

    async def GetUserTools(
        self,
        request: user_pb2.GetUserToolsRequest,
        context: aio.ServicerContext
    ) -> user_pb2.GetUserToolsResponse:
        """Get user tools and capabilities."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Getting user tools: {request.user_id}")
            
            # Validate request
            if not request.user_id:
                raise ValidationException(
                    message="User ID is required",
                    code="MISSING_USER_ID",
                    correlation_id=correlation_id
                )

            # Get user tools
            result = await self.user_service.get_user_tools(
                user_id=request.user_id,
                category=user_pb2.ToolCategory.Name(request.category) if request.category else None,
                include_disabled=request.include_disabled,
                correlation_id=correlation_id
            )

            # Convert to protobuf
            tools = [
                self._convert_to_user_tool_proto(tool)
                for tool in result.get("tools", [])
            ]
            
            available_categories = [
                user_pb2.ToolCategory.Value(cat)
                for cat in result.get("available_categories", [])
            ]

            response = user_pb2.GetUserToolsResponse(
                tools=tools,
                total_count=result.get("total_count", 0),
                available_categories=available_categories
            )

            logger.info(f"[{correlation_id}] Retrieved {len(tools)} user tools")
            return response

        except ValidationException as e:
            logger.warning(f"[{correlation_id}] Validation error: {e.message}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, e.message)
            
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            await context.abort(grpc.StatusCode.INTERNAL, e.message)
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, "An unexpected error occurred")

    async def RegisterUserTool(
        self,
        request: user_pb2.RegisterUserToolRequest,
        context: aio.ServicerContext
    ) -> user_pb2.RegisterUserToolResponse:
        """Register a new user tool."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Registering user tool: {request.user_id}")
            
            # Validate request
            if not request.user_id:
                raise ValidationException(
                    message="User ID is required",
                    code="MISSING_USER_ID",
                    correlation_id=correlation_id
                )

            # Convert tool from protobuf
            tool = self._convert_from_user_tool_proto(request.tool)
            
            # Register tool
            registered_tool = await self.user_service.register_user_tool(
                user_id=request.user_id,
                tool=tool,
                auto_enable=request.auto_enable,
                correlation_id=correlation_id
            )

            response = user_pb2.RegisterUserToolResponse(
                registered_tool=self._convert_to_user_tool_proto(registered_tool),
                success=True,
                message="User tool registered successfully",
                tool_id=registered_tool["tool_id"]
            )

            logger.info(f"[{correlation_id}] User tool registered successfully: {registered_tool['tool_id']}")
            return response

        except ValidationException as e:
            logger.warning(f"[{correlation_id}] Validation error: {e.message}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, e.message)
            
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            await context.abort(grpc.StatusCode.INTERNAL, e.message)
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, "An unexpected error occurred")

    async def GetUserActivity(
        self,
        request: user_pb2.GetUserActivityRequest,
        context: aio.ServicerContext
    ) -> user_pb2.GetUserActivityResponse:
        """Get user activity and metrics."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Getting user activity: {request.user_id}")
            
            # Validate request
            if not request.user_id:
                raise ValidationException(
                    message="User ID is required",
                    code="MISSING_USER_ID",
                    correlation_id=correlation_id
                )

            # Get user activity
            result = await self.user_service.get_user_activity(
                user_id=request.user_id,
                start_time=request.start_time if request.start_time else None,
                end_time=request.end_time if request.end_time else None,
                activity_type=user_pb2.ActivityType.Name(request.activity_type) if request.activity_type else None,
                limit=request.limit or 50,
                correlation_id=correlation_id
            )

            # Convert to protobuf
            activities = [
                self._convert_to_user_activity_proto(activity)
                for activity in result.get("activities", [])
            ]
            
            metrics = self._convert_to_user_metrics_proto(result.get("metrics", {}))

            response = user_pb2.GetUserActivityResponse(
                activities=activities,
                metrics=metrics,
                has_more=result.get("has_more", False),
                next_cursor=result.get("next_cursor", "")
            )

            logger.info(f"[{correlation_id}] Retrieved {len(activities)} user activities")
            return response

        except ValidationException as e:
            logger.warning(f"[{correlation_id}] Validation error: {e.message}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, e.message)
            
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            await context.abort(grpc.StatusCode.INTERNAL, e.message)
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, "An unexpected error occurred")

    def _convert_to_user_profile_proto(self, profile: dict) -> user_pb2.UserProfile:
        """Convert domain user profile to protobuf message."""
        if user_pb2 is None:
            return None
            
        return user_pb2.UserProfile(
            user_id=profile["user_id"],
            email=profile.get("email", ""),
            display_name=profile.get("display_name", ""),
            avatar_url=profile.get("avatar_url", ""),
            created_at=profile.get("created_at", ""),
            last_active=profile.get("last_active", ""),
            status=user_pb2.UserStatus.Value(profile.get("status", "USER_STATUS_ACTIVE")),
            metadata=profile.get("metadata", {})
        )

    def _convert_to_user_preferences_proto(self, preferences: dict) -> user_pb2.UserPreferences:
        """Convert domain user preferences to protobuf message."""
        if user_pb2 is None:
            return None
            
        # Convert sub-preferences
        ui_prefs = preferences.get("ui_preferences", {})
        workflow_prefs = preferences.get("workflow_preferences", {})
        notification_prefs = preferences.get("notification_preferences", {})
        security_prefs = preferences.get("security_preferences", {})
        
        return user_pb2.UserPreferences(
            language=user_pb2.LanguagePreference(
                code=preferences.get("language", {}).get("code", "en"),
                display_name=preferences.get("language", {}).get("display_name", "English"),
                is_default=preferences.get("language", {}).get("is_default", True)
            ),
            ui_preferences=user_pb2.UIPreferences(
                theme=ui_prefs.get("theme", "light"),
                layout=ui_prefs.get("layout", "default"),
                enable_animations=ui_prefs.get("enable_animations", True),
                items_per_page=ui_prefs.get("items_per_page", 20),
                favorite_tools=ui_prefs.get("favorite_tools", [])
            ),
            workflow_preferences=user_pb2.WorkflowPreferences(
                auto_save_workflows=workflow_prefs.get("auto_save_workflows", True),
                default_timeout_seconds=workflow_prefs.get("default_timeout_seconds", 300),
                enable_streaming=workflow_prefs.get("enable_streaming", True),
                default_model=workflow_prefs.get("default_model", "gpt-4"),
                preferred_tools=workflow_prefs.get("preferred_tools", [])
            ),
            notification_preferences=user_pb2.NotificationPreferences(
                email_notifications=notification_prefs.get("email_notifications", True),
                push_notifications=notification_prefs.get("push_notifications", True),
                workflow_completion=notification_prefs.get("workflow_completion", True),
                error_alerts=notification_prefs.get("error_alerts", True),
                notification_channels=notification_prefs.get("notification_channels", [])
            ),
            security_preferences=user_pb2.SecurityPreferences(
                require_mfa=security_prefs.get("require_mfa", False),
                session_timeout_minutes=security_prefs.get("session_timeout_minutes", 60),
                allow_tool_registration=security_prefs.get("allow_tool_registration", True),
                trusted_domains=security_prefs.get("trusted_domains", [])
            ),
            custom_preferences=preferences.get("custom_preferences", {})
        )

    def _convert_from_user_preferences_proto(self, preferences_proto: user_pb2.UserPreferences) -> dict:
        """Convert protobuf user preferences to domain model."""
        if preferences_proto is None:
            return {}
            
        return {
            "language": {
                "code": preferences_proto.language.code,
                "display_name": preferences_proto.language.display_name,
                "is_default": preferences_proto.language.is_default
            },
            "ui_preferences": {
                "theme": preferences_proto.ui_preferences.theme,
                "layout": preferences_proto.ui_preferences.layout,
                "enable_animations": preferences_proto.ui_preferences.enable_animations,
                "items_per_page": preferences_proto.ui_preferences.items_per_page,
                "favorite_tools": list(preferences_proto.ui_preferences.favorite_tools)
            },
            "workflow_preferences": {
                "auto_save_workflows": preferences_proto.workflow_preferences.auto_save_workflows,
                "default_timeout_seconds": preferences_proto.workflow_preferences.default_timeout_seconds,
                "enable_streaming": preferences_proto.workflow_preferences.enable_streaming,
                "default_model": preferences_proto.workflow_preferences.default_model,
                "preferred_tools": list(preferences_proto.workflow_preferences.preferred_tools)
            },
            "notification_preferences": {
                "email_notifications": preferences_proto.notification_preferences.email_notifications,
                "push_notifications": preferences_proto.notification_preferences.push_notifications,
                "workflow_completion": preferences_proto.notification_preferences.workflow_completion,
                "error_alerts": preferences_proto.notification_preferences.error_alerts,
                "notification_channels": list(preferences_proto.notification_preferences.notification_channels)
            },
            "security_preferences": {
                "require_mfa": preferences_proto.security_preferences.require_mfa,
                "session_timeout_minutes": preferences_proto.security_preferences.session_timeout_minutes,
                "allow_tool_registration": preferences_proto.security_preferences.allow_tool_registration,
                "trusted_domains": list(preferences_proto.security_preferences.trusted_domains)
            },
            "custom_preferences": dict(preferences_proto.custom_preferences)
        }

    def _convert_to_user_tool_proto(self, tool: dict) -> user_pb2.UserTool:
        """Convert domain user tool to protobuf message."""
        if user_pb2 is None:
            return None
            
        return user_pb2.UserTool(
            tool_id=tool["tool_id"],
            name=tool["name"],
            description=tool.get("description", ""),
            category=user_pb2.ToolCategory.Value(tool.get("category", "TOOL_CATEGORY_GENERAL")),
            configuration=tool.get("configuration", {}),
            enabled=tool.get("enabled", True),
            registered_at=tool.get("registered_at", ""),
            last_used=tool.get("last_used", ""),
            usage_count=tool.get("usage_count", 0)
        )

    def _convert_from_user_tool_proto(self, tool_proto: user_pb2.UserTool) -> dict:
        """Convert protobuf user tool to domain model."""
        if tool_proto is None:
            return {}
            
        return {
            "tool_id": tool_proto.tool_id,
            "name": tool_proto.name,
            "description": tool_proto.description,
            "category": user_pb2.ToolCategory.Name(tool_proto.category),
            "configuration": dict(tool_proto.configuration),
            "enabled": tool_proto.enabled,
            "registered_at": tool_proto.registered_at,
            "last_used": tool_proto.last_used,
            "usage_count": tool_proto.usage_count
        }

    def _convert_to_user_activity_proto(self, activity: dict) -> user_pb2.UserActivity:
        """Convert domain user activity to protobuf message."""
        if user_pb2 is None:
            return None
            
        return user_pb2.UserActivity(
            activity_id=activity["activity_id"],
            user_id=activity["user_id"],
            activity_type=user_pb2.ActivityType.Value(activity.get("activity_type", "ACTIVITY_TYPE_UNSPECIFIED")),
            description=activity.get("description", ""),
            details=activity.get("details", {}),
            timestamp=activity.get("timestamp", ""),
            session_id=activity.get("session_id", "")
        )

    def _convert_to_user_metrics_proto(self, metrics: dict) -> user_pb2.UserMetrics:
        """Convert domain user metrics to protobuf message."""
        if user_pb2 is None:
            return None
            
        tool_usage = [
            user_pb2.ToolUsage(
                tool_name=usage["tool_name"],
                usage_count=usage.get("usage_count", 0),
                last_used=usage.get("last_used", ""),
                success_rate=usage.get("success_rate", 0.0)
            )
            for usage in metrics.get("tool_usage", [])
        ]
        
        return user_pb2.UserMetrics(
            total_workflows=metrics.get("total_workflows", 0),
            total_executions=metrics.get("total_executions", 0),
            total_tool_calls=metrics.get("total_tool_calls", 0),
            first_activity=metrics.get("first_activity", ""),
            last_activity=metrics.get("last_activity", ""),
            active_sessions=metrics.get("active_sessions", 0),
            tool_usage=tool_usage
        ) 