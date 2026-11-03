import itertools
from dataclasses import dataclass, field


@dataclass
class Job:
    id: int
    kind: str
    payload: dict
    due: float = 0.0
    attempts: int = 0
    max_attempts: int | None = None
    error: str | None = None


@dataclass
class Queue:
    base: float = 1.0
    max_attempts: int = 3
    jobs: list = field(default_factory=list)
    finished: list = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    def push(self, kind, payload, due=0.0, max_attempts=None):
        job = Job(next(self._ids), kind, payload, due, max_attempts=max_attempts)
        self.jobs.append(job)
        return job.id

    def next(self, now):
        for job in self.jobs:
            if job.due <= now:
                return job
        return None

    def done(self, job_id):
        job = self._take(job_id)
        self.finished.append(job)

    def fail(self, job_id, error):
        raise NotImplementedError

    def _take(self, job_id):
        for i, job in enumerate(self.jobs):
            if job.id == job_id:
                return self.jobs.pop(i)
        raise KeyError(job_id)
