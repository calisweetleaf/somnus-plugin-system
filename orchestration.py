"""
MORPHEUS CHAT - Plugin Orchestration & Workflow Management
Advanced plugin coordination, execution pipelines, and resource optimization.
"""

import asyncio
import json
import math
import os
import random
import time
import tracemalloc
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Callable, Union, Tuple
import logging
import uuid
import weakref

from plugin_base import (
    PluginBase,
    PluginState,
    PluginContext,
    PluginMetrics,
    PluginManifest,
    current_resident_bytes,
    machine_cpu_percent,
)

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel" 
    PIPELINE = "pipeline"
    GRAPH = "graph"
    REACTIVE = "reactive"


class ExecutionPriority(str, Enum):
    """Execution priority levels.

    Dequeue order is `_PRIORITY_DRAIN_ORDER`, not enum definition order.
    Definition order and drain order both place REALTIME first so a reader
    of the enum and the queue agree. D-001 was an inversion caused by
    iterating the enum while the dict was written in the opposite order.
    """
    REALTIME = "realtime"
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


# Explicit drain order. Independent of Enum member definition order so a
# future reordering of the enum cannot silently invert the queue again.
_PRIORITY_DRAIN_ORDER: Tuple[ExecutionPriority, ...] = (
    ExecutionPriority.REALTIME,
    ExecutionPriority.CRITICAL,
    ExecutionPriority.HIGH,
    ExecutionPriority.NORMAL,
    ExecutionPriority.LOW,
)


class WorkflowState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionRequest:
    request_id: str
    plugin_id: str
    method_name: str
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: ExecutionPriority = ExecutionPriority.NORMAL
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    context: Optional[PluginContext] = None
    dependencies: Set[str] = field(default_factory=set)
    callback: Optional[Callable] = None


@dataclass
class ExecutionResult:
    request_id: str
    plugin_id: str
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    memory_used: int = 0
    cpu_percent: float = 0.0
    limit_violations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class WorkflowDefinition:
    workflow_id: str
    name: str
    description: str
    mode: ExecutionMode
    steps: List[Dict[str, Any]]
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    timeout: Optional[float] = None
    retry_policy: Dict[str, Any] = field(default_factory=dict)
    error_handling: str = "stop"  # stop, continue, retry
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowExecution:
    execution_id: str
    workflow_id: str
    state: WorkflowState
    current_step: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: Dict[str, ExecutionResult] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


class ExecutionResourceMonitor:
    """Per-plugin execution budget tracker.

    Distinct from `plugin_base.ResourceMonitor`, which samples one plugin
    process for the lifecycle engine. This monitor records measurements
    taken around each orchestrated call and enforces the manifest budget
    on the next admission decision.
    """

    def __init__(self):
        self.memory_usage: Dict[str, int] = {}
        self.cpu_usage: Dict[str, float] = {}
        self.execution_times: Dict[str, List[float]] = defaultdict(list)
        self.resource_limits = {
            'memory_mb_per_plugin': 512,
            'cpu_percent_per_plugin': 25.0,
            'max_concurrent_executions': 10
        }
        
    def record_execution(self, plugin_id: str, memory_mb: int, cpu_percent: float, execution_time: float):
        self.memory_usage[plugin_id] = max(self.memory_usage.get(plugin_id, 0), memory_mb)
        self.cpu_usage[plugin_id] = cpu_percent
        self.execution_times[plugin_id].append(execution_time)
        
        if len(self.execution_times[plugin_id]) > 100:
            self.execution_times[plugin_id] = self.execution_times[plugin_id][-100:]
    
    def check_resource_limits(self, plugin_id: str) -> Tuple[bool, List[str]]:
        violations = []
        
        memory_usage = self.memory_usage.get(plugin_id, 0)
        if memory_usage > self.resource_limits['memory_mb_per_plugin']:
            violations.append(f"Memory usage {memory_usage}MB exceeds limit {self.resource_limits['memory_mb_per_plugin']}MB")
        
        cpu_usage = self.cpu_usage.get(plugin_id, 0)
        if cpu_usage > self.resource_limits['cpu_percent_per_plugin']:
            violations.append(f"CPU usage {cpu_usage}% exceeds limit {self.resource_limits['cpu_percent_per_plugin']}%")
        
        return len(violations) == 0, violations

    def check_manifest_budget(
        self,
        plugin_id: str,
        memory_limit_mb: int,
        cpu_limit_percent: float,
    ) -> Tuple[bool, List[str]]:
        """Enforce the plugin manifest's own memory and CPU ceilings."""
        violations: List[str] = []
        memory_usage = self.memory_usage.get(plugin_id, 0)
        if memory_usage > memory_limit_mb:
            violations.append(
                f"Memory usage {memory_usage}MB exceeds manifest limit {memory_limit_mb}MB"
            )
        cpu_usage = self.cpu_usage.get(plugin_id, 0.0)
        if cpu_usage > cpu_limit_percent:
            violations.append(
                f"CPU usage {cpu_usage:.1f}% exceeds manifest limit {cpu_limit_percent}%"
            )
        return len(violations) == 0, violations
    
    def get_performance_metrics(self, plugin_id: str) -> Dict[str, float]:
        execution_times = self.execution_times.get(plugin_id, [])
        if not execution_times:
            return {}
        
        return {
            'avg_execution_time': sum(execution_times) / len(execution_times),
            'min_execution_time': min(execution_times),
            'max_execution_time': max(execution_times),
            'memory_peak_mb': self.memory_usage.get(plugin_id, 0),
            'cpu_usage_percent': self.cpu_usage.get(plugin_id, 0)
        }


