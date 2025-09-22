# profiler.py
import os
import time
import threading
import tracemalloc
import psutil
import gc


def start_basics(poll_secs: float = 5.0, trace_top: int = 10, snapshot_every: int = 30):
    """
    Starts two background threads:
      1) psutil reporter: RSS/CPU%/threads
      2) tracemalloc snapshotter: top allocators by line
    """
    proc = psutil.Process(os.getpid())
    proc.cpu_percent(interval=None)  # prime

    # 1) psutil reporter
    def _reporter():
        while True:
            rss = proc.memory_info().rss
            cpu = proc.cpu_percent(interval=None)  # % of a single core
            thr = proc.num_threads()
            # python 3.12 gc stats are nice; this is safe if older too
            try:
                gen = gc.get_stats()
            except Exception:
                gen = None
            print(
                f"[psutil] rss_mb={rss / 1e6:.1f} cpu%={cpu:.1f} threads={thr} gc={gen}",
                flush=True,
            )
            time.sleep(poll_secs)

    t1 = threading.Thread(target=_reporter, daemon=True)
    t1.start()

    # 2) tracemalloc tops
    tracemalloc.start(25)

    def _snapshots():
        last = None
        while True:
            snap = tracemalloc.take_snapshot()
            if last is not None:
                top = snap.compare_to(last, "lineno")[:trace_top]
                print("\n[tracemalloc] Top diffs since last snapshot:", flush=True)
                for s in top:
                    print(
                        f"  {s.count:>6} blocks, {s.size / 1e6:>8.3f} MB: {s.traceback.format()[-1].strip()}",
                        flush=True,
                    )
            last = snap
            time.sleep(snapshot_every)

    t2 = threading.Thread(target=_snapshots, daemon=True)
    t2.start()


def print_current_top(n: int = 20, key: str = "lineno"):
    """Call this from anywhere (e.g., an endpoint) to dump current top allocators."""
    snap = tracemalloc.take_snapshot()
    stats = snap.statistics(key)[:n]
    print("\n[tracemalloc] Current top allocations:", flush=True)
    for s in stats:
        print(
            f"  {s.count:>6} blocks, {s.size / 1e6:>8.3f} MB: {s.traceback.format()[-1].strip()}",
            flush=True,
        )


def force_gc_and_report():
    """Quick way to see what's collectible."""
    unreachable = gc.collect()
    print(f"[gc] Collected unreachable={unreachable}", flush=True)
