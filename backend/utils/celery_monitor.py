"""
Comprehensive Celery monitoring and health check system.

This module provides real-time monitoring, alerting, and automatic
remediation for Celery task queues and worker processes.
"""

import os
import time
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from enum import Enum

# Celery monitoring imports
try:
    from celery import Celery
    from celery.bin.control import inspect
    from backend.celery_app import celery_app
except ImportError:
    celery_app = None

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class WorkerMetrics:
    """Worker performance metrics."""
    worker_name: str
    active_tasks: int = 0
    scheduled_tasks: int = 0
    reserved_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    last_heartbeat: Optional[datetime] = None
    uptime: Optional[timedelta] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None

@dataclass
class TaskMetrics:
    """Task performance metrics."""
    task_name: str
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    min_execution_time: float = 0.0
    max_execution_time: float = 0.0
    sla_violations: int = 0
    last_execution: Optional[datetime] = None

@dataclass
class QueueMetrics:
    """Queue performance metrics."""
    queue_name: str
    pending_tasks: int = 0
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    average_wait_time: float = 0.0
    max_wait_time: float = 0.0

@dataclass
class Alert:
    """System alert."""
    id: str
    level: AlertLevel
    message: str
    timestamp: datetime
    source: str
    resolved: bool = False
    resolved_at: Optional[datetime] = None