class ExecutionQueue:
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.queues = {
            ExecutionPriority.REALTIME: deque(),
            ExecutionPriority.CRITICAL: deque(),
            ExecutionPriority.HIGH: deque(),
            ExecutionPriority.NORMAL: deque(),
            ExecutionPriority.LOW: deque()
        }
        self.pending_requests: Dict[str, ExecutionRequest] = {}
        self.lock = asyncio.Lock()
        
    async def enqueue(self, request: ExecutionRequest) -> bool:
        async with self.lock:
            if len(self.pending_requests) >= self.max_size:
                return False
            
            self.queues[request.priority].append(request)
            self.pending_requests[request.request_id] = request
            return True
    
    async def dequeue(self) -> Optional[ExecutionRequest]:
        async with self.lock:
            for priority in _PRIORITY_DRAIN_ORDER:
                queue = self.queues[priority]
                if queue:
                    request = queue.popleft()
                    self.pending_requests.pop(request.request_id, None)
                    return request
            return None
    
    async def remove(self, request_id: str) -> bool:
        async with self.lock:
            request = self.pending_requests.pop(request_id, None)
            if request:
                try:
                    self.queues[request.priority].remove(request)
                    return True
                except ValueError:
                    # The request was in the pending map and absent from its
                    # deque. Both structures are guarded by this lock, so this
                    # is an accounting inconsistency (double-remove, or a
                    # priority mutation). The pending entry is already gone,
                    # so the request is no longer queued. Surface it; do not
                    # report failure to a caller who would otherwise retry.
                    logger.warning(
                        "Execution queue remove inconsistency for %s "
                        "(priority=%s): pending entry cleared but deque "
                        "did not contain the request",
                        request_id,
                        request.priority.value,
                    )
                    return True
            return False
    
    def get_queue_stats(self) -> Dict[str, int]:
        return {priority.value: len(queue) for priority, queue in self.queues.items()}


