"""
MORPHEUS CHAT - Plugin Orchestration & Workflow Management
Advanced plugin coordination, execution pipelines, and resource optimization.
"""

import asyncio
import json
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Callable, Union, Tuple
import logging
import uuid
import weakref

from plugin_base import PluginBase, PluginState, PluginContext, PluginMetrics, PluginManifest

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel" 
    PIPELINE = "pipeline"
    GRAPH = "graph"
    REACTIVE = "reactive"


class ExecutionPriority(str, Enum):
    """Execution priority levels, ordered from highest to lowest.

    The iteration order matches dequeue priority — REALTIME dequeues first.
    This fixes D-001 from the defect index where the original ordering was
    inverted (LOW dequeued before REALTIME).
    """
    REALTIME = "realtime"
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


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


class ResourceMonitor:
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
            for priority in ExecutionPriority:
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
                    pass
            return False
    
    def get_queue_stats(self) -> Dict[str, int]:
        return {priority.value: len(queue) for priority, queue in self.queues.items()}


class PluginExecutor:
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_executions: Dict[str, asyncio.Task] = {}
        self.execution_semaphore = asyncio.Semaphore(max_workers)
        
    async def execute_plugin_method(self, plugin: PluginBase, request: ExecutionRequest) -> ExecutionResult:
        start_time = time.time()
        
        try:
            async with self.execution_semaphore:
                if not hasattr(plugin, request.method_name):
                    raise AttributeError(f"Plugin {plugin.plugin_id} has no method {request.method_name}")
                
                method = getattr(plugin, request.method_name)
                
                if asyncio.iscoroutinefunction(method):
                    if request.timeout:
                        result = await asyncio.wait_for(
                            method(*request.args, **request.kwargs),
                            timeout=request.timeout
                        )
                    else:
                        result = await method(*request.args, **request.kwargs)
                else:
                    loop = asyncio.get_event_loop()
                    if request.timeout:
                        result = await asyncio.wait_for(
                            loop.run_in_executor(self.executor, method, *request.args),
                            timeout=request.timeout
                        )
                    else:
                        result = await loop.run_in_executor(self.executor, method, *request.args)
                
                execution_time = time.time() - start_time
                
                return ExecutionResult(
                    request_id=request.request_id,
                    plugin_id=plugin.plugin_id,
                    success=True,
                    result=result,
                    execution_time=execution_time
                )
                
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Plugin execution failed: {plugin.plugin_id}.{request.method_name}: {e}")
            
            return ExecutionResult(
                request_id=request.request_id,
                plugin_id=plugin.plugin_id,
                success=False,
                error=e,
                execution_time=execution_time
            )
    
    def shutdown(self):
        self.executor.shutdown(wait=True, cancel_futures=True)


class WorkflowEngine:
    def __init__(self):
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        self.execution_lock = asyncio.Lock()
        
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
        dependency_graph = workflow.dependencies
        completed_steps = set()
        available_steps = set()
        
        for step_index, step in enumerate(workflow.steps):
            step_id = step.get('id', f'step_{step_index}')
            step_deps = dependency_graph.get(step_id, [])
            
            if not step_deps:
                available_steps.add(step_index)
        
        while available_steps:
            step_index = available_steps.pop()
            step = workflow.steps[step_index]
            step_id = step.get('id', f'step_{step_index}')
            
            try:
                result = await self._execute_step(step, execution)
                execution.results[step_id] = result
                completed_steps.add(step_id)
                
                for next_step_index, next_step in enumerate(workflow.steps):
                    next_step_id = next_step.get('id', f'step_{next_step_index}')
                    next_step_deps = dependency_graph.get(next_step_id, [])
                    
                    if (next_step_id not in completed_steps and 
                        all(dep in completed_steps for dep in next_step_deps)):
                        available_steps.add(next_step_index)
                
            except Exception as e:
                if workflow.error_handling == 'stop':
                    raise
                execution.errors.append(str(e))
    
    async def _execute_reactive(self, workflow: WorkflowDefinition, execution: WorkflowExecution):
        event_handlers = {}
        
        for step_index, step in enumerate(workflow.steps):
            step_id = step.get('id', f'step_{step_index}')
            trigger = step.get('trigger', 'immediate')
            
            if trigger == 'immediate':
                await self._execute_step(step, execution)
            else:
                event_handlers[trigger] = step
        
        execution.context['event_handlers'] = event_handlers
    
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


