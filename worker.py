import asyncio


class Worker():
    def __init__(self, tasks: asyncio.Queue, results: list, name: str = None):
        self.tasks = tasks
        self.results = results
        self.name = name


    async def work(self, stop: list):
        while not stop:
            task = await self.tasks.get()
            try:
                result = await task
            except Exception as e:
                print(e)
                pass
            if result:
                self.results.append(result)
        raise asyncio.CancelledError()


async def launch_workers(
            tasks_queue: asyncio.Queue,
            results_queue: asyncio.Queue = None,
            number_of_workers=4,
            stop=[],
        ):
    async with asyncio.TaskGroup() as tg:
        for n in range(number_of_workers):
            worker = Worker(tasks_queue, results_queue, str(n))
            tg.create_task(worker.work(stop))
