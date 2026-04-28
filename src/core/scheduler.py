import asyncio

class TaskManager:
    def __init__(self):
        self.scheduled_tasks: set[asyncio.Task] = set()

    def schedule_task(self, task: asyncio.Task):
        self.scheduled_tasks.add(task)
        task.add_done_callback(self.scheduled_tasks.discard)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task):
        try:
            task.result()
        except Exception as e:
            print(f"Task error: {e}")

    def cancel_all_tasks(self):
        for task in self.scheduled_tasks:
            task.cancel()
        self.scheduled_tasks.clear()

    def get_scheduled_tasks(self):
        return self.scheduled_tasks