class PluginOrchestrator:
    def __init__(self, plugin_manager):
        self.plugin_manager = plugin_manager
        self.execution_queue = ExecutionQueue()
        self.executor = PluginExecutor()
        self.workflow_engine = WorkflowEngine()
        self.resource_monitor = ResourceMonitor()
        
        self.is_running = False
        self.worker_tasks: List[asyncio.Task] = []
        self.metrics_task: Optional[asyncio.Task] = None
        
        self.execution_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self.plugin_performance: Dict[str, PluginMetrics] = {}
        
        # Circuit breaker for failing plugins
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
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
        if not await self.execution_queue.enqueue(request):
            return ExecutionResult(
                request_id=request.request_id,
                plugin_id=request.plugin_id,
                success=False,
                error=Exception("Execution queue full")
            )
        
        result_future = asyncio.Future()
        
        def callback(result: ExecutionResult):
            if not result_future.done():
                result_future.set_result(result)
        
        request.callback = callback
        
        try:
            return await result_future
        except asyncio.CancelledError:
            await self.execution_queue.remove(request.request_id)
            raise
    
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
                plugin_id: breaker['state'] 
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
                    
                    cpu_estimate = min(
                        result.execution_time / max(asyncio.get_event_loop().time(), 0.001) * 100.0,
                        100.0,
                    )
                    self.resource_monitor.record_execution(
                        request.plugin_id,
                        result.memory_used,
                        cpu_estimate,
                        result.execution_time,
                    )
                    
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
        
        for callback in self.execution_callbacks[request.plugin_id]:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Plugin callback failed: {e}")
    
    def _is_circuit_breaker_open(self, plugin_id: str) -> bool:
        breaker = self.circuit_breakers.get(plugin_id)
        if not breaker:
            return False
        
        if breaker['state'] == 'open':
            if time.time() - breaker['opened_at'] > breaker['timeout']:
                breaker['state'] = 'half_open'
                breaker['failure_count'] = 0
            else:
                return True
        
        return False
    
    def _record_success(self, plugin_id: str):
        if plugin_id not in self.circuit_breakers:
            self.circuit_breakers[plugin_id] = {
                'state': 'closed',
                'failure_count': 0,
                'threshold': 5,
                'timeout': 60
            }
        
        breaker = self.circuit_breakers[plugin_id]
        
        if breaker['state'] == 'half_open':
            breaker['state'] = 'closed'
            breaker['failure_count'] = 0
        
        breaker['failure_count'] = max(0, breaker['failure_count'] - 1)
    
    def _record_failure(self, plugin_id: str, error: Exception):
        if plugin_id not in self.circuit_breakers:
            self.circuit_breakers[plugin_id] = {
                'state': 'closed',
                'failure_count': 0,
                'threshold': 5,
                'timeout': 60
            }
        
        breaker = self.circuit_breakers[plugin_id]
        breaker['failure_count'] += 1
        
        if breaker['failure_count'] >= breaker['threshold']:
            breaker['state'] = 'open'
            breaker['opened_at'] = time.time()
            logger.warning(f"Circuit breaker opened for plugin {plugin_id} due to {breaker['failure_count']} failures")
    
    async def _metrics_loop(self):
        while self.is_running:
            try:
                await asyncio.sleep(10)
                
                for plugin_id, plugin in self.plugin_manager.active_plugins.items():
                    if hasattr(plugin, 'metrics'):
                        self.plugin_performance[plugin_id] = plugin.metrics
                
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