"""The message shape and its two renders: Telegram HTML (escaped in one place, with a plain
fallback and link previews off by default) and plain text (Keiki email, logs, the guard)."""

from __future__ import annotations

import html
import json
import logging
import re

import httpx2
import pytest

from networth import guard
from networth.bot.message import FOOTER, Link, Message, from_stored, plain, say, to_json
from networth.bot.telegram import TelegramClient
from networth.bot.telegram import html as render_html

TOKEN = "123:secret-token"
TAG = re.compile(r"<a href=\"([^\"]*)\">|<[^>]+>")
NASTY = 'RBI <b>hikes</b> & banks </blockquote> "fall"'
SAMPLE = Message(
    title="Morning. ₹1,00,000 is ready.",
    body=(
        "This month's news: RBI rate hike on Oct 20.",
        Link("Your page", "https://n.app/u/x?a=1&b=2"),
    ),
    detail=(
        "Indian banks beat the Nifty 50 in 14 of 22. Normal is 56%.",
        "The Nifty 50 rose in 12 of 22.",
    ),
    footer=say(FOOTER, "en"),
)


def html_text(rendered: str) -> str:
    """What a reader sees in the HTML render: tags gone, entities unescaped, hrefs kept."""
    return html.unescape(TAG.sub(lambda m: f" {m.group(1)} " if m.group(1) else "", rendered))


def client(handler) -> TelegramClient:
    return TelegramClient(TOKEN, client=httpx2.Client(transport=httpx2.MockTransport(handler)))


def test_plain_puts_blank_lines_between_parts_and_writes_links_as_label_and_url() -> None:
    assert plain(SAMPLE) == (
        "Morning. ₹1,00,000 is ready.\n\nThis month's news: RBI rate hike on Oct 20.\n\n"
        "Your page: https://n.app/u/x?a=1&b=2\n\n"
        "Indian banks beat the Nifty 50 in 14 of 22. Normal is 56%.\n"
        "The Nifty 50 rose in 12 of 22.\n\nResearch, not advice."
    )


def test_html_bolds_the_title_folds_the_detail_and_italicises_the_footer() -> None:
    out = render_html(SAMPLE)
    assert out.startswith("<b>Morning. ₹1,00,000 is ready.</b>\n\n")
    assert '<a href="https://n.app/u/x?a=1&amp;b=2">Your page</a>' in out
    assert "<blockquote expandable>Indian banks" in out and out.count("<blockquote") == 1
    assert out.endswith("<i>Research, not advice.</i>")


def test_a_story_title_with_markup_renders_as_text() -> None:
    out = render_html(Message(title=NASTY, body=(NASTY,), detail=(NASTY,), footer=NASTY))
    assert "<b>hikes</b>" not in out and "&lt;b&gt;hikes&lt;/b&gt;" in out
    assert out.count("</blockquote>") == 1, "a title's </blockquote> cannot close ours"
    assert "&amp; banks" in out
    assert set(re.findall(r"</?(\w+)", out)) == {"b", "blockquote", "i"}


def test_a_link_url_cannot_break_out_of_its_href() -> None:
    out = render_html(Message(body=(Link("<x>", 'https://a/"onclick="y'),)))
    assert out == '<a href="https://a/&quot;onclick=&quot;y">&lt;x&gt;</a>'


def test_html_and_plain_hold_the_same_numbers_and_pass_the_guard() -> None:
    shown = html_text(render_html(SAMPLE))
    assert guard.numbers(shown) == guard.numbers(plain(SAMPLE))
    assert guard.check(plain(SAMPLE), plain(SAMPLE)).ok


def test_link_previews_are_off_unless_the_message_names_its_link() -> None:
    seen: list[dict] = []

    def ok(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content))
        return httpx2.Response(200, json={"ok": True, "result": {"message_id": 1}})

    bot = client(ok)
    bot.send_message(1, SAMPLE)
    bot.send_message(1, Message(body=("x",), preview="https://n.app/why/rbi_hike/x"))
    assert seen[0]["link_preview_options"] == {"is_disabled": True}
    assert seen[1]["link_preview_options"] == {"url": "https://n.app/why/rbi_hike/x"}


def test_bad_markup_is_resent_once_as_plain_text_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    seen: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        seen.append(body)
        if "parse_mode" in body:
            return httpx2.Response(400, json={"ok": False, "error_code": 400, "description":
                                   "Bad Request: can't parse entities: unclosed tag"})  # fmt: skip
        return httpx2.Response(200, json={"ok": True, "result": {"message_id": 2}})

    with caplog.at_level(logging.WARNING, logger="networth.bot"):
        assert client(handler).send_message(1, SAMPLE) == {"message_id": 2}
    assert len(seen) == 2
    assert seen[1]["text"] == plain(SAMPLE) and "parse_mode" not in seen[1]
    assert "can't parse entities" in caplog.text
    assert "Morning" not in caplog.text and TOKEN not in caplog.text


def test_other_telegram_errors_are_not_resent() -> None:
    calls: list[int] = []

    def blocked(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(403, json={"ok": False, "description": "Forbidden: blocked"})

    with pytest.raises(Exception, match="Forbidden"):
        client(blocked).send_message(1, SAMPLE)
    assert calls == [1]


def test_a_stored_message_round_trips_and_a_legacy_row_is_plain_text() -> None:
    m = Message("t", ("a", Link("l", "https://x")), ("d",), "f", "https://x")
    assert from_stored(to_json(m)) == m
    assert from_stored("Investing day, Nov 1. ₹1,00,000 ready.") == Message(
        body=("Investing day, Nov 1. ₹1,00,000 ready.",)
    )


def test_say_falls_back_to_english() -> None:
    assert say(FOOTER, "hinglish") == "Research hai, advice nahin."
    assert say(FOOTER, "fr") == say(FOOTER, None) == "Research, not advice."
