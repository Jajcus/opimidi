
import asyncio
import logging
import signal

logger = logging.getLogger("util")

def abort():
    for task in asyncio.Task.all_tasks():
        task.cancel()

def signal_handler():
    logger.info("Stopping by a signal")
    abort()

def run_async_jobs(jobs):
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, signal_handler)
    loop.add_signal_handler(signal.SIGTERM, signal_handler)
    try:
        loop.run_until_complete(asyncio.wait(jobs))
    except asyncio.CancelledError:
        loop.run_until_complete(asyncio.wait(asyncio.Task.all_tasks()))
    finally:
        loop.close()
