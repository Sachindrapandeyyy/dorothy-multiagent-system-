"""
Dorothy OS v2.0 — Autonomous Workflow & Scheduled Task Engine.
Runs background cron-like loops, sequential task chains, and event-driven swarms.
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Callable, Optional, Union

logger = logging.getLogger("Dorothy.Workflows.Engine")

class WorkflowTask:
    """Represents a scheduled background task or sequential chain."""

    def __init__(
        self,
        task_id: str,
        name: str,
        trigger_type: str,  # "interval" or "cron" or "event"
        value: Union[int, float, str],  # Interval in seconds, cron string, or event name
        action: Callable[[], Any],
        description: str = "",
    ) -> None:
        self.task_id = task_id
        self.name = name
        self.trigger_type = trigger_type
        self.value = value
        self.action = action
        self.description = description
        self.is_active = False
        self.last_run: Optional[datetime] = None
        self.run_count = 0
        self._running_task: Optional[asyncio.Task] = None

    async def run(self) -> None:
        """Execute the workflow action safely with logging."""
        try:
            self.last_run = datetime.now(timezone.utc)
            self.run_count += 1
            logger.info(f"Running autonomous workflow '{self.name}' (Run #{self.run_count})")
            if asyncio.iscoroutinefunction(self.action):
                await self.action()
            else:
                self.action()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error executing workflow task '{self.name}': {e}", exc_info=True)


class WorkflowEngine:
    """Manages autonomous task scheduling, monitoring, and agent triggers."""

    def __init__(self) -> None:
        self.tasks: Dict[str, WorkflowTask] = {}
        self.is_running = False

    def register_task(
        self,
        task_id: str,
        name: str,
        trigger_type: str,
        value: Union[int, float, str],
        action: Callable[[], Any],
        description: str = "",
    ) -> bool:
        """Register a new task in the workflow engine."""
        if task_id in self.tasks:
            logger.warning(f"Task ID '{task_id}' already registered. Overwriting.")
            self.unregister_task(task_id)

        task = WorkflowTask(task_id, name, trigger_type, value, action, description)
        self.tasks[task_id] = task
        logger.info(f"Registered autonomous task '{name}' (Type: {trigger_type})")
        
        # If engine is already running, start the task immediately
        if self.is_running:
            self._start_task_loop(task)
        return True

    def unregister_task(self, task_id: str) -> bool:
        """Remove and cancel a scheduled task."""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.is_active = False
        if task._running_task:
            task._running_task.cancel()
        del self.tasks[task_id]
        logger.info(f"Unregistered autonomous task: {task_id}")
        return True

    def start(self) -> None:
        """Start execution of all registered workflow loops."""
        if self.is_running:
            return
        self.is_running = True
        logger.info("Starting Autonomous Workflow Engine...")
        for task in self.tasks.values():
            self._start_task_loop(task)

    def stop(self) -> None:
        """Stop all background workflows."""
        self.is_running = False
        logger.info("Stopping Autonomous Workflow Engine...")
        for task in self.tasks.values():
            task.is_active = False
            if task._running_task:
                task._running_task.cancel()
                task._running_task = None

    def _start_task_loop(self, task: WorkflowTask) -> None:
        """Spawns an asynchronous background task runner."""
        task.is_active = True
        
        if task.trigger_type == "interval":
            interval = float(task.value)
            
            async def interval_loop():
                await asyncio.sleep(interval)  # Wait before first run
                while task.is_active and self.is_running:
                    await task.run()
                    await asyncio.sleep(interval)
                    
            task._running_task = asyncio.create_task(interval_loop())
            
        elif task.trigger_type == "event":
            # Event-based activation triggers (handled separately or simulated)
            pass
            
        else:
            logger.warning(f"Trigger type '{task.trigger_type}' is currently unsupported.")

    def get_status_report(self) -> List[Dict[str, Any]]:
        """Snapshot of all active background workflows for visual reporting."""
        report = []
        for tid, task in self.tasks.items():
            report.append({
                "task_id": tid,
                "name": task.name,
                "trigger_type": task.trigger_type,
                "trigger_value": task.value,
                "is_active": task.is_active,
                "run_count": task.run_count,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "description": task.description,
            })
        return report

workflow_engine = WorkflowEngine()
