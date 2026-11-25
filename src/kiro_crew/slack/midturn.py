"""A Slack message that lands while a turn is running: steer it into that turn, or queue it.

``messaging.queue_mode`` (``"steer"`` by default) decides, as it does on Discord and
Telegram, and a ``!queue <msg>`` / ``!steer <msg>`` prefix overrides it for one
message. Two places take a busy message:

* the thread's own Slack session (``slack/events.py``'s queue check), through
  :func:`steer_if_busy`: the provider's steer channel, like Discord's
  ``_handle_busy``;
* a dashboard chat the thread is linked to (``route_linked_thread``), through
  :func:`steer_linked`: the slot's own steer path
  (``dashboard.channel_handoff.hand_to_resumed_slot``).

The thread's own session queues a steer that does not land. The linked slot's
hand-off owns both the steer and its queue fallback; a refusal is posted in the
thread. An ambiguously delivered steer is not replayed. A confirmed steer gets
the :data:`STEER_REACTION` reaction; a queued one keeps its ⏳.

The override and the message's ts travel to the linked route in a context
variable (:func:`set_inbound`), as the downloaded files do
(``linked_thread_images``): the route is reached from the native handler, the
transport dispatcher and code channels, none of which carries them. The value is
taken once, and the queue drain clears it, so a replayed entry never steers or
reacts on the strength of the message whose task queued it.
"""

from __future__ import annotations

import contextvars
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

#: Slack's name for ↪, the steer mark the other channels' renderers draw. The
#: queue keeps ``hourglass_flowing_sand``.
STEER_REACTION = "arrow_right_hook"
QUEUE_REACTION = "hourglass_flowing_sand"

_QUEUE = "!queue"
_STEER = "!steer"

#: Told for a lone ``!queue`` / ``!steer``: a prefix with no message has nothing to act on.
BARE_PREFIX_HINT = (
    "Put your message after it: `!steer <msg>` folds it into the running reply, "
    "`!queue <msg>` answers it after the reply finishes."
)


def parse_override(text: str) -> tuple[str | None, str]:
    """``("queue" | "steer", rest)`` for a ``!queue`` / ``!steer`` prefix with a body, else ``(None, text)``."""
    parts = text.lstrip().split(None, 1)
    if len(parts) != 2:
        return None, text
    cmd = parts[0].lower()
    if cmd == _QUEUE:
        return "queue", parts[1]
    if cmd == _STEER:
        return "steer", parts[1]
    return None, text


def is_bare_override(text: str) -> bool:
    parts = text.strip().split()
    return len(parts) == 1 and parts[0].lower() in (_QUEUE, _STEER)


def resolve_mode(cfg: Any, override: str | None) -> str:
    """The override, else ``messaging.queue_mode``; anything but ``"queue"`` steers."""
    mode = override or str(getattr(getattr(cfg, "messaging", None), "queue_mode", "steer"))
    return "queue" if mode == "queue" else "steer"


@dataclass(frozen=True)
class Inbound:
    """What the linked route needs to steer one typed Slack message."""

    msg_ts: str
    override: str | None
    #: False for a message with files (a steer carries text only), a shared user's
    #: or a trusted bot's: it is always queued.
    steerable: bool
    #: The thread the message is in; empty outside a thread.
    thread_ts: str = ""


_INBOUND: contextvars.ContextVar[Inbound | None] = contextvars.ContextVar(
    "slack_midturn_inbound", default=None
)


def set_inbound(value: Inbound | None) -> None:
    _INBOUND.set(value)


def take_inbound() -> Inbound | None:
    value = _INBOUND.get()
    _INBOUND.set(None)
    return value


async def react(slack: Any, channel: str, msg_ts: str, name: str) -> None:
    """Best-effort reaction on the user's message; a code channel without reactions gets none."""
    if not slack or not msg_ts:
        return
    try:
        from kiro_crew.slack.code_channels.binding import no_reactions

        if no_reactions(channel):
            return
        await slack.add_reaction(channel, msg_ts, name)
    except Exception:
        logger.debug("slack: %s reaction failed", name, exc_info=True)


