from fastapi import BackgroundTasks, FastAPI
import asyncio
from concurrent.futures import ProcessPoolExecutor
import gc
import time

import profiler

app = FastAPI()

profiler.start_basics()
# in my local development using docker, because of the profiler and API, the process starts already with 8 threads. So, any new one created by fastapi will be 9, 10, etc.

# Create a process pool executor once when the app starts. This is for testing the process pool (can be skipped for now)
process_pool = ProcessPoolExecutor()


# This function must be defined at the top level to be "picklable"
# This is just for testnig the process pool (can be skipped for now)
def memory_task_for_process():
    """Memory task that runs in a separate process for guaranteed cleanup"""
    big = []
    for _ in range(5):
        big.append(" " * 10**7)  # ~10MB
        time.sleep(1)
    del big
    gc.collect()
    print("Process task finished and cleaned up.")
    return {"Memory process": "Done"}


@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.get("/blocking")
async def blocking():
    # async function (runs in the event loop). It's a blocking function
    # Running this effectively blocks the event loop for 5 seconds
    import time

    time.sleep(5)
    return {"Blocking": "Done"}


@app.get("/compute")
async def compute():
    # this does some CPU work for 5 seconds
    # blocks? YES. It's async function, so it runs in the event loop. The event loop is blocked for 5 seconds.
    # cpu spike then goes down. threads still the same. RSS_mb up a bit and oscilates.
    import time

    end_time = time.time() + 5
    while time.time() < end_time:
        sum(i * i for i in range(10000))
    return {"Compute": "Done"}


@app.get("/memory")
async def memory():
    # this allocates some memory for 5 seconds. Used to test functions that increase the memory usage
    # spike in RSS_mb, stays at an upper level than the base but less than spike.. cpu% low. threads same.
    # async function, so it runs in the event loop. The event loop is blocked for the duration of the function
    import time

    big = []
    for _ in range(5):
        big.append(" " * 10**7)  # ~10MB
        time.sleep(1)
    print("Memory task done")
    return {"Memory": "Done"}


@app.get("/backgroundtask")
async def background_task(background_tasks: BackgroundTasks):
    import time

    # This will create a BackgroundTask that runs in a separate thread
    # Important to have the task defined with def, not async def.

    # blocks?
    # No blocking. New thread created (from 8 to 9)
    # memory a bit up, keeps raising a bit
    # I ran it again, no new thread added (i guess it reused the previous one), memory is the same.
    # I ran two consecutives. Now two new threads compared to base (10). Memory a bit up and stayed there.
    def task():
        time.sleep(8)
        print("Background task done")

    background_tasks.add_task(task)
    return {"BackgroundTask": "Started"}


@app.get("/backgroundtask_async")
async def background_task_async(background_tasks: BackgroundTasks):
    import time

    # Look that here , the inner task is defined with async def, not def!

    # blocks?
    # Yes, blocks because async def. The task is not returned inmediately. No new thread created. The thread is only created by BackgroundTasks if the function is sync.
    async def task():
        time.sleep(8)
        print("Background task done")

    background_tasks.add_task(task)
    return {"BackgroundTask": "Started"}


@app.get("/def_backgroundtask_async")
def background_task_defasync(background_tasks: BackgroundTasks):
    import time

    # Main difference is that the endpoint is def but the inner task is async def.

    # blocks?
    # Warning with this one. Creates a new thread, I guess because the endpoint is def, not async def. But everything is blocked as well, I think the async def is run in the main thread and it blocks. The task is not returned inmediately.
    async def task():
        time.sleep(8)
        print("Background task done")

    background_tasks.add_task(task)
    return {"BackgroundTask": "Started"}


@app.get("/create_task")
async def create_task():
    import asyncio
    import time

    # Now we use asyncio.create_task directly. This will fire and forget using asyncio inner mechanism instead of BackgroundTasks. Beware, the create_task runs the task in the main event loop, not in a new thread! It first returns the response and fires the task in the main event loop.

    # blocks?
    # Yes. Because of async def. No new thread created. The task "CreateTask:started" is returned inmediately, but the event loop is blocked for 8 seconds.
    # To make this work correctly you need an async inner function that actually awaits something. Could be a functions that is awaitable (httpx request, asyncio.sleep, etc) or something that you run in a threadpool or thread and is awaited.
    async def task():
        time.sleep(8)
        print("Create task done")

    asyncio.create_task(task())
    return {"CreateTask": "Started"}


