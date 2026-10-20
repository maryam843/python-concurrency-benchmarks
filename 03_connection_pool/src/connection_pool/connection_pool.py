"""A database connection pool shared by processes, guarded by a semaphore.

2025 bug: the pool had no semaphore (my README said it did). get_connection() returned None when
the queue was empty, so with 8 processes and 2 connections, 6 processes printed "Waiting..." and
gave up: only 2 of 8 ever got a connection.

Now a multiprocessing.Semaphore(size) is acquired before taking a connection. acquire() blocks
until a connection is released (or until the optional timeout), so every process gets one in turn
and never more than `size` processes hold a connection at the same time.
"""

import multiprocessing
import random
import time

from connection_pool.utils import append_line, log_path


class ConnectionPool:
    """Manages a pool of database connections with process-safe access."""

    def __init__(self, size: int, ctx=None):
        if size < 1:
            raise ValueError("size must be >= 1")
        ctx = ctx or multiprocessing.get_context()
        self.size = size
        self.semaphore = ctx.Semaphore(size)
        self.pool = ctx.Queue()
        for i in range(size):
            self.pool.put(f"DB_Conn_{i}")
        self._lock = ctx.Lock()
        self._holders = ctx.Value("i", 0, lock=False)
        self._max_holders = ctx.Value("i", 0, lock=False)
        self._manager = ctx.Manager()
        self.usage_log = self._manager.list()

    def get_connection(self, timeout: float | None = None) -> str | None:
        """Block until a connection is free. Returns None only if `timeout` seconds pass first."""
        if not self.semaphore.acquire(timeout=timeout):
            return None
        conn = self.pool.get()  # a permit guarantees a connection is in the queue
        with self._lock:
            self._holders.value += 1
            self._max_holders.value = max(self._max_holders.value, self._holders.value)
            self.usage_log.append((time.time(), "acquired", conn, self._holders.value))
        return conn

    def release_connection(self, conn: str) -> None:
        """Return a connection to the pool and wake one waiting process."""
        with self._lock:
            self._holders.value -= 1
            self.usage_log.append((time.time(), "released", conn, self._holders.value))
        self.pool.put(conn)
        self.semaphore.release()

    def __getstate__(self):
        # The Manager process handle cannot be pickled (needed under "spawn"); children only need the list proxy.
        state = self.__dict__.copy()
        state["_manager"] = None
        return state

    @property
    def max_concurrent_holders(self) -> int:
        return self._max_holders.value

    def shutdown(self) -> None:
        self._manager.shutdown()


def access_database(pool: ConnectionPool, process_id: int, work_s: tuple[float, float] = (1, 2),
                    seed: int | None = None, timeout: float | None = None, log_file: str | None = None,
                    log_lock=None) -> None:
    """Simulates a process accessing the database. `log_file` is a full path; `log_lock` keeps lines whole."""
    rng = random.Random(None if seed is None else seed + process_id)

    def log(message: str) -> None:
        if log_file:
            append_line(log_file, f"Process {process_id}: {message}", log_lock)

    log("Waiting for connection...")
    conn = pool.get_connection(timeout=timeout)
    if conn is None:
        log("Timed out waiting for a connection")
        return
    try:
        log(f"Acquired {conn}")
        time.sleep(rng.uniform(*work_s))  # Simulate work
    finally:
        pool.release_connection(conn)
        log(f"Released {conn}")


def run_connection_pool(num_processes: int = 8, size: int = 2, work_s=(1, 2), seed: int | None = 0,
                        timeout: float | None = None, start_method: str | None = None,
                        log_file: str | None = None) -> dict:
    """Start `num_processes` processes that share a pool of `size` connections."""
    ctx = multiprocessing.get_context(start_method)
    pool = ConnectionPool(size=size, ctx=ctx)
    path = log_path(log_file) if log_file else None  # resolved here: workers may not share this process's env
    lock = ctx.Lock()
    processes = []
    t0 = time.perf_counter()
    for i in range(num_processes):
        p = ctx.Process(target=access_database, args=(pool, i, work_s, seed, timeout, path, lock))
        p.start()
        processes.append(p)
    for p in processes:
        p.join()
    elapsed = time.perf_counter() - t0
    log = [list(e) for e in pool.usage_log]
    summary = {
        "num_processes": num_processes,
        "pool_size": size,
        "acquired": sum(1 for e in log if e[1] == "acquired"),
        "released": sum(1 for e in log if e[1] == "released"),
        "max_concurrent_holders": pool.max_concurrent_holders,
        "exit_codes": [p.exitcode for p in processes],
        "elapsed_s": elapsed,
        "log": [{"t": e[0] - log[0][0] if log else 0.0, "event": e[1], "conn": e[2], "holders_after": e[3]}
                for e in log],
    }
    pool.shutdown()
    return summary
