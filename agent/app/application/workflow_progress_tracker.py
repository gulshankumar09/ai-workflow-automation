"""
Real-time Workflow Progress Tracker

This module provides real-time progress tracking for workflow execution with Supabase
Realtime integration, comprehensive monitoring, and user notification capabilities.

Key Features:
- Real-time progress updates via Supabase Realtime
- Comprehensive workflow execution monitoring
- User notification system with multiple channels
- Progress analytics and performance metrics
- Event-driven architecture with custom events
- Comprehensive error handling and recovery
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Set, Union
from contextlib import asynccontextmanager

from app.shared.exceptions import (
    ValidationException,
    ExternalServiceException,
    DatabaseException,
    ErrorSeverity
)
from app.application.parallel_workflow_executor import (
    WorkflowExecutionResult,
    PhaseExecutionResult,
    StepExecutionResult,
    WorkflowStatus,
    ExecutionContext
)


class ProgressEventType(Enum):
    """Types of progress events"""
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_FAILED = "phase_failed"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_RETRY = "step_retry"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    MILESTONE_REACHED = "milestone_reached"


class NotificationChannel(Enum):
    """Notification delivery channels"""
    REALTIME = "realtime"  # Supabase Realtime
    WEBHOOK = "webhook"    # HTTP webhook
    EMAIL = "email"        # Email notification
    SLACK = "slack"        # Slack integration
    WEBSOCKET = "websocket"  # Direct WebSocket


class NotificationPriority(Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ProgressEvent:
    """Individual progress event"""
    event_id: str
    event_type: ProgressEventType
    workflow_id: str
    timestamp: float
    data: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "workflow_id": self.workflow_id,
            "timestamp": self.timestamp,
            "iso_timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "data": self.data,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id
        }


@dataclass
class ProgressSnapshot:
    """Current progress snapshot"""
    workflow_id: str
    status: WorkflowStatus
    current_phase: Optional[int] = None
    total_phases: int = 0
    completed_steps: int = 0
    total_steps: int = 0
    failed_steps: int = 0
    start_time: Optional[float] = None
    last_update: Optional[float] = None
    estimated_completion: Optional[float] = None
    parallel_efficiency: float = 0.0
    error_summary: Optional[Dict[str, Any]] = None
    
    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage"""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100
    
    @property
    def elapsed_time(self) -> float:
        """Calculate elapsed time in seconds"""
        if not self.start_time:
            return 0.0
        return (self.last_update or time.time()) - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)


@dataclass
class NotificationRule:
    """Rule for sending notifications"""
    rule_id: str
    name: str
    event_types: List[ProgressEventType]
    channels: List[NotificationChannel]
    priority: NotificationPriority = NotificationPriority.NORMAL
    conditions: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    user_filters: List[str] = field(default_factory=list)  # User IDs to filter
    
    def matches_event(self, event: ProgressEvent) -> bool:
        """Check if this rule matches an event"""
        if not self.enabled:
            return False
        
        if event.event_type not in self.event_types:
            return False
        
        if self.user_filters and event.user_id not in self.user_filters:
            return False
        
        # Check additional conditions
        for condition_key, condition_value in self.conditions.items():
            if condition_key in event.data:
                if event.data[condition_key] != condition_value:
                    return False
        
        return True


