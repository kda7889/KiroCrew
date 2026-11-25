"""``!bot <name>`` joins a Slack thread to the Bot's own dashboard chat (``slack/bot_chat.py``).

With the Bot's chat open on the dashboard, the thread is linked to it the way Discord's
``!bot`` binds: each later message runs (or queues) on that chat, so the owner sees it on
the Bots page, and the chat's replies go back to the thread. With none open the thread
keeps the older per-thread Bot session (``test_slack_thread_bot_switch.py``).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import test_slack_thread_bot_switch as _switch
from chat_test_helpers import _make_state
from slack_transport_dispatch_helpers import _MSG_TS, RecordingSlackClient
from test_slack_thread_bot_switch import (
    _KEY,
    _OTHER_KEY,
    _OTHER_TS,
    _OWNER,
    _posts,
    _send,
    _Sessions,
)

from kiro_crew.members import DM_SLOT_MODE, member_slot_key
from kiro_crew.messaging.link import ChannelLink
from kiro_crew.slack import handler as _handler

# The shared fixtures, bound by assignment rather than import: pyflakes reads a test's
# ``bots`` / ``audit`` parameter as a redefinition of an imported name, not of a global.
bots = _switch.bots
audit = _switch.audit

_SECOND_TS = "1700000900.000100"


def _bot_chat(ds, bot):
    return ds.get_or_create_slot(name=member_slot_key(bot), agent=bot, mode=DM_SLOT_MODE)


@pytest.fixture()
def ds(tmp_path, monkeypatch):
    """A dashboard with Bot web-frontend's own chat open, as the Bots page leaves it."""
    state = _make_state(tmp_path)
    # The real map reads a Slack link back as the session's mirror (``get_mirror_link``).
    plain = state.sessions.get_mirror_link.side_effect

    def _mirror(key):
        held = plain(key)
        if held is not None:
            return held
        ts, ch = state.sessions.get_slack_link(key)
        return ChannelLink("slack", channel_id=ch, thread_id=ts) if ts else None

    state.sessions.get_mirror_link = MagicMock(side_effect=_mirror)
    _bot_chat(state, "web-frontend")
    monkeypatch.setattr(_handler, "_dashboard_state", state)
    return state


@pytest.fixture()
def run_chat():
    with patch("kiro_crew.dashboard.chat._run_chat", new_callable=AsyncMock) as mock:
        yield mock


def _run(*messages):
    """Send each ``(text, thread_ts, msg_ts)`` from the owner in channel D1 (a DM)."""
    slack, sessions = RecordingSlackClient(), _Sessions()

    async def _scenario():
        for text, thread_ts, msg_ts in messages:
            await _send(slack, sessions, text, thread_ts=thread_ts, msg_ts=msg_ts)
        # Let the turn tasks the linked route started run to their (mocked) end.
        await asyncio.sleep(0)

    asyncio.run(_scenario())
    return slack, sessions


def _first(text, ts=_MSG_TS):
    return (text, None, ts)


def _reply(text, ts=_MSG_TS, n=200):
    return (text, ts, f"{ts.split('.')[0]}.000{n}")


def _user_rows(slot):
    return [m["content"] for m in slot.messages if m.get("role") == "user"]


class TestJoin:
    def test_the_reply_lands_in_the_bots_own_chat(self, bots, audit, ds, run_chat):
        slot = ds._slots[member_slot_key("web-frontend")]
        slack, sessions = _run(_first("!bot web-frontend"), _reply("hello"))

        assert slot._slack_linked and slot._slack_thread_ts == _MSG_TS
        assert ds.get_linked_slot(_MSG_TS) is slot
        assert _user_rows(slot) == ["hello"]
        [call] = run_chat.await_args_list
        assert call.args[1] is slot and call.args[2] == "hello"
        # No per-thread Bot session: the turn ran in the chat, not on Slack's own key.
        assert sessions.calls == []
        assert _KEY not in _handler._thread_agents
        assert any("talks to Bot *web-frontend* in its own chat" in p for p in _posts(slack))

    def test_replies_go_back_to_the_thread(self, bots, audit, ds, run_chat):
        # The chat's turns mirror to the Slack link it now holds.
        slot = ds._slots[member_slot_key("web-frontend")]
        _run(_first("!bot web-frontend"))

        key = "dashboard:" + slot.key
        assert ds.sessions.get_slack_link(key) == (_MSG_TS, "D1")

    def test_a_running_dashboard_turn_queues_the_slack_message(self, bots, audit, ds, run_chat):
        slot = ds._slots[member_slot_key("web-frontend")]
        slot.append("user", "from the dashboard", "msg msg-u")
        slot._turn_admission_reserved = True  # a dashboard turn holds the chat
        _run(_first("!bot web-frontend"), _reply("one", n=201), _reply("two", n=202))

        run_chat.assert_not_awaited()
        assert [e["content"] for e in slot._queue] == ["one", "two"]
        assert _user_rows(slot) == ["from the dashboard", "one", "two"]

    def test_naming_the_same_bot_again_keeps_the_link(self, bots, audit, ds, run_chat):
        slot = ds._slots[member_slot_key("web-frontend")]
        slack, _ = _run(_first("!bot web-frontend"), _reply("!bot web-frontend"))

        assert ds.get_linked_slot(_MSG_TS) is slot
        assert "already talks to Bot *web-frontend*" in _posts(slack)[-1]