@app.get("/create_task_sync")
async def create_task_sync():
    import asyncio
    import time

    # Main difference is that the inner task is defined with def, not async def!

    # blocks?
    # Fails because create_task needs a coroutine, not a normal function. Needs to be async def.
    def task():
        time.sleep(8)
        print("Create task done")

    asyncio.create_task(task())
    return {"CreateTask": "Started"}


@app.get("/run_in_threadpool")
async def run_in_threadpool_fn():
    from starlette.concurrency import run_in_threadpool
    import time

    # Now we use run_in_threadpool to run a blocking function in a thread from the threadpool-

    # Doesn't block, new thread created (from 8 to 9). Memory a bit up and stays there.
    # the task must be Def, not async def.
    # uses the threadpool default (40) max
    # Note to test again: with timeouts and all, it used more memory than threadpoolExecutor (just with sleep)
    def task():
        time.sleep(8)
        print("Run in threadpool done")

    res = await run_in_threadpool(task)
    return {"RunInThreadpool": "Done"}


@app.get("/run_in_threadpoolExecutor")
async def run_in_threadpoolExecutor():
    import concurrent.futures
    import time
    import asyncio

    # We use ThreadPoolExecutor directly. This is similar to run_in_threadpool, but we create a new threadpool for each request. We have more control of the threadpool, but we need to manage it ourselves. You could create the threadpool once at startup and reuse it. In that case it's the same as run_in_threadpool I think if you don't manage anything special,  but you could set the max_workers, etc.

    # doesn't block.
    # new threads created infinitely as it created a threadpool for each request. Memory a bit up and stays there.
    def task():
        time.sleep(9)
        print("Run in threadpool executor done")

    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, task)
    return {"RunInThreadpoolExecutor": "Done"}


@app.get("/to_thread")
async def to_thread_fn():
    import time
    import asyncio

    # Here we use asyncio.to_thread. Similar to run_in_threadpool but it uses the default threadpool from asyncio (which is a ThreadPoolExecutor with max_workers=min(32, os.cpu_count() + 4)) by default)
    # https://stackoverflow.com/questions/71516140/fastapi-runs-api-calls-in-serial-instead-of-parallel-fashion/71517830#71517830
    # It's confusing because in another answers we see the usage of anyo.to_thread, which I think has other defaults.

    # Doesn't block, new thread created (from 8 to 9). Memory a bit up and stays there.
    # the task must be Def, not async def.
    # the max number of threads is limited by the main thread (different somehow that to threadpool). It created just 20 (instead of 40), much more timeout
    # memory usage similar as threadpoolExecutor
    def task():
        time.sleep(8)
        print("to_thread done")

    res = await asyncio.to_thread(task)
    return {"to_thread": "Done"}


@app.get("/run_in_threadpool_memory")
async def run_in_threadpool_memory():
    from starlette.concurrency import run_in_threadpool
    import time

    # Now we use again run_in_threadpool with a memory intensive function.
    # This is where we start to test the api memory usage using artillery (stress testing)

    # Doesn't block, new thread created (from 8 to 9). Memory a bit up and stays there.
    # the task must be Def, not async def.
    # uses the threadpool default (40) max
    # check again this: with timeouts and all used more memory than threadpoolExecutor (just with sleep)

    def memory():
        # this allocates some memory for 5 seconds
        # spike in RSS_mb, stays at an upper leve but less than spike.. cpu% low. threads same.

        big = []
        for _ in range(5):
            big.append(" " * 10**7)  # ~10MB
            time.sleep(1)
        print("Memory task in threadpool memory done")
        return {"Memory threadpool memory": "Done"}

    res = await run_in_threadpool(memory)
    return {"RunInThreadpool Memory": "Done"}


