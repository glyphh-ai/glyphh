"""`python -m glyphh_ada.worker --queue sync|jobs`: a process group's command in fly.toml (`ada`, `adajobs`). It
starts single-threaded worker processes for each kernel this deploy runs (docs/specs/ada-cloud.md, 12.4): for the
latest stable's (the venv's), one per vCPU it may use (cpus; or GLYPHH_ADA_WORKERS, or --processes); for every other
one, GLYPHH_ADA_KERNEL_WORKERS, each started with that kernel's own install (GLYPHH_ADA_KERNELS_DIR/<kernel>) first
on its path, so it imports only that copy. It starts again any that dies. With GLYPHH_ADA_CLOUD off it does nothing
at all, touching neither Postgres nor Redis, and waits to be stopped, so a deploy with the flag off runs exactly what
ran before."""

import argparse
import logging
import multiprocessing
import os
import signal
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.context import SpawnContext
from multiprocessing.process import BaseProcess
from pathlib import Path

from glyphh_ada import registry, routing
from glyphh_ada.process import Worker
from glyphh_ada.protocol import JOBS, SYNC
from glyphh_server.config import Settings, get_settings
from glyphh_server.obs.logs import configure, fields

log = logging.getLogger("glyphh.ada")
RESTART_EVERY: float = 1.0
CPU_MAX: Path = Path("/sys/fs/cgroup/cpu.max")


@dataclass(frozen=True)
class Slot:
    """A kernel's worker processes: the kernel, the folder it is installed in (None: the venv's), how many."""

    kernel: str
    path: str | None
    count: int


def idle(stop: threading.Event, every: float = 3600.0) -> None:
    log.warning("Ada Cloud is off (GLYPHH_ADA_CLOUD): this worker group does nothing")
    while not stop.wait(every):
        pass


def serve(queue: str, kernel: str) -> None:
    """One worker process for this kernel, until SIGTERM. One that imported another kernel than it was started for
    (its install missing or wrong) serves nothing, rather than answer with the wrong maths."""
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    settings = get_settings()
    configure(settings.log_level)
    if routing.installed() != kernel:
        log.error("this process imported another kernel", extra=fields(kernel=kernel, imported=routing.installed()))
        return idle(stop)
    Worker(settings, queue, kernel).serve(stop)


def plan(settings: Settings, count: int) -> list[Slot]:
    """The slots this deploy runs: every kernel the registry installs whose folder is there."""
    reg, here = registry.registry(), routing.installed()
    latest = reg.latest(registry.today()).kernel
    slots = []
    for kernel in reg.kernels():
        path = None if kernel == here else str(Path(settings.ada_kernels_dir) / kernel)
        if path is not None and not Path(path).is_dir():
            log.error("a kernel the registry lists is not installed", extra=fields(kernel=kernel, path=path))
            continue
        slots.append(Slot(kernel, path, count if kernel == latest else settings.ada_kernel_workers))
    return slots


def start(spawn: SpawnContext, slot: Slot, queue: str, target: Callable[[str, str], None]) -> BaseProcess:
    """One process of a slot. A spawned process starts with its parent's sys.path, so the kernel's folder goes first
    on it for that start only."""
    process = spawn.Process(target=target, args=(queue, slot.kernel), daemon=True)
    if slot.path is not None:
        sys.path.insert(0, slot.path)
    try:
        process.start()
    finally:
        if slot.path is not None:
            sys.path.remove(slot.path)
    return process


def supervise(
    slots: list[Slot],
    queue: str,
    stop: threading.Event,
    target: Callable[[str, str], None] = serve,
    every: float = RESTART_EVERY,
) -> int:
    """Each slot's processes kept running until stop is set; returns how many were started in all."""
    spawn = multiprocessing.get_context("spawn")
    running: dict[tuple[str, int], BaseProcess] = {}
    started = 0
    while not stop.is_set():
        for slot in slots:
            for n in range(slot.count):
                key, process = (slot.kernel, n), running.get((slot.kernel, n))
                if process is not None and process.is_alive():
                    continue
                if process is not None:
                    log.warning("a worker stopped; starting another", extra=fields(queue=queue, kernel=slot.kernel))
                running[key] = start(spawn, slot, queue, target)
                started += 1
        stop.wait(every)
    for process in running.values():
        process.terminate()
        process.join(10)
    return started


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
    slots = plan(settings, args.processes or settings.ada_workers or cpus())
    log.info("starting workers", extra=fields(queue=args.queue, slots=[(s.kernel, s.count) for s in slots]))
    supervise(slots, args.queue, stop)


def cpus(quota: Path = CPU_MAX) -> int:
    """The CPUs this process may use: those it is allowed to run on, cut to its container's CPU quota (cgroup v2
    cpu.max, as `docker run --cpus` and Fly set it). os.cpu_count() alone is the host's: in a container on a 12-CPU
    laptop it starts twelve kernel processes per group, which then contend for the CPUs and the memory."""
    n = os.process_cpu_count() or 1
    try:
        limit, period = quota.read_text().split()
    except (OSError, ValueError):
        return n
    return n if limit == "max" else max(1, min(n, int(limit) // int(period)))


if __name__ == "__main__":  # pragma: no cover
    main()
