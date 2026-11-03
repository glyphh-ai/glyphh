def run_once(queue, handlers, now):
    job = queue.next(now)
    if job is None:
        return None
    handlers[job.kind](job.payload)
    queue.done(job.id)
    return job.id