async def take_override(
    orch: Any, channel: str, reply_ts: str, msg_ts: str, text: str, *, steerable: bool
) -> str | None:
    """*text* without its ``!queue`` / ``!steer`` prefix, recorded for this message's route.

    ``None`` for a lone prefix, which is answered with :data:`BARE_PREFIX_HINT`
    instead of reaching the model as the literal word. *steerable* is False for a
    message that must never steer: one with files (a steer carries text only), a
    shared user's, a trusted bot's.
    """
    if is_bare_override(text):
        slack = getattr(orch, "slack", None)
        if slack:
            await slack.post_message(channel, BARE_PREFIX_HINT, reply_ts)
        return None
    override, rest = parse_override(text)
    set_inbound(Inbound(msg_ts, override, steerable, reply_ts))
    return rest


def answered_before_a_turn(text: str, context_builder: Any) -> bool:
    """Whether a turn's start would answer *text* itself instead of sending it to the model.

    What ``_dispatch_before_turn`` takes before the prompt: a ``!`` command, a
    ``!temporary`` / ``!incognito`` modifier anywhere in the text, the ``status`` /
    ``sessions`` / ``spawn`` / ``bg`` / ``task run`` / ``project run`` / ``cron``
    keywords, the transport's ``ping`` shortcut, and a message hook that replies
    or rewrites; and a leading ``/`` command (``/agent``, ``/compact``), which
    the harness runs from the drained prompt. A steer would hand the model the
    literal text and skip all of it (an incognito message would be stored), so
    such a message is queued and the drain runs it through them.
    """
    from kiro_crew.hooks import HOOK_PASSTHROUGH
    from kiro_crew.messaging import privacy_mode
    from kiro_crew.slack.handler import _is_control_message, _is_sessions_keyword
    from kiro_crew.slack.handler_runtime.dispatch import _message_command_text

    if _is_control_message(text) or privacy_mode.strip_tokens(text)[1]:
        return True
    low = text.strip().lower()
    if low in ("status", "ping") or _is_sessions_keyword(text):
        return True
    if low.startswith(("spawn ", "bg ", "task run ", "project run ")):
        return True
    words = low.split()
    if len(words) > 1 and words[0] == "cron":
        return True
    if _message_command_text(text).startswith("/"):
        return True
    hooks = getattr(context_builder, "hooks", None)
    if hooks is None:
        return False
    try:
        return bool(hooks.on_message(text).action != HOOK_PASSTHROUGH)
    except Exception:
        logger.debug("slack: message hook probe failed; queueing", exc_info=True)
        return True


async def steer_if_busy(
    orch: Any, session_key: str, text: str, *, channel: str, msg_ts: str, task_busy: bool
) -> bool:
    """Steer *text* into the running session; True when landed or delivery is ambiguous.

    False (the caller queues it, as before) when the session is idle, for queue
    mode, a message that is not steerable or that a turn's start answers itself
    (:func:`answered_before_a_turn`), a ``!stop`` still settling on the session
    (it would cancel the turn the steer went into, and nothing would hold the
    text), a thread a dashboard chat owns (a single-session DM keys every thread
    by the channel, so the busy turn is not that thread's), no provider, a provider without a
    steer channel, a turn not genuinely in flight (``has_active_turn``: the lease
    outlives the prompt through post-turn bookkeeping, and a steer there is
    swallowed), or a steer the provider declined or raised on with definite non-delivery.
    """
    sessions = getattr(orch, "sessions", None)
    inbound = _INBOUND.get()
    if sessions is None or inbound is None or not inbound.steerable:
        return False
    if not (task_busy or sessions.is_busy(session_key)):
        return False
    from kiro_crew.slack.events_queue import _stops_in_flight
    from kiro_crew.slack.handler import slack_cfg
    from kiro_crew.slack.thread_parent import is_slack_born

    if session_key in _stops_in_flight.get(orch, {}):
        return False
    owner = sessions.get_session_for_thread(inbound.thread_ts) if inbound.thread_ts else None
    if isinstance(owner, str) and owner and not is_slack_born(owner):
        return False
    if answered_before_a_turn(text, getattr(orch, "ctx_builder", None)):
        return False

    if resolve_mode(slack_cfg(orch), inbound.override) == "queue":
        return False
    provider = sessions.get_provider(session_key)
    steer = getattr(provider, "steer", None)
    if steer is None or not getattr(provider, "supports_steer", False):
        return False
    has_active = getattr(provider, "has_active_turn", None)
    if has_active is not None and not has_active():
        return False
    try:
        steered = bool(await steer(text))
    except Exception as exc:
        if getattr(exc, "ambiguous_delivery", False) is True:
            logger.warning(
                "slack: steer into %s may have been delivered; not replaying",
                session_key,
                exc_info=True,
            )
            return True
        logger.warning("slack: steer into %s raised; queueing instead", session_key, exc_info=True)
        return False
    if steered:
        logger.info("Message %s steered into the running turn of %s", msg_ts, session_key)
        await react(getattr(orch, "slack", None), channel, msg_ts, STEER_REACTION)
    return steered