class CeleryMonitor:
    """
    Comprehensive Celery monitoring system.
    
    Features:
    - Real-time worker health monitoring
    - Task queue status tracking
    - Performance metrics collection
    - SLA compliance monitoring
    - Automatic alerting system
    - Automatic worker restart
    """
    
    def __init__(self, 
                 sla_threshold: float = 60.0,  # 60 seconds SLA
                 alert_threshold: int = 5,
                 check_interval: int = 30,
                 history_size: int = 1000):
        
        self.sla_threshold = sla_threshold
        self.alert_threshold = alert_threshold
        self.check_interval = check_interval
        self.history_size = history_size
        
        # Metrics storage
        self.worker_metrics: Dict[str, WorkerMetrics] = {}
        self.task_metrics: Dict[str, TaskMetrics] = defaultdict(lambda: TaskMetrics(task_name=""))
        self.queue_metrics: Dict[str, QueueMetrics] = {}
        
        # Alert system
        self.alerts: deque = deque(maxlen=history_size)
        self.alert_handlers: List[Callable[[Alert], None]] = []
        
        # Performance history
        self.performance_history: deque = deque(maxlen=history_size)
        
        # Threading
        self._monitoring_thread: Optional[threading.Thread] = None
        self._monitoring_active = False
        self._lock = threading.Lock()
        
        # State tracking
        self.worker_restart_counts: Dict[str, int] = defaultdict(int)
        self.last_worker_check: Dict[str, datetime] = {}
        
        logger.info("🔍 Celery Monitor initialized")
        logger.info(f"   SLA Threshold: {self.sla_threshold}s")
        logger.info(f"   Alert Threshold: {self.alert_threshold}")
        logger.info(f"   Check Interval: {self.check_interval}s")
    
    def start_monitoring(self):
        """Start the monitoring system."""
        if self._monitoring_active:
            logger.warning("Monitoring is already active")
            return
        
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        logger.info("✅ Celery monitoring started")
    
    def stop_monitoring(self):
        """Stop the monitoring system."""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=10)
        logger.info("🛑 Celery monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                self._collect_metrics()
                self._check_worker_health()
                self._check_sla_compliance()
                self._process_alerts()
                self._check_worker_restart()
                
                # Store performance snapshot
                snapshot = {
                    'timestamp': datetime.now(),
                    'worker_count': len(self.worker_metrics),
                    'active_tasks': sum(wm.active_tasks for wm in self.worker_metrics.values()),
                    'completed_tasks': sum(wm.completed_tasks for wm in self.worker_metrics.values()),
                    'failed_tasks': sum(wm.failed_tasks for wm in self.worker_metrics.values()),
                    'queue_load': {qm.queue_name: qm.pending_tasks for qm in self.queue_metrics.values()}
                }
                
                with self._lock:
                    self.performance_history.append(snapshot)
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)  # Brief pause before retry
    
    def _collect_metrics(self):
        """Collect worker and task metrics."""
        try:
            if not celery_app:
                return
            
            # Get worker inspect
            inspect_client = celery_app.control.inspect()
            
            # Collect worker stats
            stats = inspect_client.stats() or {}
            for worker_name, worker_info in stats.items():
                # Calculate uptime
                start_time = worker_info.get('rusage', {}).get('stime', time.time())
                uptime = timedelta(seconds=time.time() - start_time)
                
                # Get active/scheduled/reserved tasks
                active_tasks = inspect_client.active() or {}
                scheduled_tasks = inspect_client.scheduled() or {}
                reserved_tasks = inspect_client.reserved() or {}
                
                worker_metrics = WorkerMetrics(
                    worker_name=worker_name,
                    active_tasks=len(active_tasks.get(worker_name, [])),
                    scheduled_tasks=len(scheduled_tasks.get(worker_name, [])),
                    reserved_tasks=len(reserved_tasks.get(worker_name, [])),
                    last_heartbeat=datetime.now(),
                    uptime=uptime,
                    cpu_usage=worker_info.get('rusage', {}).get('cpu', 0),
                    memory_usage=worker_info.get('rusage', {}).get('mem', 0)
                )
                
                with self._lock:
                    self.worker_metrics[worker_name] = worker_metrics
            
            # Collect queue metrics
            registered_queues = inspect_client.active_queues() or {}
            for worker_name, queues in registered_queues.items():
                for queue in queues:
                    queue_name = queue.get('name', 'unknown')
                    
                    if queue_name not in self.queue_metrics:
                        self.queue_metrics[queue_name] = QueueMetrics(queue_name=queue_name)
                    
                    # Estimate queue load (pending tasks = scheduled + reserved)
                    scheduled_count = len(scheduled_tasks.get(worker_name, []))
                    reserved_count = len(reserved_tasks.get(worker_name, []))
                    
                    queue_metrics = self.queue_metrics[queue_name]
                    queue_metrics.pending_tasks = scheduled_count + reserved_count
                    queue_metrics.active_tasks = len(active_tasks.get(worker_name, []))
        
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
    
    def _check_worker_health(self):
        """Check worker health status."""
        current_time = datetime.now()
        
        for worker_name, metrics in list(self.worker_metrics.items()):
            # Check if worker is responsive
            if metrics.last_heartbeat:
                time_since_heartbeat = current_time - metrics.last_heartbeat
                if time_since_heartbeat > timedelta(seconds=120):  # 2 minutes
                    self._create_alert(
                        AlertLevel.CRITICAL,
                        f"Worker {worker_name} is unresponsive",
                        "worker_health",
                        f"No heartbeat for {time_since_heartbeat}"
                    )
            
            # Check for stuck workers
            if metrics.active_tasks == 0 and metrics.scheduled_tasks == 0 and metrics.reserved_tasks == 0:
                continue  # Worker is idle, which is healthy
            
            # Check for high task failure rate
            total_tasks = metrics.completed_tasks + metrics.failed_tasks
            if total_tasks > 0:
                failure_rate = metrics.failed_tasks / total_tasks
                if failure_rate > 0.5:  # More than 50% failures
                    self._create_alert(
                        AlertLevel.ERROR,
                        f"Worker {worker_name} has high failure rate ({failure_rate:.2%})",
                        "worker_health",
                        f"Failure rate: {failure_rate:.2%}"
                    )
    
    def _check_sla_compliance(self):
        """Check SLA compliance for task execution times."""
        for task_name, task_metrics in self.task_metrics.items():
            if task_metrics.execution_count > 0:
                if task_metrics.average_execution_time > self.sla_threshold:
                    task_metrics.sla_violations += 1
                    
                    if task_metrics.sla_violations >= self.alert_threshold:
                        self._create_alert(
                            AlertLevel.WARNING,
                            f"Task {task_name} frequently exceeds SLA threshold",
                            "sla_compliance",
                            f"Avg execution: {task_metrics.average_execution_time:.2f}s > {self.sla_threshold}s"
                        )
    
    def _process_alerts(self):
        """Process and resolve alerts."""
        # Auto-resolve resolved alerts
        for alert in list(self.alerts):
            if not alert.resolved:
                continue
            
            # Clean up old resolved alerts
            if alert.resolved_at and datetime.now() - alert.resolved_at > timedelta(hours=24):
                with self._lock:
                    self.alerts.remove(alert)
    
    def _check_worker_restart(self):
        """Check if workers need to be restarted."""
        current_time = datetime.now()
        
        for worker_name, metrics in self.worker_metrics.items():
            if metrics.last_heartbeat:
                time_since_heartbeat = current_time - metrics.last_heartbeat
                
                # Restart workers that haven't responded for 5 minutes
                if time_since_heartbeat > timedelta(minutes=5):
                    self._restart_worker(worker_name)
    
    def _restart_worker(self, worker_name: str):
        """Restart a non-responsive worker."""
        try:
            if not celery_app:
                return
            
            logger.info(f"🔄 Restarting non-responsive worker: {worker_name}")
            
            # Revoke active tasks for this worker
            celery_app.control.revoke(worker=worker_name, terminate=True)
            
            # Count restart
            self.worker_restart_counts[worker_name] += 1
            
            self._create_alert(
                AlertLevel.WARNING,
                f"Worker {worker_name} was automatically restarted",
                "worker_restart",
                f"Restart count: {self.worker_restart_counts[worker_name]}"
            )
            
            # Note: In production, you would implement actual worker restart logic here
            # This might involve system signals, process management tools, or orchestration
            
        except Exception as e:
            logger.error(f"Failed to restart worker {worker_name}: {e}")
    
    def _create_alert(self, level: AlertLevel, message: str, source: str, details: str = ""):
        """Create a new alert."""
        alert = Alert(
            id=f"{source}_{int(time.time())}",
            level=level,
            message=message,
            timestamp=datetime.now(),
            source=source
        )
        
        with self._lock:
            self.alerts.append(alert)
        
        # Notify alert handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
        
        logger.warning(f"🚨 Alert [{level.value}] {message}: {details}")
    
    def update_task_metrics(self, task_name: str, execution_time: float, success: bool):
        """Update task execution metrics."""
        task_metrics = self.task_metrics[task_name]
        
        with self._lock:
            task_metrics.task_name = task_name
            task_metrics.execution_count += 1
            task_metrics.last_execution = datetime.now()
            
            # Update timing metrics
            if task_metrics.execution_count == 1:
                task_metrics.min_execution_time = execution_time
                task_metrics.max_execution_time = execution_time
            else:
                task_metrics.min_execution_time = min(task_metrics.min_execution_time, execution_time)
                task_metrics.max_execution_time = max(task_metrics.max_execution_time, execution_time)
            
            # Update running averages
            task_metrics.total_execution_time += execution_time
            task_metrics.average_execution_time = task_metrics.total_execution_time / task_metrics.execution_count
            
            # Update success/failure counts
            if success:
                task_metrics.success_count += 1
            else:
                task_metrics.failure_count += 1
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        with self._lock:
            current_alerts = [alert for alert in self.alerts if not alert.resolved]
            critical_alerts = [alert for alert in current_alerts if alert.level == AlertLevel.CRITICAL]
            error_alerts = [alert for alert in current_alerts if alert.level == AlertLevel.ERROR]
            warning_alerts = [alert for alert in current_alerts if alert.level == AlertLevel.WARNING]
            
            # Determine overall health
            if critical_alerts:
                status = "critical"
            elif error_alerts:
                status = "error"
            elif warning_alerts:
                status = "warning"
            else:
                status = "healthy"
            
            return {
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "workers": {
                    "total": len(self.worker_metrics),
                    "healthy": sum(1 for wm in self.worker_metrics.values() 
                                 if wm.last_heartbeat and 
                                 datetime.now() - wm.last_heartbeat < timedelta(seconds=120))
                },
                "tasks": {
                    "total_executed": sum(tm.execution_count for tm in self.task_metrics.values()),
                    "success_rate": self._calculate_overall_success_rate()
                },
                "queues": {
                    "total": len(self.queue_metrics),
                    "pending_load": sum(qm.pending_tasks for qm in self.queue_metrics.values())
                },
                "alerts": {
                    "total_active": len(current_alerts),
                    "critical": len(critical_alerts),
                    "error": len(error_alerts),
                    "warning": len(warning_alerts)
                },
                "sla_compliance": {
                    "overall_rate": self._calculate_sla_compliance(),
                    "violations": sum(tm.sla_violations for tm in self.task_metrics.values())
                }
            }
    
    def _calculate_overall_success_rate(self) -> float:
        """Calculate overall task success rate."""
        total_success = sum(tm.success_count for tm in self.task_metrics.values())
        total_attempts = sum(tm.execution_count for tm in self.task_metrics.values())
        
        return (total_success / total_attempts * 100) if total_attempts > 0 else 100.0
    
    def _calculate_sla_compliance(self) -> float:
        """Calculate overall SLA compliance rate."""
        total_tasks = sum(tm.execution_count for tm in self.task_metrics.values())
        compliant_tasks = sum(
            tm.execution_count - tm.sla_violations 
            for tm in self.task_metrics.values()
        )
        
        return (compliant_tasks / total_tasks * 100) if total_tasks > 0 else 100.0
    
    def get_worker_details(self, worker_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific worker."""
        with self._lock:
            worker_metrics = self.worker_metrics.get(worker_name)
            if not worker_metrics:
                return None
            
            return asdict(worker_metrics)
    
    def get_task_details(self, task_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific task."""
        with self._lock:
            task_metrics = self.task_metrics.get(task_name)
            if not task_metrics:
                return None
            
            return asdict(task_metrics)
    
    def get_queue_details(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific queue."""
        with self._lock:
            queue_metrics = self.queue_metrics.get(queue_name)
            if not queue_metrics:
                return None
            
            return asdict(queue_metrics)
    
    def get_performance_history(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Get performance history for the specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            return [
                snapshot for snapshot in self.performance_history 
                if snapshot['timestamp'] > cutoff_time
            ]
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve a specific alert."""
        with self._lock:
            for alert in self.alerts:
                if alert.id == alert_id and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    return True
        return False
    
    def add_alert_handler(self, handler: Callable[[Alert], None]):
        """Add a custom alert handler."""
        self.alert_handlers.append(handler)
    
    def export_metrics(self, filepath: str):
        """Export current metrics to JSON file."""
        metrics_data = {
            "system_status": self.get_system_status(),
            "workers": {name: asdict(metrics) for name, metrics in self.worker_metrics.items()},
            "tasks": {name: asdict(metrics) for name, metrics in self.task_metrics.items()},
            "queues": {name: asdict(metrics) for name, metrics in self.queue_metrics.items()},
            "alerts": [asdict(alert) for alert in self.alerts],
            "performance_history": list(self.performance_history),
            "timestamp": datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(metrics_data, f, indent=2, default=str)
        
        logger.info(f"📊 Metrics exported to {filepath}")

# Global monitor instance
monitor = CeleryMonitor(
    sla_threshold=60.0,  # 60 seconds SLA
    alert_threshold=5,
    check_interval=30,
    history_size=1000
)

def start_monitoring():
    """Start the global monitoring system."""
    monitor.start_monitoring()

def stop_monitoring():
    """Stop the global monitoring system."""
    monitor.stop_monitoring()

def get_status():
    """Get current system status."""
    return monitor.get_system_status()

def export_metrics(filepath: str):
    """Export metrics to file."""
    monitor.export_metrics(filepath)

# Export the monitor class and instance
__all__ = [
    'CeleryMonitor',
    'monitor',
    'start_monitoring',
    'stop_monitoring', 
    'get_status',
    'export_metrics',
    'AlertLevel'
]