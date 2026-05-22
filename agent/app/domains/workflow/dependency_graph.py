"""
Dependency Graph Builder for Parallel Workflow Execution

This module provides dependency analysis and parallel execution planning for MCP workflows.
It analyzes workflow steps, identifies dependencies, and optimizes execution order for maximum
parallelism while respecting dependency constraints.

Key Features:
- Workflow step dependency analysis
- Dependency graph construction and validation
- Parallel execution planning with phase identification
- Context variable tracking and resolution
- Execution time estimation and optimization
- Comprehensive error handling with custom exceptions
"""

import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Tuple, Union
from datetime import datetime

from app.shared.exceptions import (
    ValidationException,
    NotFoundException,
    ConfigurationException,
    ErrorSeverity
)


class ExecutionMode(Enum):
    """Execution modes for workflow steps"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    PIPELINE = "pipeline"


class StepStatus(Enum):
    """Status of workflow steps"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ContextVariable:
    """Represents a context variable used in workflow execution"""
    name: str
    value: Any = None
    source_step: Optional[str] = None
    required: bool = True
    data_type: str = "any"
    description: Optional[str] = None


@dataclass
class WorkflowStep:
    """Represents a single step in a workflow with dependencies"""
    step_id: str
    tool_name: str
    server_name: str
    parameters: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    timeout: float = 30.0
    max_retries: int = 3
    priority: int = 0  # Higher priority = earlier execution
    
    # Context management
    input_variables: List[str] = field(default_factory=list)
    output_variables: List[str] = field(default_factory=list)
    
    # Execution metadata
    estimated_duration: float = 5.0
    status: StepStatus = StepStatus.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if not self.step_id:
            raise ValidationException("Step ID is required")
        if not self.tool_name:
            raise ValidationException("Tool name is required")
        if not self.server_name:
            raise ValidationException("Server name is required")


@dataclass
class ExecutionPhase:
    """Represents a phase of parallel execution"""
    phase_id: int
    steps: List[str]
    mode: ExecutionMode = ExecutionMode.PARALLEL
    estimated_duration: float = 0.0
    dependencies_resolved: bool = False
    
    def __post_init__(self):
        # Calculate estimated duration as max of all steps in phase
        if hasattr(self, '_step_durations'):
            self.estimated_duration = max(
                self._step_durations.get(step_id, 5.0) for step_id in self.steps
            ) if self.steps else 0.0


