#! /bin/sh

redis-server &
/archive-verify/.venv/bin/rq worker &
/archive-verify/.venv/bin/archive-verify-ws -c=/archive-verify/config/ &
nginx &
wait
