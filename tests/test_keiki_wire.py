"""Keiki's wire: payload parsing, quoted-mail stripping, the HTTP clients, plain email text and
the outbox. No network: httpx2's MockTransport stands in for Keiki."""

from __future__ import annotations

import json
from pathlib import Path

import httpx2
import pytest

from networth.app.store import Profile, Step, Store
from networth.bot.onboarding import Reply
from networth.bot.telegram import Button
from networth.keiki.client import KeikiApi, KeikiError, TurnClient
from networth.keiki.mail import NOTICE, Mail
from networth.keiki.render import plain
from networth.keiki.wire import KeikiTurn, Other, parse, strip_quoted
from tests.keiki_fakes import (
    ADDRESS,
    SLACK_TEAM,
    SLACK_USER,
    TURN_URL,
    FakeApi,
    FakeTurnClient,
    slack_payload,
    turn_payload,
)  # fmt: skip

NOW = "2026-10-25T06:00:00+00:00"


def test_a_turn_payload_parses_into_its_fields_without_silent_messages() -> None:
    payload = turn_payload("What happened today?", traceId="tr_1", heldBack=True)
    payload["messages"].append({"text": "typing...", "silent": True})
    turn = parse(payload)
    assert turn == KeikiTurn("t1", "agent-test", "t1.thread@agentmail.to", ADDRESS, "agentmail",
                             ("What happened today?",), True, False, TURN_URL,
                             "tr_1")  # fmt: skip


def test_a_turn_without_a_trace_id_uses_the_turn_id_as_keiki_does() -> None:
    turn = parse(turn_payload("hi", turn_id="3084530f"))
    assert turn is not None and turn.trace_id == "3084530f"


def test_an_email_sender_is_one_contact_across_threads_whatever_the_case() -> None:
    first = parse(turn_payload("hi", turn_id="a"))
    second = parse(turn_payload("hi", turn_id="b", address=ADDRESS.upper()))
    assert first is not None and second is not None
    assert first.conversation_id != second.conversation_id
    assert first.contact == second.contact == ADDRESS


def test_a_slack_author_is_one_contact_across_threads() -> None:
    first, second = parse(slack_payload("hi", "1.1")), parse(slack_payload("hi", "2.2", "s2"))
    assert first is not None and second is not None
    assert first.conversation_id != second.conversation_id
    assert (first.channel, first.contact) == ("slack", f"slack:{SLACK_TEAM}:{SLACK_USER}")
    assert second.contact == first.contact


@pytest.mark.parametrize("kind", ["keiki.turn.arrival", "keiki.turn.cancelled", "keiki.reaction"])
def test_arrivals_cancellations_and_reactions_carry_no_work(kind: str) -> None:
    assert parse({"type": kind, "agentId": "agent-test"}) == Other(kind, "agent-test")


@pytest.mark.parametrize("payload", [
    [], {"type": "keiki.turn"}, {"type": "keiki.other", "agentId": "a"},
    {**turn_payload("hi"), "turnId": ""}, {**turn_payload("hi"), "keiki": {}},
])  # fmt: skip
def test_an_unknown_shape_parses_to_none(payload: object) -> None:
    assert parse(payload) is None


def test_quoted_mail_is_stripped_from_an_email_reply() -> None:
    reply = (
        "what is OFS?\n\n> earlier line\nOn Fri, 24 Oct 2026 at 09:00, Networth "
        "<networth@agentmail.to> wrote:\n> Investing day, Oct 24."
    )
    assert strip_quoted(reply) == "what is OFS?"
    assert strip_quoted("hi\n-----Original Message-----\nold text") == "hi"


def mock(handler) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_a_turn_reply_posts_the_text_and_key_with_the_turn_token() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json={"ok": True})

    client = TurnClient(TURN_URL, "tok", client=mock(handler))
    client.send("Hello", "t1:1")
    client.complete("completed")
    assert [str(r.url) for r in seen] == [f"{TURN_URL}/messages", f"{TURN_URL}/complete"]
    assert json.loads(seen[0].content) == {"text": "Hello", "idempotencyKey": "t1:1"}
    assert json.loads(seen[1].content) == {"status": "completed"}
    assert seen[0].headers["authorization"] == "Bearer tok"


