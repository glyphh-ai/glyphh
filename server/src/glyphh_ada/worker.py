"""`python -m glyphh_ada.worker --queue sync|jobs`: a process group's command in fly.toml (`ada`, `adajobs`). It
starts one single-threaded worker process per vCPU (or GLYPHH_ADA_WORKERS, or --processes), and starts again any that
dies. With GLYPHH_ADA_CLOUD off it does nothing at all, touching neither Postgres nor Redis, and waits to be stopped,
so a deploy with the flag off runs exactly what ran before."""

import argparse
import logging
import multiprocessing
import os
import signal
import threading
from collections.abc import Callable
from multiprocessing.process import BaseProcess

from glyphh_ada.process import Worker
from glyphh_ada.protocol import JOBS, SYNC
from glyphh_server.config import get_settings
from glyphh_server.obs.logs import configure, fields

log = logging.getLogger("glyphh.ada")
RESTART_EVERY: float = 1.0


def serve(queue: str) -> None:
    """One worker process, until SIGTERM."""
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    settings = get_settings()
    configure(settings.log_level)
    Worker(settings, queue).serve(stop)


def supervise(
    count: int, queue: str, stop: threading.Event, target: Callable[[str], None] = serve, every: float = RESTART_EVERY
) -> int:
    """`count` worker processes kept running until stop is set; returns how many were started in all."""
    spawn = multiprocessing.get_context("spawn")
    running: dict[int, BaseProcess] = {}
    started = 0
    while not stop.is_set():
        for slot in range(count):
            if slot not in running or not running[slot].is_alive():
                if slot in running:
                    log.warning("a worker stopped; starting another", extra=fields(queue=queue, slot=slot))
                running[slot] = spawn.Process(target=target, args=(queue,), daemon=True)
                running[slot].start()
                started += 1
        stop.wait(every)
    for process in running.values():
        process.terminate()
        process.join(10)
    return started


def idle(stop: threading.Event, every: float = 3600.0) -> None:
    log.warning("Ada Cloud is off (GLYPHH_ADA_CLOUD): this worker group does nothing")
    while not stop.wait(every):
        pass


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="glyphh_ada.worker")
    parser.add_argument("--queue", choices=(SYNC, JOBS), required=True)
    parser.add_argument("--processes", type=int, default=0)
    args = parser.parse_args(argv)
    settings = get_settings()
    configure(settings.log_level)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    if not settings.ada_cloud:
        return idle(stop)
    count = args.processes or settings.ada_workers or os.cpu_count() or 1
    log.info("starting workers", extra=fields(queue=args.queue, processes=count))
    supervise(count, args.queue, stop)


if __name__ == "__main__":  # pragma: no cover
    main()
