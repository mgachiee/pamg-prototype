import asyncio

class TaskManager:
    """A simple task manager to keep track of scheduled asyncio tasks."""
    def __init__(self):
        self.scheduled_tasks: set[asyncio.Task] = set()

    def schedule_task(self, task: asyncio.Task):
        """
        Schedules a new asyncio task and adds it to the set of scheduled tasks.

        Args:
            task: The asyncio Task to be scheduled.
        """
        self.scheduled_tasks.add(task)
        task.add_done_callback(self.scheduled_tasks.discard)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task):
        """
        A callback function that is called when a task is done. It checks for exceptions and prints them.

        Args:
            task: The asyncio Task that has completed.
        """
        try:
            task.result()
        except Exception as e:
            print(f"Task error: {e}")

    def cancel_all_tasks(self):
        """Cancels all currently scheduled tasks."""
        for task in self.scheduled_tasks:
            task.cancel()
        self.scheduled_tasks.clear()

    def get_scheduled_tasks(self):
        """Returns a set of all currently scheduled tasks."""
        return self.scheduled_tasks