class DependencyGraphException(ValidationException):
    """Exception for dependency graph related errors"""
    
    def __init__(
        self,
        message: str,
        graph_info: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        enhanced_details = graph_info or {}
        enhanced_details["component"] = "dependency_graph"
        
        super().__init__(
            message=message,
            correlation_id=correlation_id,
            details=enhanced_details,
            severity=ErrorSeverity.HIGH
        )


class DependencyGraphBuilder:
    """
    Builds and analyzes dependency graphs for parallel workflow execution
    
    This class provides comprehensive dependency analysis for workflow steps,
    including cycle detection, topological sorting, and parallel execution
    phase planning. It optimizes workflow execution by identifying steps
    that can run in parallel while respecting dependency constraints.
    
    Features:
    - Dependency graph construction and validation
    - Cycle detection and resolution
    - Topological sorting for execution order
    - Parallel execution phase identification
    - Context variable dependency tracking
    - Execution time estimation and optimization
    """
    
    def __init__(self, correlation_id: Optional[str] = None):
        """
        Initialize the Dependency Graph Builder
        
        Args:
            correlation_id: Request correlation ID for tracking
        """
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.logger = logging.getLogger(__name__)
        
        # Graph data structures
        self.steps: Dict[str, WorkflowStep] = {}
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)
        self.context_variables: Dict[str, ContextVariable] = {}
        
        # Execution planning
        self.execution_phases: List[ExecutionPhase] = []
        self.topological_order: List[str] = []
        
        # Analysis results
        self.has_cycles: bool = False
        self.cycle_paths: List[List[str]] = []
        self.critical_path: List[str] = []
        self.total_estimated_time: float = 0.0
        self.parallel_efficiency: float = 0.0
    
    def add_step(self, step: WorkflowStep) -> None:
        """
        Add a workflow step to the dependency graph
        
        Args:
            step: Workflow step to add
            
        Raises:
            ValidationException: If step is invalid or already exists
        """
        if step.step_id in self.steps:
            raise ValidationException(
                f"Step '{step.step_id}' already exists",
                correlation_id=self.correlation_id,
                details={"existing_steps": list(self.steps.keys())}
            )
        
        # Validate step configuration
        if step.timeout <= 0:
            raise ValidationException(
                f"Step '{step.step_id}' timeout must be positive",
                correlation_id=self.correlation_id
            )
        
        if step.max_retries < 0:
            raise ValidationException(
                f"Step '{step.step_id}' max_retries cannot be negative",
                correlation_id=self.correlation_id
            )
        
        # Add step to graph
        self.steps[step.step_id] = step
        
        # Build dependency relationships
        for dependency in step.dependencies:
            if dependency == step.step_id:
                raise ValidationException(
                    f"Step '{step.step_id}' cannot depend on itself",
                    correlation_id=self.correlation_id
                )
            
            self.dependency_graph[dependency].add(step.step_id)
            self.reverse_graph[step.step_id].add(dependency)
        
        # Initialize nodes without dependencies
        if step.step_id not in self.dependency_graph:
            self.dependency_graph[step.step_id] = set()
        if step.step_id not in self.reverse_graph:
            self.reverse_graph[step.step_id] = set()
        
        # Track context variables
        self._track_context_variables(step)
        
        self.logger.debug(f"Added step '{step.step_id}' with dependencies: {step.dependencies}")
    
    def _track_context_variables(self, step: WorkflowStep) -> None:
        """Track context variables defined and used by a step"""
        # Track input variables
        for var_name in step.input_variables:
            if var_name not in self.context_variables:
                self.context_variables[var_name] = ContextVariable(
                    name=var_name,
                    required=True,
                    description=f"Input variable for step {step.step_id}"
                )
        
        # Track output variables
        for var_name in step.output_variables:
            self.context_variables[var_name] = ContextVariable(
                name=var_name,
                source_step=step.step_id,
                required=False,
                description=f"Output variable from step {step.step_id}"
            )
    
    def remove_step(self, step_id: str) -> None:
        """
        Remove a workflow step from the dependency graph
        
        Args:
            step_id: ID of step to remove
            
        Raises:
            NotFoundException: If step doesn't exist
        """
        if step_id not in self.steps:
            raise NotFoundException(
                f"Step '{step_id}' not found",
                correlation_id=self.correlation_id,
                details={"available_steps": list(self.steps.keys())}
            )
        
        # Remove from steps
        del self.steps[step_id]
        
        # Remove from dependency graph
        if step_id in self.dependency_graph:
            del self.dependency_graph[step_id]
        
        # Remove references from reverse graph
        if step_id in self.reverse_graph:
            del self.reverse_graph[step_id]
        
        # Remove dependencies on this step from other steps
        for dependent_steps in self.dependency_graph.values():
            dependent_steps.discard(step_id)
        
        for step_deps in self.reverse_graph.values():
            step_deps.discard(step_id)
        
        self.logger.debug(f"Removed step '{step_id}' from dependency graph")
    
    def validate_dependencies(self) -> Dict[str, Any]:
        """
        Validate all dependencies in the graph
        
        Returns:
            Validation results with any issues found
            
        Raises:
            DependencyGraphException: If critical validation errors found
        """
        issues = []
        warnings = []
        
        # Check for undefined dependencies
        undefined_deps = set()
        for step_id, step in self.steps.items():
            for dep in step.dependencies:
                if dep not in self.steps:
                    undefined_deps.add(dep)
                    issues.append(f"Step '{step_id}' depends on undefined step '{dep}'")
        
        if undefined_deps:
            raise DependencyGraphException(
                f"Found undefined dependencies: {list(undefined_deps)}",
                graph_info={
                    "undefined_dependencies": list(undefined_deps),
                    "total_steps": len(self.steps)
                },
                correlation_id=self.correlation_id
            )
        
        # Check for context variable dependencies
        for step_id, step in self.steps.items():
            for var_name in step.input_variables:
                if var_name not in self.context_variables:
                    warnings.append(f"Step '{step_id}' uses undefined variable '{var_name}'")
                elif self.context_variables[var_name].source_step:
                    # Check if the source step is a dependency
                    source_step = self.context_variables[var_name].source_step
                    if source_step not in step.dependencies:
                        warnings.append(
                            f"Step '{step_id}' uses variable '{var_name}' from '{source_step}' "
                            f"but doesn't declare it as a dependency"
                        )
        
        # Detect cycles
        self.has_cycles, self.cycle_paths = self._detect_cycles()
        if self.has_cycles:
            raise DependencyGraphException(
                f"Dependency cycles detected: {self.cycle_paths}",
                graph_info={
                    "cycles": self.cycle_paths,
                    "affected_steps": set().union(*self.cycle_paths) if self.cycle_paths else set()
                },
                correlation_id=self.correlation_id
            )
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "total_steps": len(self.steps),
            "has_cycles": self.has_cycles,
            "validation_time": datetime.utcnow().isoformat()
        }
    
    def _detect_cycles(self) -> Tuple[bool, List[List[str]]]:
        """Detect cycles in the dependency graph using DFS"""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {step_id: WHITE for step_id in self.steps}
        cycles = []
        
        def dfs_visit(node: str, path: List[str]) -> bool:
            color[node] = GRAY
            path.append(node)
            
            for neighbor in self.dependency_graph[node]:
                if color[neighbor] == GRAY:
                    # Found a back edge - cycle detected
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
                    return True
                elif color[neighbor] == WHITE:
                    if dfs_visit(neighbor, path.copy()):
                        return True
            
            color[node] = BLACK
            return False
        
        for step_id in self.steps:
            if color[step_id] == WHITE:
                if dfs_visit(step_id, []):
                    break
        
        return len(cycles) > 0, cycles
    
    def build_execution_plan(self) -> List[ExecutionPhase]:
        """
        Build optimized execution plan with parallel phases
        
        Returns:
            List of execution phases with steps that can run in parallel
            
        Raises:
            DependencyGraphException: If graph is invalid
        """
        # Validate dependencies first
        validation_result = self.validate_dependencies()
        if not validation_result["valid"]:
            raise DependencyGraphException(
                "Cannot build execution plan: graph validation failed",
                graph_info=validation_result,
                correlation_id=self.correlation_id
            )
        
        # Build topological order
        self.topological_order = self._topological_sort()
        
        # Group steps into parallel execution phases
        self.execution_phases = self._build_parallel_phases()
        
        # Calculate critical path and timing estimates
        self._calculate_critical_path()
        self._calculate_execution_metrics()
        
        self.logger.info(
            f"Built execution plan with {len(self.execution_phases)} phases "
            f"for {len(self.steps)} steps"
        )
        
        return self.execution_phases
    
    def _topological_sort(self) -> List[str]:
        """Perform topological sort using Kahn's algorithm"""
        in_degree = {step_id: len(self.reverse_graph[step_id]) for step_id in self.steps}
        queue = deque([step_id for step_id, degree in in_degree.items() if degree == 0])
        result = []
        
        while queue:
            # Sort by priority for deterministic ordering
            current_level = []
            while queue:
                current_level.append(queue.popleft())
            
            # Sort by priority (higher priority first) then by step_id for determinism
            current_level.sort(key=lambda x: (-self.steps[x].priority, x))
            
            for step_id in current_level:
                result.append(step_id)
                
                # Reduce in-degree of dependent steps
                for dependent in self.dependency_graph[step_id]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        
        if len(result) != len(self.steps):
            missing_steps = set(self.steps.keys()) - set(result)
            raise DependencyGraphException(
                f"Topological sort failed: missing steps {missing_steps}",
                correlation_id=self.correlation_id
            )
        
        return result
    
    def _build_parallel_phases(self) -> List[ExecutionPhase]:
        """Build execution phases where steps can run in parallel"""
        phases = []
        processed = set()
        step_durations = {step_id: step.estimated_duration for step_id, step in self.steps.items()}
        
        phase_id = 0
        while len(processed) < len(self.steps):
            # Find all steps that can run in this phase
            ready_steps = []
            
            for step_id in self.topological_order:
                if step_id in processed:
                    continue
                
                # Check if all dependencies are satisfied
                dependencies_satisfied = all(
                    dep in processed for dep in self.reverse_graph[step_id]
                )
                
                if dependencies_satisfied:
                    ready_steps.append(step_id)
            
            if not ready_steps:
                remaining_steps = set(self.steps.keys()) - processed
                raise DependencyGraphException(
                    f"Cannot find ready steps. Remaining: {remaining_steps}",
                    correlation_id=self.correlation_id
                )
            
            # Determine execution mode for this phase
            mode = ExecutionMode.PARALLEL if len(ready_steps) > 1 else ExecutionMode.SEQUENTIAL
            
            # Create execution phase
            phase = ExecutionPhase(
                phase_id=phase_id,
                steps=ready_steps,
                mode=mode,
                dependencies_resolved=True
            )
            phase._step_durations = step_durations
            phase.__post_init__()  # Calculate estimated duration
            
            phases.append(phase)
            processed.update(ready_steps)
            phase_id += 1
        
        return phases
    
    def _calculate_critical_path(self) -> None:
        """Calculate the critical path through the workflow"""
        # Find the critical path (longest path through the graph)
        def find_longest_path(step_id: str, visited: Set[str]) -> Tuple[float, List[str]]:
            if step_id in visited:
                return 0.0, []
            
            visited.add(step_id)
            step = self.steps[step_id]
            
            max_length = 0.0
            best_path = []
            
            for dependent in self.dependency_graph[step_id]:
                length, path = find_longest_path(dependent, visited.copy())
                if length > max_length:
                    max_length = length
                    best_path = path
            
            return step.estimated_duration + max_length, [step_id] + best_path
        
        # Find the critical path starting from steps with no dependencies
        max_critical_length = 0.0
        best_critical_path = []
        
        for step_id in self.steps:
            if not self.reverse_graph[step_id]:  # No dependencies
                length, path = find_longest_path(step_id, set())
                if length > max_critical_length:
                    max_critical_length = length
                    best_critical_path = path
        
        self.critical_path = best_critical_path
        self.total_estimated_time = max_critical_length
    
    def _calculate_execution_metrics(self) -> None:
        """Calculate execution efficiency metrics"""
        if not self.execution_phases:
            return
        
        # Calculate sequential execution time
        sequential_time = sum(step.estimated_duration for step in self.steps.values())
        
        # Calculate parallel execution time (sum of phase durations)
        parallel_time = sum(phase.estimated_duration for phase in self.execution_phases)
        
        # Calculate efficiency
        self.parallel_efficiency = (
            (sequential_time - parallel_time) / sequential_time * 100
            if sequential_time > 0 else 0.0
        )
        
        self.logger.info(
            f"Execution metrics: Sequential={sequential_time:.1f}s, "
            f"Parallel={parallel_time:.1f}s, Efficiency={self.parallel_efficiency:.1f}%"
        )
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get comprehensive execution plan summary"""
        return {
            "plan_info": {
                "total_steps": len(self.steps),
                "execution_phases": len(self.execution_phases),
                "has_cycles": self.has_cycles,
                "total_estimated_time": self.total_estimated_time,
                "parallel_efficiency": self.parallel_efficiency
            },
            "critical_path": {
                "steps": self.critical_path,
                "duration": self.total_estimated_time
            },
            "execution_phases": [
                {
                    "phase_id": phase.phase_id,
                    "steps": phase.steps,
                    "mode": phase.mode.value,
                    "estimated_duration": phase.estimated_duration,
                    "step_count": len(phase.steps)
                }
                for phase in self.execution_phases
            ],
            "generation_time": datetime.utcnow().isoformat(),
            "correlation_id": self.correlation_id
        }
    
    def visualize_graph(self) -> str:
        """
        Create a text-based visualization of the dependency graph
        
        Returns:
            String representation of the graph
        """
        lines = ["Dependency Graph Visualization:", "=" * 40]
        
        # Show execution phases
        for phase in self.execution_phases:
            lines.append(f"\nPhase {phase.phase_id} ({phase.mode.value}):")
            for step_id in phase.steps:
                step = self.steps[step_id]
                deps = ", ".join(self.reverse_graph[step_id]) if self.reverse_graph[step_id] else "None"
                lines.append(f"  └─ {step_id} ({step.tool_name}) [deps: {deps}]")
        
        # Show critical path
        if self.critical_path:
            lines.append(f"\nCritical Path ({self.total_estimated_time:.1f}s):")
            lines.append("  " + " → ".join(self.critical_path))
        
        return "\n".join(lines) 