#: ``steer_linked`` outcomes. ``DECLINED``: nothing holds the text, the caller queues it.
LINKED_DECLINED = "declined"
#: The text is in the running turn, or already somewhere that runs it: nothing more to do.
LINKED_DONE = "done"
#: The hand-off refused the message; the user was told.
LINKED_REFUSED = "refused"


async def steer_linked(
    state: Any,
    slot: Any,
    text: str,
    *,
    channel: str,
    slack: Any,
    reply_ts: str,
    cfg: Any,
    inbound: Inbound | None,
    gated: bool,
    user_meta: dict[str, Any] | None = None,
) -> str:
    """Steer *text* into the linked dashboard *slot*'s running turn.

    Only for a typed message (*inbound* set by the event route) that is
    steerable, in steer mode, into an available running slot on an ungated route.
    The hand-off owns both the steer and its queue fallback, as on Discord, and
    stamps the entry it queues as Slack's own queue does: *channel* as its source
    channel and *user_meta* as its row meta.
    Every decline is synchronous, so the caller's Slack queue path awaits nothing.
    A leading ``/`` command (``/agent <name>``, ``/tools``) is declined too: the
    slot's turn start runs it, and a steer would hand the model the literal text.
    """
    from kiro_crew.dashboard.channel_handoff import (
        HANDOFF_QUEUED,
        HANDOFF_STEERED,
        RESUMED_BUSY_MOVED_REFUSAL,
        hand_to_resumed_slot,
        resumed_busy_reply,
        slot_unable_to_take,
    )
    from kiro_crew.slack.handler_runtime.dispatch import _message_command_text

    if (
        gated
        or inbound is None
        or not inbound.steerable
        or resolve_mode(cfg, inbound.override) == "queue"
        or not getattr(slot, "running", False)
        or slot_unable_to_take(slot)
        or _message_command_text(text).startswith("/")
    ):
        return LINKED_DECLINED

    outcome = await hand_to_resumed_slot(
        state,
        f"dashboard:{slot.key}",
        text,
        mode="steer",
        has_attachments=False,
        channel_type="slack",
        conversation_id=channel,
        source_channels=(channel,),
        user_meta=user_meta,
    )
    if outcome.kind == HANDOFF_STEERED:
        logger.info("Linked Slack message %s steered into slot %s", inbound.msg_ts, slot.key)
        await react(slack, channel, inbound.msg_ts, STEER_REACTION)
        return LINKED_DONE
    if outcome.kind == HANDOFF_QUEUED:
        # The hand-off queued it, its turn's teardown requeued it, or its
        # successor holds it: queueing again would run it twice.
        await react(slack, channel, inbound.msg_ts, QUEUE_REACTION)
        return LINKED_DONE
    await slack.post_message(
        channel, resumed_busy_reply(outcome, busy_refusal=RESUMED_BUSY_MOVED_REFUSAL), reply_ts
    )
    return LINKED_REFUSED
