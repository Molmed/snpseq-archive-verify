
from arteria.web.state import State

# mapping between the internal states of the service (keys) and the states that should be
# returned in the response object (parsed by e.g. poll_status.py in snpseq_packs)
REDIS_STATES = {
    "queued": State.PENDING,
    "deferred": State.PENDING,
    "scheduled": State.PENDING,
    "started": State.STARTED,
    "finished": State.DONE,
    "failed": State.ERROR,
    "stopped": State.CANCELLED,
    "canceled": State.CANCELLED
}
