"""Async task tracking utilities for the clock loop."""

import asyncio


# ---------------------------------------------------------------------------
# Task tracking
# ---------------------------------------------------------------------------

class TaskManager:
    """Track scheduled asyncio tasks so they can be awaited or cancelled."""

    def __init__(self) -> None:
        """Initialize the internal task set."""
        self.scheduled_tasks: set[asyncio.Task] = set()

    def schedule_task(self, task: asyncio.Task) -> None:
        """Register and track a new asyncio task.

        Args:
            task (asyncio.Task): Task to track.
        """
        # Track the task and clean it up when complete.
        self.scheduled_tasks.add(task)
        task.add_done_callback(self.scheduled_tasks.discard)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task) -> None:
        """
        Handle task completion and surface unexpected exceptions.

        Args:
            task (asyncio.Task): Completed task instance.
        """
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except KeyboardInterrupt:
            print("Task cancelled by user.")
        except Exception as e:
            print(f"Task error: {e}")

    def cancel_all_tasks(self) -> None:
        """Cancel all currently scheduled tasks."""
        # Cancel before clearing so callbacks still run.
        for task in self.scheduled_tasks:
            task.cancel()
        self.scheduled_tasks.clear()

    def get_scheduled_tasks(self) -> set[asyncio.Task]:
        """
        Return the currently tracked tasks.

        Returns:
            set[asyncio.Task]: Active scheduled tasks.
        """
        return self.scheduled_tasks