class TestNearbyInputs:
    def test_a_thread_with_no_bot_is_unchanged(self, bots, audit, ds, run_chat):
        slot = ds._slots[member_slot_key("web-frontend")]
        _slack, sessions = _run(_first("!bot web-frontend"), ("hi there", None, _OTHER_TS))

        assert _user_rows(slot) == []
        assert ds.get_linked_slot(_OTHER_TS) is None
        [(key, kw)] = sessions.calls
        assert key == _OTHER_KEY and "crew_agent" not in kw

    def test_a_second_thread_to_the_same_bot_is_refused(self, bots, audit, ds, run_chat):
        slot = ds._slots[member_slot_key("web-frontend")]
        slack, sessions = _run(
            _first("!bot web-frontend"),
            _first("!bot web-frontend", ts=_SECOND_TS),
            _reply("still here?", ts=_SECOND_TS),
        )

        assert ds.get_linked_slot(_MSG_TS) is slot
        assert ds.get_linked_slot(_SECOND_TS) is None
        assert any("already talking to" in p and "another Slack thread" in p for p in _posts(slack))
        # The refused thread runs as before, on its own session and the default agent.
        assert _user_rows(slot) == []
        assert [key for key, _kw in sessions.calls] == ["slack:" + _SECOND_TS]

    def test_a_chat_bound_to_another_channel_is_refused(self, bots, audit, ds, run_chat):
        slot = ds._slots[member_slot_key("web-frontend")]
        ds.sessions.set_mirror_link(
            "dashboard:" + slot.key, ChannelLink("discord", channel_id="9"), accepts_inbound=True
        )
        slack, _ = _run(_first("!bot web-frontend"))

        assert ds.get_linked_slot(_MSG_TS) is None
        assert "already talking to Discord" in _posts(slack)[-1]

    def test_off_leaves_the_chat_and_the_thread_runs_on_its_own(self, bots, audit, ds, run_chat):
        slot = ds._slots[member_slot_key("web-frontend")]
        slack, sessions = _run(
            _first("!bot web-frontend"), _reply("!bot off", n=201), _reply("after", n=202)
        )

        assert not slot._slack_linked and ds.get_linked_slot(_MSG_TS) is None
        assert ds.sessions.get_slack_link("dashboard:" + slot.key) == (None, None)
        assert _user_rows(slot) == []
        assert any("left Bot *web-frontend*'s chat" in p for p in _posts(slack))
        assert [key for key, _kw in sessions.calls] == [_KEY]

    def test_a_refused_switch_keeps_the_thread_in_the_chat(self, bots, audit, ds, run_chat):
        slot = ds._slots[member_slot_key("web-frontend")]
        slack, _ = _run(_first("!bot web-frontend"), _reply("!bot web-frontnd", n=201))

        assert ds.get_linked_slot(_MSG_TS) is slot
        assert "Unknown Bot `web-frontnd`" in _posts(slack)[-1]
        assert not any("left Bot" in p for p in _posts(slack))

    def test_a_shared_user_cannot_take_the_thread_out_of_the_chat(
        self, bots, audit, ds, run_chat, monkeypatch
    ):
        # ``!bot`` stays the owner's in a joined thread too: the router refuses first.
        monkeypatch.setattr(_handler, "is_shared_user", lambda uid: uid == _switch._SHARED)
        slot = ds._slots[member_slot_key("web-frontend")]
        slack, sessions = RecordingSlackClient(), _Sessions()

        async def _scenario():
            await _send(slack, sessions, "!bot web-frontend")
            for n, text in enumerate(("!bot off", "!bot research"), start=201):
                await _send(
                    slack,
                    sessions,
                    text,
                    user_id=_switch._SHARED,
                    thread_ts=_MSG_TS,
                    msg_ts=f"{_MSG_TS.split('.')[0]}.000{n}",
                )

        asyncio.run(_scenario())

        assert ds.get_linked_slot(_MSG_TS) is slot
        assert _posts(slack)[-2:] == ["⛔ Owner-only command."] * 2
        assert not any("left Bot" in p for p in _posts(slack))
        assert _user_rows(slot) == []

    def test_a_thread_whose_memory_belongs_to_another_bot_is_refused(
        self, bots, audit, ds, run_chat
    ):
        held = "This thread's memory belongs to Bot 'vault'. Start a new thread."
        with patch.object(_handler, "memory_binding_refusal", AsyncMock(return_value=held)):
            slack, _ = _run(_first("!bot web-frontend"))

        assert ds.get_linked_slot(_MSG_TS) is None
        assert _posts(slack)[-1] == f"❌ {held}"

    def test_a_damaged_memory_record_is_refused_and_audited(self, bots, audit, ds, run_chat):
        from kiro_crew.memory_stores import UnknownMemoryStore

        broken = AsyncMock(side_effect=UnknownMemoryStore("no memory store 'gone'"))
        with patch.object(_handler, "memory_binding_refusal", broken):
            slack, _ = _run(_first("!bot web-frontend"))

        assert ds.get_linked_slot(_MSG_TS) is None
        assert "no memory store 'gone'" in _posts(slack)[-1]
        outcomes = [c.kwargs.get("outcome") for c in audit.log_tool_invocation.call_args_list]
        assert "agent_denied_memory_binding" in outcomes

    def test_switching_out_asks_the_memory_rule_on_the_threads_own_key(
        self, bots, audit, ds, run_chat
    ):
        slot = ds._slots[member_slot_key("web-frontend")]
        asked = AsyncMock(return_value=None)
        slack, sessions = RecordingSlackClient(), _Sessions()

        async def _scenario():
            await _send(slack, sessions, "!bot web-frontend", msg_ts=_MSG_TS)
            # The transport routes a joined thread under the Bot chat's dashboard key.
            sessions.linked_owner = "dashboard:" + slot.key
            text, thread_ts, msg_ts = _reply("!bot research", n=201)
            await _send(slack, sessions, text, thread_ts=thread_ts, msg_ts=msg_ts)

        with patch.object(_handler, "memory_binding_refusal", asked):
            asyncio.run(_scenario())

        # The join asks it for web-frontend; the switch out asks it for research.
        assert {c.args for c in asked.await_args_list} == {
            (_KEY, "web-frontend"),
            (_KEY, "research"),
        }
        assert not slot._slack_linked

    def test_a_switch_the_memory_rule_refuses_keeps_the_thread_in_the_chat(
        self, bots, audit, ds, run_chat
    ):
        slot = ds._slots[member_slot_key("web-frontend")]
        held = "This thread's memory belongs to Bot 'web-frontend'. Start a new thread."
        rule = AsyncMock(side_effect=lambda _key, bot: held if bot == "research" else None)
        with patch.object(_handler, "memory_binding_refusal", rule):
            slack, _ = _run(_first("!bot web-frontend"), _reply("!bot research", n=201))

        assert ds.get_linked_slot(_MSG_TS) is slot
        assert _posts(slack)[-1] == f"❌ {held}"
        assert not any("left Bot" in p for p in _posts(slack))

    def test_a_join_whose_save_fails_is_taken_back_down(self, bots, audit, ds, run_chat):
        slot = ds._slots[member_slot_key("web-frontend")]
        ds.sessions.aflush = AsyncMock(side_effect=OSError("disk full"))
        slack, _ = _run(_first("!bot web-frontend"))

        assert "Could not save joining Bot *web-frontend*'s chat" in _posts(slack)[-1]
        assert not slot._slack_linked and ds.get_linked_slot(_MSG_TS) is None
        assert ds.sessions.get_slack_link("dashboard:" + slot.key) == (None, None)

    def test_off_whose_save_fails_does_not_say_it_left(self, bots, audit, ds, run_chat):
        # The join saves; the leave's save is the one that fails.
        ds.sessions.aflush = AsyncMock(side_effect=[None, OSError("read-only data home")])
        slack, _ = _run(_first("!bot web-frontend"), _reply("!bot off", n=201))

        assert "Could not save leaving Bot *web-frontend*'s chat" in _posts(slack)[-1]
        assert not any("left Bot *web-frontend*'s chat" in p for p in _posts(slack))

    def test_switching_bots_mid_thread_moves_the_thread(self, bots, audit, ds, run_chat):
        first = ds._slots[member_slot_key("web-frontend")]
        second = _bot_chat(ds, "research")
        _run(_first("!bot web-frontend"), _reply("!bot research", n=201), _reply("hi", n=202))

        assert not first._slack_linked
        assert ds.get_linked_slot(_MSG_TS) is second
        assert _user_rows(second) == ["hi"] and _user_rows(first) == []

    def test_switching_to_a_bot_with_no_open_chat_runs_it_on_the_thread(
        self, bots, audit, ds, run_chat
    ):
        first = ds._slots[member_slot_key("web-frontend")]
        _slack, sessions = _run(
            _first("!bot web-frontend"), _reply("!bot research", n=201), _reply("hi", n=202)
        )

        assert not first._slack_linked
        assert _handler._thread_agents[_KEY] == "research"
        [(key, kw)] = sessions.calls
        assert key == _KEY and kw["crew_agent"] == "research"

    def test_no_open_chat_keeps_the_per_thread_bot(self, bots, audit, ds, run_chat):
        _slack, sessions = _run(_first("!bot research"), _reply("hello"))

        assert ds.get_linked_slot(_MSG_TS) is None
        assert _handler._thread_agents[_KEY] == "research"
        assert sessions.calls[0][1]["crew_agent"] == "research"
        run_chat.assert_not_awaited()

    def test_a_pinned_channel_keeps_the_per_thread_bot(self, bots, audit, ds, run_chat):
        with patch.object(_handler, "channel_pinned_agent", return_value="kirocrew"):
            slack, sessions = RecordingSlackClient(), _Sessions()

            async def _scenario():
                await transport_send(slack, sessions, "!bot web-frontend")

            asyncio.run(_scenario())

        assert ds.get_linked_slot(_MSG_TS) is None
        assert _handler._thread_agents[_KEY] == "web-frontend"

    def test_a_flat_dm_keeps_the_per_thread_bot(self, bots, audit, ds, run_chat):
        # ``slack.dm_single_session``: the DM is ONE conversation keyed by the channel. A
        # join links one message's ts, so the next top-level message would miss the Bot.
        slot = ds._slots[member_slot_key("web-frontend")]
        slack, sessions = RecordingSlackClient(), _Sessions()

        async def _scenario():
            await _send(slack, sessions, "!bot web-frontend", dm_single_session=True)
            await _send(slack, sessions, "hello", msg_ts=_OTHER_TS, dm_single_session=True)

        asyncio.run(_scenario())

        assert not slot._slack_linked and ds.get_linked_slot(_MSG_TS) is None
        assert _handler._thread_agents["slack:D1"] == "web-frontend"
        run_chat.assert_not_awaited()
        assert sessions.calls[-1][0] == "slack:D1"
        assert sessions.calls[-1][1]["crew_agent"] == "web-frontend"

    def test_a_review_channel_keeps_the_per_thread_bot(self, bots, audit, ds, run_chat):
        # A ``review`` channel shows each reply to the owner as a draft first; a chat's
        # mirrored replies would post without it.
        from kiro_crew.config import live
        from kiro_crew.config.loader import ACTIVATION_REVIEW, ChannelConfig

        live.snapshot().slack_channels["C0PINNED"] = ChannelConfig(activation=ACTIVATION_REVIEW)
        slack, sessions = RecordingSlackClient(), _Sessions()

        async def _scenario():
            await transport_send(slack, sessions, "!bot web-frontend")

        asyncio.run(_scenario())

        assert ds.get_linked_slot(_MSG_TS) is None
        assert _handler._thread_agents[_KEY] == "web-frontend"

    def test_a_temporary_thread_keeps_the_per_thread_bot(self, bots, audit, ds, run_chat):
        # The Bot's chat is saved; a thread marked ``!temporary`` must stay off it.
        from kiro_crew.messaging import privacy_mode

        privacy_mode.mark_temporary(_KEY)
        try:
            _run(_first("!bot web-frontend"))
        finally:
            privacy_mode.reset()

        assert ds.get_linked_slot(_MSG_TS) is None
        assert _handler._thread_agents[_KEY] == "web-frontend"

    def test_a_join_landing_during_the_store_load_is_seen(self, bots, audit, ds, run_chat):
        # Another thread takes the chat while this join waits on the store: the check
        # runs after that wait, so this thread is refused and the first keeps the chat.
        slot = ds._slots[member_slot_key("web-frontend")]

        async def _other_thread_joins(_operation):
            ds.link_slack(slot.key, _SECOND_TS, "D1")

        with patch(
            "kiro_crew.slack.code_channels.binding.load_store_for_links", _other_thread_joins
        ):
            slack, _ = _run(_first("!bot web-frontend"))

        assert ds.get_linked_slot(_SECOND_TS) is slot and ds.get_linked_slot(_MSG_TS) is None
        assert "already talking to" in _posts(slack)[-1]


async def transport_send(slack, sessions, text):
    from kiro_crew.slack import transport_dispatch

    await transport_dispatch.handle_message_transport(
        slack=slack,
        sessions=sessions,
        channel="C0PINNED",
        text=text,
        thread_ts=None,
        msg_ts=_MSG_TS,
        user_id=_OWNER,
        context_builder=None,
        conversation_log=None,
    )