class ProgressTrackingException(DatabaseException):
    """Exception for progress tracking related errors"""
    
    def __init__(
        self,
        message: str,
        tracking_info: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        enhanced_details = tracking_info or {}
        enhanced_details["component"] = "progress_tracker"
        
        super().__init__(
            message=message,
            correlation_id=correlation_id,
            details=enhanced_details,
            severity=ErrorSeverity.MEDIUM
        )


class WorkflowProgressTracker:
    """
    Real-time workflow progress tracker with comprehensive monitoring
    
    This service provides real-time tracking of workflow execution progress
    with integration to Supabase Realtime, user notifications, and comprehensive
    analytics. It supports multiple notification channels and custom event rules.
    
    Features:
    - Real-time progress updates via Supabase Realtime
    - Multi-channel notification system
    - Custom notification rules and filtering
    - Progress analytics and performance metrics
    - Event history and audit logging
    - Integration with circuit breaker events
    """
    
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """
        Initialize the Progress Tracker
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase API key
            correlation_id: Request correlation ID
        """
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.logger = logging.getLogger(__name__)
        
        # Progress tracking state
        self.active_workflows: Dict[str, ProgressSnapshot] = {}
        self.event_history: Dict[str, List[ProgressEvent]] = {}
        self.notification_rules: Dict[str, NotificationRule] = {}
        
        # Subscribers and callbacks
        self.event_subscribers: Dict[str, List[Callable]] = {}
        self.webhook_endpoints: Dict[str, str] = {}
        
        # Performance metrics
        self.metrics: Dict[str, Any] = {
            "total_workflows_tracked": 0,
            "total_events_processed": 0,
            "total_notifications_sent": 0,
            "average_workflow_duration": 0.0,
            "start_time": time.time()
        }
        
        # Initialize default notification rules
        self._initialize_default_rules()
    
    def _initialize_default_rules(self) -> None:
        """Initialize default notification rules"""
        # Critical workflow failures
        self.add_notification_rule(NotificationRule(
            rule_id="critical_failures",
            name="Critical Workflow Failures",
            event_types=[ProgressEventType.WORKFLOW_FAILED],
            channels=[NotificationChannel.REALTIME, NotificationChannel.EMAIL],
            priority=NotificationPriority.CRITICAL
        ))
        
        # Workflow completions
        self.add_notification_rule(NotificationRule(
            rule_id="workflow_completions",
            name="Workflow Completions",
            event_types=[ProgressEventType.WORKFLOW_COMPLETED],
            channels=[NotificationChannel.REALTIME],
            priority=NotificationPriority.NORMAL
        ))
        
        # Circuit breaker events
        self.add_notification_rule(NotificationRule(
            rule_id="circuit_breaker_events",
            name="Circuit Breaker Triggers",
            event_types=[ProgressEventType.CIRCUIT_BREAKER_TRIGGERED],
            channels=[NotificationChannel.REALTIME, NotificationChannel.SLACK],
            priority=NotificationPriority.HIGH
        ))
    
    async def start_tracking_workflow(
        self,
        workflow_id: str,
        user_id: str,
        total_steps: int,
        total_phases: int,
        context: Optional[ExecutionContext] = None
    ) -> None:
        """
        Start tracking a new workflow
        
        Args:
            workflow_id: Workflow identifier
            user_id: User executing the workflow
            total_steps: Total number of steps in workflow
            total_phases: Total number of execution phases
            context: Optional execution context
        """
        try:
            # Create progress snapshot
            snapshot = ProgressSnapshot(
                workflow_id=workflow_id,
                status=WorkflowStatus.RUNNING,
                total_steps=total_steps,
                total_phases=total_phases,
                start_time=time.time(),
                last_update=time.time()
            )
            
            self.active_workflows[workflow_id] = snapshot
            
            # Initialize event history
            if workflow_id not in self.event_history:
                self.event_history[workflow_id] = []
            
            # Create and emit start event
            event = ProgressEvent(
                event_id=str(uuid.uuid4()),
                event_type=ProgressEventType.WORKFLOW_STARTED,
                workflow_id=workflow_id,
                timestamp=time.time(),
                data={
                    "total_steps": total_steps,
                    "total_phases": total_phases,
                    "context": context.workflow_id if context else None
                },
                correlation_id=self.correlation_id,
                user_id=user_id
            )
            
            await self._emit_event(event)
            
            # Update metrics
            self.metrics["total_workflows_tracked"] += 1
            
            self.logger.info(f"Started tracking workflow '{workflow_id}' with {total_steps} steps")
            
        except Exception as e:
            raise ProgressTrackingException(
                f"Failed to start tracking workflow '{workflow_id}': {str(e)}",
                tracking_info={
                    "workflow_id": workflow_id,
                    "user_id": user_id,
                    "total_steps": total_steps
                },
                correlation_id=self.correlation_id
            )
    
    async def update_workflow_progress(
        self,
        workflow_result: WorkflowExecutionResult,
        phase_result: Optional[PhaseExecutionResult] = None
    ) -> None:
        """
        Update workflow progress with latest results
        
        Args:
            workflow_result: Current workflow execution result
            phase_result: Optional latest phase result
        """
        workflow_id = workflow_result.workflow_id
        
        if workflow_id not in self.active_workflows:
            self.logger.warning(f"Workflow '{workflow_id}' not being tracked")
            return
        
        try:
            snapshot = self.active_workflows[workflow_id]
            
            # Update snapshot
            snapshot.status = workflow_result.status
            snapshot.completed_steps = workflow_result.successful_steps
            snapshot.failed_steps = workflow_result.failed_steps
            snapshot.parallel_efficiency = workflow_result.parallel_efficiency
            snapshot.last_update = time.time()
            
            if phase_result:
                snapshot.current_phase = phase_result.phase_id
            
            # Calculate estimated completion
            if snapshot.completion_percentage > 0 and snapshot.status == WorkflowStatus.RUNNING:
                elapsed = snapshot.elapsed_time
                estimated_total = elapsed / (snapshot.completion_percentage / 100)
                snapshot.estimated_completion = snapshot.start_time + estimated_total
            
            # Create appropriate progress event
            if phase_result:
                if phase_result.status == WorkflowStatus.COMPLETED:
                    event_type = ProgressEventType.PHASE_COMPLETED
                elif phase_result.status == WorkflowStatus.FAILED:
                    event_type = ProgressEventType.PHASE_FAILED
                else:
                    event_type = ProgressEventType.PHASE_STARTED
                
                event = ProgressEvent(
                    event_id=str(uuid.uuid4()),
                    event_type=event_type,
                    workflow_id=workflow_id,
                    timestamp=time.time(),
                    data={
                        "phase_id": phase_result.phase_id,
                        "execution_time": phase_result.execution_time,
                        "step_count": len(phase_result.step_results),
                        "parallel_efficiency": phase_result.parallel_efficiency,
                        "progress_snapshot": snapshot.to_dict()
                    },
                    correlation_id=self.correlation_id,
                    user_id=workflow_result.context.user_id if workflow_result.context else None
                )
                
                await self._emit_event(event)
            
            # Check for milestones
            await self._check_milestones(snapshot, workflow_result)
            
        except Exception as e:
            self.logger.error(f"Failed to update progress for workflow '{workflow_id}': {str(e)}")
    
    async def complete_workflow_tracking(
        self,
        workflow_result: WorkflowExecutionResult
    ) -> None:
        """
        Complete tracking for a finished workflow
        
        Args:
            workflow_result: Final workflow execution result
        """
        workflow_id = workflow_result.workflow_id
        
        if workflow_id not in self.active_workflows:
            self.logger.warning(f"Workflow '{workflow_id}' not being tracked")
            return
        
        try:
            snapshot = self.active_workflows[workflow_id]
            
            # Update final snapshot
            snapshot.status = workflow_result.status
            snapshot.completed_steps = workflow_result.successful_steps
            snapshot.failed_steps = workflow_result.failed_steps
            snapshot.parallel_efficiency = workflow_result.parallel_efficiency
            snapshot.last_update = time.time()
            
            if workflow_result.error_summary:
                snapshot.error_summary = workflow_result.error_summary
            
            # Determine event type
            if workflow_result.status == WorkflowStatus.COMPLETED:
                event_type = ProgressEventType.WORKFLOW_COMPLETED
            elif workflow_result.status == WorkflowStatus.FAILED:
                event_type = ProgressEventType.WORKFLOW_FAILED
            elif workflow_result.status == WorkflowStatus.CANCELLED:
                event_type = ProgressEventType.WORKFLOW_CANCELLED
            else:
                event_type = ProgressEventType.WORKFLOW_COMPLETED
            
            # Create completion event
            event = ProgressEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                workflow_id=workflow_id,
                timestamp=time.time(),
                data={
                    "total_execution_time": workflow_result.total_execution_time,
                    "successful_steps": workflow_result.successful_steps,
                    "failed_steps": workflow_result.failed_steps,
                    "parallel_efficiency": workflow_result.parallel_efficiency,
                    "error_summary": workflow_result.error_summary,
                    "final_snapshot": snapshot.to_dict()
                },
                correlation_id=self.correlation_id,
                user_id=workflow_result.context.user_id if workflow_result.context else None
            )
            
            await self._emit_event(event)
            
            # Update metrics
            self._update_completion_metrics(workflow_result, snapshot)
            
            # Move to completed workflows (optional: implement cleanup strategy)
            # For now, keep in active workflows for recent access
            
            self.logger.info(
                f"Completed tracking workflow '{workflow_id}' - "
                f"Status: {workflow_result.status.value}, "
                f"Duration: {workflow_result.total_execution_time:.2f}s"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to complete tracking for workflow '{workflow_id}': {str(e)}")
    
    async def track_step_event(
        self,
        workflow_id: str,
        step_result: StepExecutionResult,
        event_type: ProgressEventType
    ) -> None:
        """
        Track individual step events
        
        Args:
            workflow_id: Workflow identifier
            step_result: Step execution result
            event_type: Type of step event
        """
        try:
            event = ProgressEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                workflow_id=workflow_id,
                timestamp=time.time(),
                data={
                    "step_id": step_result.step_id,
                    "status": step_result.status.value,
                    "execution_time": step_result.execution_time,
                    "retry_count": step_result.retry_count,
                    "used_fallback": step_result.used_fallback,
                    "circuit_breaker_triggered": step_result.circuit_breaker_triggered,
                    "error": step_result.error
                },
                correlation_id=self.correlation_id
            )
            
            await self._emit_event(event)
            
        except Exception as e:
            self.logger.error(f"Failed to track step event for '{step_result.step_id}': {str(e)}")
    
    async def track_circuit_breaker_event(
        self,
        workflow_id: str,
        server_name: str,
        circuit_breaker_info: Dict[str, Any]
    ) -> None:
        """
        Track circuit breaker events
        
        Args:
            workflow_id: Workflow identifier
            server_name: Server that triggered circuit breaker
            circuit_breaker_info: Circuit breaker state information
        """
        try:
            event = ProgressEvent(
                event_id=str(uuid.uuid4()),
                event_type=ProgressEventType.CIRCUIT_BREAKER_TRIGGERED,
                workflow_id=workflow_id,
                timestamp=time.time(),
                data={
                    "server_name": server_name,
                    "circuit_breaker_state": circuit_breaker_info.get("state"),
                    "failure_count": circuit_breaker_info.get("failure_count"),
                    "last_failure_time": circuit_breaker_info.get("last_failure_time"),
                    "next_attempt_time": circuit_breaker_info.get("next_attempt_time")
                },
                correlation_id=self.correlation_id
            )
            
            await self._emit_event(event)
            
        except Exception as e:
            self.logger.error(f"Failed to track circuit breaker event: {str(e)}")
    
    async def _emit_event(self, event: ProgressEvent) -> None:
        """
        Emit a progress event to all subscribers and notification channels
        
        Args:
            event: Progress event to emit
        """
        try:
            # Store event in history
            if event.workflow_id not in self.event_history:
                self.event_history[event.workflow_id] = []
            self.event_history[event.workflow_id].append(event)
            
            # Update metrics
            self.metrics["total_events_processed"] += 1
            
            # Notify subscribers
            await self._notify_subscribers(event)
            
            # Send notifications based on rules
            await self._send_notifications(event)
            
            # Send to Supabase Realtime (if configured)
            await self._send_realtime_update(event)
            
        except Exception as e:
            self.logger.error(f"Failed to emit event {event.event_id}: {str(e)}")
    
    async def _notify_subscribers(self, event: ProgressEvent) -> None:
        """Notify event subscribers"""
        subscribers = self.event_subscribers.get(event.workflow_id, [])
        
        for subscriber in subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(event)
                else:
                    subscriber(event)
            except Exception as e:
                self.logger.warning(f"Subscriber notification failed: {str(e)}")
    
    async def _send_notifications(self, event: ProgressEvent) -> None:
        """Send notifications based on rules"""
        for rule in self.notification_rules.values():
            if rule.matches_event(event):
                await self._send_rule_notifications(event, rule)
    
    async def _send_rule_notifications(
        self,
        event: ProgressEvent,
        rule: NotificationRule
    ) -> None:
        """Send notifications for a specific rule"""
        try:
            for channel in rule.channels:
                await self._send_channel_notification(event, rule, channel)
                self.metrics["total_notifications_sent"] += 1
                
        except Exception as e:
            self.logger.error(f"Failed to send notifications for rule '{rule.rule_id}': {str(e)}")
    
    async def _send_channel_notification(
        self,
        event: ProgressEvent,
        rule: NotificationRule,
        channel: NotificationChannel
    ) -> None:
        """Send notification to specific channel"""
        # This is a placeholder implementation
        # In a real implementation, you would integrate with actual services
        
        if channel == NotificationChannel.REALTIME:
            # Already handled in _send_realtime_update
            pass
        elif channel == NotificationChannel.WEBHOOK:
            # Send to configured webhook endpoints
            await self._send_webhook_notification(event, rule)
        elif channel == NotificationChannel.EMAIL:
            # Send email notification
            self.logger.info(f"Email notification: {event.event_type.value} for {event.workflow_id}")
        elif channel == NotificationChannel.SLACK:
            # Send Slack notification
            self.logger.info(f"Slack notification: {event.event_type.value} for {event.workflow_id}")
        elif channel == NotificationChannel.WEBSOCKET:
            # Send WebSocket notification
            self.logger.info(f"WebSocket notification: {event.event_type.value} for {event.workflow_id}")
    
    async def _send_webhook_notification(
        self,
        event: ProgressEvent,
        rule: NotificationRule
    ) -> None:
        """Send webhook notification"""
        # Placeholder for webhook implementation
        self.logger.info(f"Webhook notification: {event.event_type.value} for {event.workflow_id}")
    
    async def _send_realtime_update(self, event: ProgressEvent) -> None:
        """Send update to Supabase Realtime"""
        if not self.supabase_url or not self.supabase_key:
            return
        
        try:
            # Placeholder for Supabase Realtime integration
            # In a real implementation, you would use the Supabase client
            self.logger.debug(f"Realtime update: {event.event_type.value} for {event.workflow_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to send realtime update: {str(e)}")
    
    async def _check_milestones(
        self,
        snapshot: ProgressSnapshot,
        workflow_result: WorkflowExecutionResult
    ) -> None:
        """Check and emit milestone events"""
        # Check for percentage milestones
        completion = snapshot.completion_percentage
        
        milestone_percentages = [25, 50, 75, 90]
        for milestone in milestone_percentages:
            if completion >= milestone:
                # Check if we've already emitted this milestone
                milestone_key = f"milestone_{milestone}"
                
                # Simple check - in production, you'd want more sophisticated tracking
                recent_events = self.event_history.get(snapshot.workflow_id, [])[-10:]
                milestone_already_emitted = any(
                    event.event_type == ProgressEventType.MILESTONE_REACHED and
                    event.data.get("milestone_percentage") == milestone
                    for event in recent_events
                )
                
                if not milestone_already_emitted:
                    milestone_event = ProgressEvent(
                        event_id=str(uuid.uuid4()),
                        event_type=ProgressEventType.MILESTONE_REACHED,
                        workflow_id=snapshot.workflow_id,
                        timestamp=time.time(),
                        data={
                            "milestone_percentage": milestone,
                            "completion_percentage": completion,
                            "elapsed_time": snapshot.elapsed_time,
                            "estimated_completion": snapshot.estimated_completion
                        },
                        correlation_id=self.correlation_id,
                        user_id=workflow_result.context.user_id if workflow_result.context else None
                    )
                    
                    await self._emit_event(milestone_event)
    
    def _update_completion_metrics(
        self,
        workflow_result: WorkflowExecutionResult,
        snapshot: ProgressSnapshot
    ) -> None:
        """Update completion metrics"""
        # Update average workflow duration
        current_avg = self.metrics.get("average_workflow_duration", 0.0)
        total_workflows = self.metrics.get("total_workflows_tracked", 1)
        
        new_avg = (current_avg * (total_workflows - 1) + workflow_result.total_execution_time) / total_workflows
        self.metrics["average_workflow_duration"] = new_avg
    
    def add_notification_rule(self, rule: NotificationRule) -> None:
        """Add a notification rule"""
        self.notification_rules[rule.rule_id] = rule
        self.logger.info(f"Added notification rule '{rule.name}'")
    
    def remove_notification_rule(self, rule_id: str) -> bool:
        """Remove a notification rule"""
        if rule_id in self.notification_rules:
            del self.notification_rules[rule_id]
            self.logger.info(f"Removed notification rule '{rule_id}'")
            return True
        return False
    
    def subscribe_to_workflow(
        self,
        workflow_id: str,
        callback: Callable[[ProgressEvent], None]
    ) -> str:
        """
        Subscribe to workflow events
        
        Args:
            workflow_id: Workflow to subscribe to
            callback: Callback function for events
            
        Returns:
            Subscription ID
        """
        if workflow_id not in self.event_subscribers:
            self.event_subscribers[workflow_id] = []
        
        self.event_subscribers[workflow_id].append(callback)
        subscription_id = str(uuid.uuid4())
        
        self.logger.debug(f"Added subscriber for workflow '{workflow_id}'")
        return subscription_id
    
    def get_workflow_progress(self, workflow_id: str) -> Optional[ProgressSnapshot]:
        """Get current progress for a workflow"""
        return self.active_workflows.get(workflow_id)
    
    def get_workflow_events(
        self,
        workflow_id: str,
        event_types: Optional[List[ProgressEventType]] = None,
        limit: Optional[int] = None
    ) -> List[ProgressEvent]:
        """Get events for a workflow"""
        events = self.event_history.get(workflow_id, [])
        
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        
        if limit:
            events = events[-limit:]
        
        return events
    
    def get_tracking_metrics(self) -> Dict[str, Any]:
        """Get tracking performance metrics"""
        uptime = time.time() - self.metrics["start_time"]
        
        return {
            **self.metrics,
            "uptime_seconds": uptime,
            "active_workflows": len(self.active_workflows),
            "notification_rules": len(self.notification_rules),
            "events_per_second": self.metrics["total_events_processed"] / uptime if uptime > 0 else 0
        }
    
    async def cleanup_completed_workflows(self, max_age_hours: int = 24) -> int:
        """
        Cleanup old completed workflows
        
        Args:
            max_age_hours: Maximum age for completed workflows
            
        Returns:
            Number of workflows cleaned up
        """
        cutoff_time = time.time() - (max_age_hours * 3600)
        workflows_to_remove = []
        
        for workflow_id, snapshot in self.active_workflows.items():
            if (snapshot.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED] and
                snapshot.last_update and snapshot.last_update < cutoff_time):
                workflows_to_remove.append(workflow_id)
        
        for workflow_id in workflows_to_remove:
            del self.active_workflows[workflow_id]
            if workflow_id in self.event_history:
                del self.event_history[workflow_id]
            if workflow_id in self.event_subscribers:
                del self.event_subscribers[workflow_id]
        
        self.logger.info(f"Cleaned up {len(workflows_to_remove)} completed workflows")
        return len(workflows_to_remove) 