def _dependency_cycles(
    step_ids: Set[str], dependencies: Dict[str, List[str]]
) -> List[List[str]]:
    """Return each cycle as a closed list of step ids."""
    cycles: List[List[str]] = []
    visiting: Set[str] = set()
    visited: Set[str] = set()
    stack: List[str] = []

    def walk(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            if node in stack:
                start = stack.index(node)
                cycles.append(stack[start:] + [node])
            return
        visiting.add(node)
        stack.append(node)
        for dep in dependencies.get(node, []):
            if dep in step_ids:
                walk(dep)
        stack.pop()
        visiting.discard(node)
        visited.add(node)

    for step_id in step_ids:
        walk(step_id)
    return cycles


def _resident_bytes() -> int:
    """Current resident set size in bytes. Same reading as the lifecycle monitor."""
    return current_resident_bytes()


def _sample_execution_cost(
    cpu_before: float, rss_before: int, wall_s: float
) -> Tuple[int, float]:
    """Return (memory_used_mb, cpu_percent) for one plugin call."""
    cpu_s = max(0.0, time.process_time() - cpu_before)
    # Share of the whole machine. A call that saturates one core on a 4-core
    # host reports about 25, which is the default per-plugin ceiling, so a
    # quiet call stays admissible and a tighter manifest limit can still trip.
    cpu_percent = machine_cpu_percent(cpu_s, wall_s)
    peak = 0
    if tracemalloc.is_tracing():
        _current, peak = tracemalloc.get_traced_memory()
    rss_delta = max(0, _resident_bytes() - rss_before)
    memory_bytes = max(peak, rss_delta)
    memory_mb = int(math.ceil(memory_bytes / (1024 * 1024))) if memory_bytes else 0
    return memory_mb, round(min(cpu_percent, 100.0), 2)


class PluginExecutor:
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_executions: Dict[str, asyncio.Task] = {}
        self.execution_semaphore = asyncio.Semaphore(max_workers)
        
    async def execute_plugin_method(self, plugin: PluginBase, request: ExecutionRequest) -> ExecutionResult:
        start_time = time.perf_counter()
        cpu_before = time.process_time()
        rss_before = _resident_bytes()
        started_trace = False
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            started_trace = True

        try:
            async with self.execution_semaphore:
                if not hasattr(plugin, request.method_name):
                    raise AttributeError(f"Plugin {plugin.plugin_id} has no method {request.method_name}")

                method = getattr(plugin, request.method_name)

                if asyncio.iscoroutinefunction(method):
                    invocation = method(*request.args, **request.kwargs)
                    if request.timeout:
                        result = await asyncio.wait_for(invocation, timeout=request.timeout)
                    else:
                        result = await invocation
                else:
                    loop = asyncio.get_running_loop()
                    bound = partial(method, *request.args, **request.kwargs)
                    if request.timeout:
                        result = await asyncio.wait_for(
                            loop.run_in_executor(self.executor, bound),
                            timeout=request.timeout,
                        )
                    else:
                        result = await loop.run_in_executor(self.executor, bound)

                execution_time = time.perf_counter() - start_time
                memory_mb, cpu_percent = _sample_execution_cost(
                    cpu_before, rss_before, execution_time
                )

                return ExecutionResult(
                    request_id=request.request_id,
                    plugin_id=plugin.plugin_id,
                    success=True,
                    result=result,
                    execution_time=execution_time,
                    memory_used=memory_mb,
                    cpu_percent=cpu_percent,
                )

        except Exception as e:
            execution_time = time.perf_counter() - start_time
            memory_mb, cpu_percent = _sample_execution_cost(
                cpu_before, rss_before, execution_time
            )
            logger.error(f"Plugin execution failed: {plugin.plugin_id}.{request.method_name}: {e}")

            return ExecutionResult(
                request_id=request.request_id,
                plugin_id=plugin.plugin_id,
                success=False,
                error=e,
                execution_time=execution_time,
                memory_used=memory_mb,
                cpu_percent=cpu_percent,
            )
        finally:
            if started_trace and tracemalloc.is_tracing():
                tracemalloc.stop()
    
    def shutdown(self):
        self.executor.shutdown(wait=True, cancel_futures=True)


class WorkflowEngine:
    def __init__(self):
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        self.execution_lock = asyncio.Lock()
        self._reactive_dispatch: Dict[str, Callable] = {}
        
    def register_workflow(self, workflow: WorkflowDefinition):
        self.workflows[workflow.workflow_id] = workflow
        logger.info(f"Registered workflow: {workflow.name}")
    
    def unregister_workflow(self, workflow_id: str):
        self.workflows.pop(workflow_id, None)
        logger.info(f"Unregistered workflow: {workflow_id}")
    
    async def execute_workflow(self, workflow_id: str, context: Dict[str, Any] = None) -> str:
        if workflow_id not in self.workflows:
            raise ValueError(f"Unknown workflow: {workflow_id}")
        
        workflow = self.workflows[workflow_id]
        execution_id = str(uuid.uuid4())
        
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            state=WorkflowState.PENDING,
            context=context or {}
        )
        
        async with self.execution_lock:
            self.executions[execution_id] = execution
        
        asyncio.create_task(self._execute_workflow_async(execution))
        return execution_id
    
    async def _execute_workflow_async(self, execution: WorkflowExecution):
        workflow = self.workflows[execution.workflow_id]
        execution.state = WorkflowState.RUNNING
        execution.started_at = datetime.now(timezone.utc)
        
        try:
            if workflow.mode == ExecutionMode.SEQUENTIAL:
                await self._execute_sequential(workflow, execution)
            elif workflow.mode == ExecutionMode.PARALLEL:
                await self._execute_parallel(workflow, execution)
            elif workflow.mode == ExecutionMode.PIPELINE:
                await self._execute_pipeline(workflow, execution)
            elif workflow.mode == ExecutionMode.GRAPH:
                await self._execute_graph(workflow, execution)
            elif workflow.mode == ExecutionMode.REACTIVE:
                await self._execute_reactive(workflow, execution)

            if execution.state != WorkflowState.FAILED:
                execution.state = WorkflowState.COMPLETED
            
        except Exception as e:
            execution.state = WorkflowState.FAILED
            execution.errors.append(str(e))
            logger.error(f"Workflow execution failed: {execution.workflow_id}: {e}")
        
        finally:
            execution.completed_at = datetime.now(timezone.utc)
    
    async def _execute_sequential(self, workflow: WorkflowDefinition, execution: WorkflowExecution):
        for step_index, step in enumerate(workflow.steps):
            execution.current_step = step_index
            
            try:
                result = await self._execute_step(step, execution)
                execution.results[step.get('id', f'step_{step_index}')] = result
                
                if not result.success and workflow.error_handling == 'stop':
                    break
                    
            except Exception as e:
                if workflow.error_handling == 'stop':
                    raise
                execution.errors.append(str(e))
    
    async def _execute_parallel(self, workflow: WorkflowDefinition, execution: WorkflowExecution):
        tasks = []
        for step_index, step in enumerate(workflow.steps):
            task = asyncio.create_task(self._execute_step(step, execution))
            tasks.append((step.get('id', f'step_{step_index}'), task))
        
        for step_id, task in tasks:
            try:
                result = await task
                execution.results[step_id] = result
            except Exception as e:
                execution.errors.append(str(e))
                if workflow.error_handling == 'stop':
                    for _, remaining_task in tasks:
                        remaining_task.cancel()
                    raise
    
    async def _execute_pipeline(self, workflow: WorkflowDefinition, execution: WorkflowExecution):
        pipeline_data = execution.context.copy()
        
        for step_index, step in enumerate(workflow.steps):
            execution.current_step = step_index
            step_id = step.get('id', f'step_{step_index}')
            
            try:
                step_with_data = step.copy()
                if 'args' not in step_with_data:
                    step_with_data['args'] = []
                step_with_data['args'].append(pipeline_data)
                
                result = await self._execute_step(step_with_data, execution)
                execution.results[step_id] = result
                
                if result.success and result.result is not None:
                    pipeline_data = result.result
                elif not result.success and workflow.error_handling == 'stop':
                    break
                    
            except Exception as e:
                if workflow.error_handling == 'stop':
                    raise
                execution.errors.append(str(e))
    
    async def _execute_graph(self, workflow: WorkflowDefinition, execution: WorkflowExecution):
        """Execute a dependency graph.

        Steps whose dependencies are satisfied run concurrently. A cycle is
        reported before any step runs. A missing dependency is reported as
        its own error rather than being collapsed into a generic deadlock.
        """
        dependency_graph = workflow.dependencies
        completed_steps: Set[str] = set()
        step_map = {
            step.get('id', f'step_{i}'): (i, step)
            for i, step in enumerate(workflow.steps)
        }
        known = set(step_map)
        missing: List[str] = []
        for step_id, deps in dependency_graph.items():
            for dep in deps:
                if dep not in known:
                    missing.append(f"{step_id}->{dep}")
        if missing:
            execution.errors.append(f"Graph references unknown steps: {missing}")
            execution.state = WorkflowState.FAILED
            return

        cycles = _dependency_cycles(known, dependency_graph)
        if cycles:
            execution.errors.append(f"Cyclic dependency: {cycles}")
            execution.state = WorkflowState.FAILED
            return

        while len(completed_steps) < len(workflow.steps):
            ready: List[Tuple[str, Dict[str, Any]]] = []
            for step_id, (_, step) in step_map.items():
                if step_id in completed_steps:
                    continue
                deps = dependency_graph.get(step_id, [])
                if all(d in completed_steps for d in deps):
                    ready.append((step_id, step))

            if not ready:
                remaining = set(step_map.keys()) - completed_steps
                logger.error(f"Graph deadlock: no ready steps, remaining={remaining}")
                execution.errors.append(f"Graph deadlock on steps: {remaining}")
                break

            async def _run_step(sid: str, sdef: Dict[str, Any]) -> Tuple[str, Optional[ExecutionResult]]:
                try:
                    result = await self._execute_step(sdef, execution)
                    return sid, result
                except Exception as exc:
                    return sid, None

            results = await asyncio.gather(
                *[_run_step(sid, sdef) for sid, sdef in ready]
            )

            for step_id, result in results:
                if result is not None:
                    execution.results[step_id] = result
                    completed_steps.add(step_id)
                    if not result.success and workflow.error_handling == 'stop':
                        return
                else:
                    if workflow.error_handling == 'stop':
                        return
                    completed_steps.add(step_id)
    
    async def _execute_reactive(self, workflow: WorkflowDefinition, execution: WorkflowExecution):
        """Bind triggers to steps and run anything already queued.

        `execution.context['events']` is a list of `{'name', 'payload'}`
        dicts drained during this call. Later events go through
        `dispatch_event`, which invokes every step registered for that
        trigger. Immediate steps run during setup.
        """
        event_handlers: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for step_index, step in enumerate(workflow.steps):
            step_id = step.get('id', f'step_{step_index}')
            trigger = step.get('trigger', 'immediate')

            if trigger == 'immediate':
                result = await self._execute_step(step, execution)
                execution.results[step_id] = result
            else:
                event_handlers[trigger].append(step)

        async def dispatch(event_name: str, payload: Any = None) -> List[ExecutionResult]:
            fired: List[ExecutionResult] = []
            for step in event_handlers.get(event_name, []):
                step_id = step.get('id', event_name)
                step_run = dict(step)
                kwargs = dict(step_run.get('kwargs') or {})
                kwargs['event'] = {'name': event_name, 'payload': payload}
                step_run['kwargs'] = kwargs
                result = await self._execute_step(step_run, execution)
                execution.results[step_id] = result
                fired.append(result)
            execution.context.setdefault('events_dispatched', []).append(event_name)
            return fired

        execution.context['event_handlers'] = {
            trigger: [step.get('id') for step in steps]
            for trigger, steps in event_handlers.items()
        }
        execution.context['dispatch_event'] = dispatch
        self._reactive_dispatch[execution.execution_id] = dispatch

        for event in list(execution.context.get('events') or []):
            if isinstance(event, dict):
                await dispatch(event.get('name', ''), event.get('payload'))
            else:
                await dispatch(str(event), None)

    async def dispatch_event(
        self, execution_id: str, event_name: str, payload: Any = None
    ) -> List[ExecutionResult]:
        """Deliver an event to a reactive workflow that is already bound."""
        dispatch = self._reactive_dispatch.get(execution_id)
        if dispatch is None:
            raise KeyError(f"No reactive dispatch registered for execution {execution_id}")
        return await dispatch(event_name, payload)
    
    async def _execute_step(self, step: Dict[str, Any], execution: WorkflowExecution) -> ExecutionResult:
        plugin_id = step['plugin_id']
        method_name = step['method']
        args = step.get('args', [])
        kwargs = step.get('kwargs', {})
        
        request = ExecutionRequest(
            request_id=str(uuid.uuid4()),
            plugin_id=plugin_id,
            method_name=method_name,
            args=args,
            kwargs=kwargs,
            timeout=step.get('timeout')
        )
        
        return await self._orchestrator.execute_plugin_request(request)
    
    def get_execution_status(self, execution_id: str) -> Optional[WorkflowExecution]:
        return self.executions.get(execution_id)
    
    def cancel_execution(self, execution_id: str) -> bool:
        execution = self.executions.get(execution_id)
        if execution and execution.state == WorkflowState.RUNNING:
            execution.state = WorkflowState.CANCELLED
            return True
        return False


class CircuitBreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker with exponential backoff and decorrelated jitter.

    Implements the three-state circuit breaker pattern:
    - CLOSED: requests flow normally, failures are counted
    - OPEN: requests are rejected, backoff timer runs with exponential increase
    - HALF_OPEN: a single probe request is allowed to test recovery

    The backoff uses decorrelated jitter (AWS-style) to prevent thundering herd
    when multiple plugins recover simultaneously:
        sleep = min(cap, random(base, sleep * 3))
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        base_timeout_s: float = 10.0,
        max_timeout_s: float = 300.0,
        success_threshold: int = 3,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.base_timeout_s = base_timeout_s
        self.max_timeout_s = max_timeout_s
        self.success_threshold = success_threshold

        self.state = CircuitBreakerState.CLOSED
        self.failure_count: int = 0
        self.success_count: int = 0
        self.last_failure_time: float = 0.0
        self._current_timeout: float = base_timeout_s
        self._consecutive_opens: int = 0

    @property
    def is_open(self) -> bool:
        if self.state == CircuitBreakerState.OPEN:
            if time.monotonic() - self.last_failure_time >= self._current_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                return False
            return True
        return False

    def record_success(self) -> None:
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self._consecutive_opens = 0
                self._current_timeout = self.base_timeout_s
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()

        if self.state == CircuitBreakerState.HALF_OPEN:
            self._trip()
        elif self.failure_count >= self.failure_threshold:
            self._trip()

    def _trip(self) -> None:
        """Open the circuit with exponential backoff and decorrelated jitter."""
        self.state = CircuitBreakerState.OPEN
        self._consecutive_opens += 1
        exp_timeout = self.base_timeout_s * (2 ** self._consecutive_opens)
        jittered = random.uniform(self.base_timeout_s, min(exp_timeout, self.max_timeout_s))
        self._current_timeout = jittered
        logger.warning(
            f"Circuit breaker tripped (failures={self.failure_count}, "
            f"timeout={self._current_timeout:.1f}s)"
        )

    def snapshot(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "current_timeout_s": round(self._current_timeout, 2),
            "consecutive_opens": self._consecutive_opens,
        }