@app.get("/run_in_threadpool_memory_def")
def run_in_threadpool_memory_def():
    from starlette.concurrency import run_in_threadpool
    import time

    # what happened here? is the same?

    # Doesn't block, new thread created (from 8 to 9). Memory a bit up and stays there.
    # the task must be Def, not async def.
    # uses the threadpool default (40) max
    # with timeouts and all used more memory than threadpoolExecutor (just with sleep)
    def memory():
        # this allocates some memory for 5 seconds
        # spike in RSS_mb, stays at an upper leve but less than spike.. cpu% low. threads same.

        big = []
        for _ in range(5):
            big.append(" " * 10**7)  # ~10MB
            time.sleep(1)
        print("Memory task in threadpool memory done")
        return {"Memory threadpool memory": "Done"}

    res = run_in_threadpool(memory)
    return {"RunInThreadpool Memory": "Done"}


@app.get("/run_in_threadpoolExecutor_memory")
async def run_in_threadpoolExecutor_memory():
    import concurrent.futures
    import time
    import asyncio

    # doesn't block.
    # new thread created infinitely as it created a threadpool for each request. Memory a bit up and stays there.
    def memory():
        # this allocates some memory for 5 seconds
        # spike in RSS_mb, stays at an upper leve but less than spike.. cpu% low. threads same.

        big = []
        for _ in range(5):
            big.append(" " * 10**7)  # ~10MB
            time.sleep(1)
        print("Memory task in threadpoolExecutor done")
        return {"Memory threadpoolExecutor": "Done"}

    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, memory)
    return {"RunInThreadpoolExecutor Memory": "Done"}


# from here and below, is less tested and documents, they were quick experiments to see if something released quickly the memory... Sorry, not sure yet about it


@app.get("/run_in_threadpoolExecutor_memory_clean")
async def run_in_threadpoolExecutor_memory_clean():
    """Memory endpoint with explicit cleanup"""
    import concurrent.futures
    import time
    import asyncio
    import gc
    import psutil
    import os

    def memory_with_cleanup():
        """Memory allocation with explicit cleanup"""
        try:
            big = []
            for i in range(5):
                chunk = " " * 10**7  # ~10MB
                big.append(chunk)
                time.sleep(1)

            print(f"Memory task allocated {len(big)} chunks")
            return {"chunks_allocated": len(big)}
        finally:
            # Explicit cleanup
            try:
                del big
                del chunk
            except:
                pass
            gc.collect()

    loop = asyncio.get_running_loop()

    # Track memory before
    process = psutil.Process(os.getpid())
    memory_before = process.memory_info().rss / 1024 / 1024

    # Run the memory task
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        result = await loop.run_in_executor(pool, memory_with_cleanup)

    # Force cleanup after thread completion
    gc.collect()

    # Track memory after
    memory_after = process.memory_info().rss / 1024 / 1024

    return {
        "task_result": result,
        "memory_before_mb": round(memory_before, 2),
        "memory_after_mb": round(memory_after, 2),
        "memory_difference_mb": round(memory_after - memory_before, 2),
        "threadpool_executor": "cleaned",
    }


@app.get("/run_in_process")
async def run_in_process():
    """Memory task that runs in a separate process for guaranteed memory cleanup"""
    # This is work in progress I haven't tested much
    # I think each processor doesn't die after the function ends, it stays alive in the pool os memory is not freed
    loop = asyncio.get_running_loop()
    # Run the blocking function in the process pool
    await loop.run_in_executor(process_pool, memory_task_for_process)
    return {"RunInProcess": "Done"}


@app.get("/run_in_fresh_process")
async def run_in_fresh_process():
    """Memory task with a fresh process that dies after completion"""
    loop = asyncio.get_running_loop()

    # Create a NEW process pool with max_workers=1 for this request only
    # uses much more memory I think because it creates a new process each time
    with ProcessPoolExecutor(max_workers=1) as fresh_pool:
        await loop.run_in_executor(fresh_pool, memory_task_for_process)
    # Process is guaranteed to be terminated here
    return {"RunInFreshProcess": "Done"}


@app.get("/gc_collect")
async def gc_collect():
    import gc

    gc.collect()
    return {"gc": "collected"}
