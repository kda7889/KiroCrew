#!/bin/sh
# Isolated owner trial. No inherited credentials, shared home, tunnel or browser launch.
set -eu

if [ -n "${KIROCREW_SANDBOX_ACTIVE:-}" ]; then
    echo 'Run this trial in an ordinary owner terminal; never clear the sandbox marker.' >&2
    exit 1
fi

MAX_SOURCE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
MAX_TASK_ROOT=$(dirname -- "$MAX_SOURCE_ROOT")
MAX_TRIAL_ROOT="$MAX_TASK_ROOT/_only_local/max-trial-11249e86"
MAX_TRIAL_HOME="$MAX_TRIAL_ROOT/os-home"
MAX_TRIAL_CLI="$MAX_TASK_ROOT/max-source-test-env/bin/kirocrew"

if [ ! -x "$MAX_TRIAL_CLI" ] || [ ! -d "$MAX_TRIAL_HOME" ]; then
    echo 'Prepared candidate is missing; do not substitute the installed gateway.' >&2
    exit 1
fi

if [ "$#" -eq 0 ]; then
    set -- gateway --no-open --no-tunnel --no-crons --port 55476 --approval interactive
fi

cd -- "$MAX_TRIAL_ROOT"
exec env -i \
    PATH="$MAX_TASK_ROOT/max-source-test-env/bin:/usr/local/bin:/usr/bin:/bin" \
    HOME="$MAX_TRIAL_HOME" KIRO_HOME="$MAX_TRIAL_HOME/.kiro" \
    KIROCREW_HOME="$MAX_TRIAL_HOME/.kiro/crew" KIROCREW_BIND=127.0.0.1 \
    KIROCREW_WORKSPACE="$MAX_TRIAL_ROOT/workspace" \
    XDG_CONFIG_HOME="$MAX_TRIAL_HOME/.config" XDG_DATA_HOME="$MAX_TRIAL_HOME/.local/share" \
    XDG_CACHE_HOME="$MAX_TRIAL_HOME/.cache" LANG=C.UTF-8 TERM="${TERM:-xterm}" \
    MAX_BOT_TOKEN=secret://max-bot MAX_WEBHOOK_SECRET=secret://max-webhook \
    "$MAX_TRIAL_CLI" "$@"