class PluginOrchestrator:
    def __init__(self, plugin_manager):
        self.plugin_manager = plugin_manager
        self.execution_queue = ExecutionQueue()
        self.executor = PluginExecutor()
        self.workflow_engine = WorkflowEngine()
        self.resource_monitor = ExecutionResourceMonitor()
        
        self.is_running = False
        self.worker_tasks: List[asyncio.Task] = []
        self.metrics_task: Optional[asyncio.Task] = None
        
        self.execution_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self.plugin_performance: Dict[str, PluginMetrics] = {}
        
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Workflow engine reference
        self.workflow_engine._orchestrator = self
    
    async def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        
        worker_count = min(self.executor.max_workers, 5)
        for i in range(worker_count):
            task = asyncio.create_task(self._worker_loop(f"worker_{i}"))
            self.worker_tasks.append(task)
        
        self.metrics_task = asyncio.create_task(self._metrics_loop())
        
        logger.info(f"Plugin orchestrator started with {worker_count} workers")
    
    async def stop(self):
        if not self.is_running:
            return
        
        self.is_running = False
        
        for task in self.worker_tasks:
            task.cancel()
        
        if self.metrics_task:
            self.metrics_task.cancel()
        
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        
        if self.metrics_task:
            await asyncio.gather(self.metrics_task, return_exceptions=True)
        
        self.executor.shutdown()
        logger.info("Plugin orchestrator stopped")
    
    async def execute_plugin_request(self, request: ExecutionRequest) -> ExecutionResult:
        loop = asyncio.get_running_loop()
        result_future: asyncio.Future = loop.create_future()

        def callback(result: ExecutionResult) -> None:
            if not result_future.done():
                result_future.set_result(result)

        # Bind the completion path before the request is visible to a worker.
        # Assigning the callback after enqueue loses the race: the worker can
        # dequeue during the await boundary and observe callback is None,
        # which drops the result and leaves this future pending forever.
        request.callback = callback

        if not await self.execution_queue.enqueue(request):
            return ExecutionResult(
                request_id=request.request_id,
                plugin_id=request.plugin_id,
                success=False,
                error=Exception("Execution queue full")
            )

        try:
            if request.timeout:
                return await asyncio.wait_for(result_future, timeout=request.timeout)
            return await result_future
        except asyncio.CancelledError:
            await self.execution_queue.remove(request.request_id)
            raise
        except asyncio.TimeoutError:
            await self.execution_queue.remove(request.request_id)
            return ExecutionResult(
                request_id=request.request_id,
                plugin_id=request.plugin_id,
                success=False,
                error=TimeoutError(
                    f"Plugin request {request.request_id} exceeded {request.timeout}s"
                ),
            )
    
    async def execute_plugin_method(self, plugin_id: str, method_name: str, *args, **kwargs) -> ExecutionResult:
        request = ExecutionRequest(
            request_id=str(uuid.uuid4()),
            plugin_id=plugin_id,
            method_name=method_name,
            args=list(args),
            kwargs=kwargs
        )
        
        return await self.execute_plugin_request(request)
    
    async def execute_workflow(self, workflow_id: str, context: Dict[str, Any] = None) -> str:
        return await self.workflow_engine.execute_workflow(workflow_id, context)
    
    def register_workflow(self, workflow: WorkflowDefinition):
        self.workflow_engine.register_workflow(workflow)
    
    def register_execution_callback(self, plugin_id: str, callback: Callable[[ExecutionResult], None]):
        self.execution_callbacks[plugin_id].append(callback)
    
    def get_plugin_performance(self, plugin_id: str) -> Optional[PluginMetrics]:
        return self.plugin_performance.get(plugin_id)
    
    def get_orchestrator_stats(self) -> Dict[str, Any]:
        return {
            'queue_stats': self.execution_queue.get_queue_stats(),
            'active_executions': len(self.executor.active_executions),
            'total_plugins': len(self.plugin_manager.active_plugins),
            'worker_count': len(self.worker_tasks),
            'resource_monitor': {
                'memory_usage': dict(self.resource_monitor.memory_usage),
                'cpu_usage': dict(self.resource_monitor.cpu_usage)
            },
            'circuit_breakers': {
                plugin_id: breaker.snapshot()
                for plugin_id, breaker in self.circuit_breakers.items()
            }
        }
    
    async def _worker_loop(self, worker_name: str):
        logger.debug(f"Starting worker: {worker_name}")
        
        while self.is_running:
            try:
                request = await self.execution_queue.dequeue()
                
                if not request:
                    await asyncio.sleep(0.1)
                    continue
                
                await self._process_request(request)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                await asyncio.sleep(1)
        
        logger.debug(f"Worker {worker_name} stopped")
    
    async def _process_request(self, request: ExecutionRequest):
        plugin = self.plugin_manager.active_plugins.get(request.plugin_id)
        
        if not plugin:
            result = ExecutionResult(
                request_id=request.request_id,
                plugin_id=request.plugin_id,
                success=False,
                error=Exception(f"Plugin {request.plugin_id} not found or not active")
            )
        elif self._is_circuit_breaker_open(request.plugin_id):
            result = ExecutionResult(
                request_id=request.request_id,
                plugin_id=request.plugin_id,
                success=False,
                error=Exception(f"Plugin {request.plugin_id} circuit breaker is open")
            )
        else:
            within_limits, violations = self.resource_monitor.check_resource_limits(request.plugin_id)
            manifest = getattr(plugin, "manifest", None)
            if manifest is not None:
                budget_ok, budget_violations = self.resource_monitor.check_manifest_budget(
                    request.plugin_id,
                    int(manifest.memory_limit_mb),
                    float(manifest.cpu_limit_percent),
                )
                if not budget_ok:
                    within_limits = False
                    violations.extend(budget_violations)
                    logger.warning(
                        "Refusing %s.%s: %s",
                        request.plugin_id,
                        request.method_name,
                        budget_violations,
                    )

            if not within_limits:
                result = ExecutionResult(
                    request_id=request.request_id,
                    plugin_id=request.plugin_id,
                    success=False,
                    error=Exception(f"Resource limits exceeded: {violations}")
                )
            else:
                try:
                    result = await self.executor.execute_plugin_method(plugin, request)

                    if result.success:
                        self._record_success(request.plugin_id)
                    else:
                        self._record_failure(request.plugin_id, result.error)

                    self.resource_monitor.record_execution(
                        request.plugin_id,
                        result.memory_used,
                        result.cpu_percent,
                        result.execution_time,
                    )
                    if manifest is not None:
                        within_budget, budget_violations = (
                            self.resource_monitor.check_manifest_budget(
                                request.plugin_id,
                                int(manifest.memory_limit_mb),
                                float(manifest.cpu_limit_percent),
                            )
                        )
                        if not within_budget:
                            result.limit_violations.extend(budget_violations)
                            logger.warning(
                                "Plugin %s exceeded manifest budget: %s",
                                request.plugin_id,
                                budget_violations,
                            )

                    self._record_plugin_metrics(plugin, result)

                except Exception as e:
                    result = ExecutionResult(
                        request_id=request.request_id,
                        plugin_id=request.plugin_id,
                        success=False,
                        error=e
                    )
                    self._record_failure(request.plugin_id, e)
        
        if request.callback:
            try:
                request.callback(result)
            except Exception as e:
                logger.error(f"Callback execution failed: {e}")
        else:
            logger.error(
                "Request %s finished with no callback; the awaiting caller "
                "would hang if the callback was bound after enqueue",
                request.request_id,
            )
        
        for callback in self.execution_callbacks[request.plugin_id]:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Plugin callback failed: {e}")
    
    def _record_plugin_metrics(self, plugin: Any, result: ExecutionResult) -> None:
        """Update canonical PluginMetrics from a finished call.

        Plugins loaded through the canonical base already own a metrics
        object. A plugin that does not is given one here so the metrics
        loop has a real object to read instead of skipping the plugin.
        """
        metrics = getattr(plugin, "metrics", None)
        if metrics is None:
            metrics = PluginMetrics()
            setattr(plugin, "metrics", metrics)
        if hasattr(metrics, "record_execution"):
            metrics.record_execution(
                result.execution_time,
                max(0, result.memory_used) * 1024 * 1024,
            )
            if not result.success and hasattr(metrics, "record_error"):
                metrics.record_error()
        self.plugin_performance[plugin.plugin_id] = metrics

    def _get_circuit_breaker(self, plugin_id: str) -> CircuitBreaker:
        if plugin_id not in self.circuit_breakers:
            self.circuit_breakers[plugin_id] = CircuitBreaker()
        return self.circuit_breakers[plugin_id]

    def _is_circuit_breaker_open(self, plugin_id: str) -> bool:
        return self._get_circuit_breaker(plugin_id).is_open

    def _record_success(self, plugin_id: str) -> None:
        self._get_circuit_breaker(plugin_id).record_success()

    def _record_failure(self, plugin_id: str, error: Exception) -> None:
        breaker = self._get_circuit_breaker(plugin_id)
        breaker.record_failure()
        if breaker.state == CircuitBreakerState.OPEN:
            logger.warning(
                f"Circuit breaker opened for plugin {plugin_id}: "
                f"{breaker.failure_count} failures, "
                f"timeout={breaker._current_timeout:.1f}s"
            )
    
    async def _metrics_loop(self):
        while self.is_running:
            try:
                await asyncio.sleep(10)
                
                for plugin_id, plugin in self.plugin_manager.active_plugins.items():
                    metrics = getattr(plugin, "metrics", None)
                    if metrics is None:
                        metrics = PluginMetrics()
                        setattr(plugin, "metrics", metrics)
                    self.plugin_performance[plugin_id] = metrics
                
                performance_metrics = self.resource_monitor.get_performance_metrics
                for plugin_id in list(self.plugin_performance.keys()):
                    metrics = performance_metrics(plugin_id)
                    if metrics and plugin_id in self.plugin_performance:
                        plugin_metrics = self.plugin_performance[plugin_id]
                        plugin_metrics.execution_count = len(self.resource_monitor.execution_times.get(plugin_id, []))
                        plugin_metrics.total_execution_time = sum(self.resource_monitor.execution_times.get(plugin_id, []))
                        plugin_metrics.memory_usage_peak = metrics.get('memory_peak_mb', 0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics loop error: {e}")


async def create_orchestrator(plugin_manager) -> PluginOrchestrator:
    orchestrator = PluginOrchestrator(plugin_manager)
    await orchestrator.start()
    return orchestrator