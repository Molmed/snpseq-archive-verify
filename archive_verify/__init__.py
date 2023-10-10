
# mapping between the internal states of the service (keys) and the states that should be
# returned in the response object (parsed by e.g. poll_status.py in snpseq_packs)
REDIS_STATES = {
    "queued": "pending",
    "deferred": "pending",
    "scheduled": "pending",
    "started": "started",
    "finished": "done",
    "failed": "error",
    "stopped": "cancelled",
    "canceled": "cancelled"
}
