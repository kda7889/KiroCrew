#!/bin/sh
# Isolated owner trial. No inherited credentials, shared home, tunnel or browser launch.
set -eu

if [ -n "${KIROCREW_SANDBOX_ACTIVE:-}" ]; then
    echo 'Run this trial in an ordinary owner terminal; never clear the sandbox marker.' >&2
    exit 1
fi

MAX_SOURCE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
MAX_TASK_ROOT=$(dirname -- "$MAX_SOURCE_ROOT")
MAX_TRIAL_CLI="$MAX_TASK_ROOT/max-source-test-env/bin/kirocrew"

if [ ! -x "$MAX_TRIAL_CLI" ]; then
    echo 'Prepared candidate is missing; do not substitute the installed gateway.' >&2
    exit 1
fi

exec "$MAX_TASK_ROOT/max-source-test-env/bin/python" "$MAX_SOURCE_ROOT/scripts/max_trial_runtime.py" "$@"