def test_a_closed_turn_counts_as_done_and_other_failures_raise_without_the_token() -> None:
    closed = TurnClient(TURN_URL, "tok", client=mock(
        lambda r: httpx2.Response(409, json={"error": "turn_closed"})))  # fmt: skip
    closed.complete("completed")
    broken = TurnClient(TURN_URL, "tok", client=mock(lambda r: httpx2.Response(500)))
    with pytest.raises(KeikiError) as err:
        broken.send("Hello", "t1:1")
    assert "tok" not in str(err.value)


def test_a_notice_reports_keikis_outcome_or_no_conversation() -> None:
    seen: list[httpx2.Request] = []

    def ok(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json={"outcome": "dispatched"})

    assert KeikiApi("key", "agent-1", client=mock(ok)).notice(ADDRESS, "text") == "dispatched"
    assert str(seen[0].url).endswith("/developer/agents/agent-1/notice")
    assert json.loads(seen[0].content) == {"text": "text", "phone": ADDRESS}
    missing = mock(lambda r: httpx2.Response(404, json={"error": "no_conversation"}))
    assert KeikiApi("key", "agent-1", client=missing).notice(ADDRESS, "t") == "no_conversation"


def test_link_buttons_become_lines_and_answer_buttons_one_reply_line() -> None:
    buttons = (
        (Button("A house", "ob:goal:house"), Button("Retirement", "ob:goal:retirement")),
        (Button("Why?", "", "https://nw.example/why/rbi_hike/^NSEBANK"),),
        (Button("Invest as planned", "br:ok"), Button("Stop 1", "wt:stop:7")),
    )
    assert plain("What's this money for?", buttons) == (
        "What's this money for?\n\nWhy?: https://nw.example/why/rbi_hike/^NSEBANK\n"
        "Reply with one of: A house, Retirement"
    )
    assert plain("Just text") == "Just text"


def profile(user_id: str = "tg:1") -> Profile:
    return Profile(user_id, "telegram", 1, Step.DONE, "t", NOW, NOW)


def test_queued_mail_waits_for_a_turn_and_goes_out_once(tmp_path: Path) -> None:
    store, api = Store(tmp_path), FakeApi()
    store.bind_contact(ADDRESS, "tg:1")
    mail = Mail(store, api)
    reply = Reply("Investing day.", ((Button("Why?", "", "https://nw.example/why"),),))
    assert mail.queue(profile(), reply)
    assert api.notices == [(ADDRESS, NOTICE)]
    client = FakeTurnClient()
    assert mail.flush(ADDRESS, client) == 1
    assert client.sent == [("Investing day.\n\nWhy?: https://nw.example/why", "outbox:1")]
    assert mail.flush(ADDRESS, client) == 0, "a sent row is not sent again"


def test_mail_for_a_user_with_no_email_is_not_queued(tmp_path: Path) -> None:
    api = FakeApi()
    assert not Mail(Store(tmp_path), api).queue(profile(), Reply("Hi"))
    assert api.notices == []


def test_a_failed_flush_keeps_the_row_for_the_next_turn(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.bind_contact(ADDRESS, "tg:1")
    mail = Mail(store, FakeApi())
    mail.queue(profile(), Reply("Hi"))
    assert mail.flush(ADDRESS, FakeTurnClient(fail_send=True)) == 0
    assert mail.flush(ADDRESS, FakeTurnClient()) == 1


def test_a_slack_contact_is_never_mailed(tmp_path: Path) -> None:
    store, api = Store(tmp_path), FakeApi()
    store.bind_contact(f"slack:{SLACK_TEAM}:{SLACK_USER}", "tg:1")
    assert not Mail(store, api).queue(profile(), Reply("brief"))
    assert api.notices == []


def test_a_rebound_contact_points_at_the_newest_user(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.bind_contact(ADDRESS, "kk:new")
    store.bind_contact(ADDRESS, "tg:1")
    assert store.contact_user(ADDRESS) == "tg:1"
    assert store.contact_for("tg:1") == ADDRESS
    assert store.contact_for("kk:new") is None
