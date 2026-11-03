def summary(queue, now):
    return {"pending": len(queue.jobs), "done": len(queue.finished)}
