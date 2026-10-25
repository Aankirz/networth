"""Signed /u/{token} links: a real token opens the user's page, anything else is a friendly 404."""

from __future__ import annotations

import datetime as dt
import html
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from networth.app import links
from networth.app.services import Services
from networth.app.settings import Settings
from networth.app.store import Step, Store
from networth.bot.message import Link
from networth.web.routes import router, settings
from tests.test_onboarding import USER, Chat, onboard

SECRET = "test-signing-secret-not-real"
NOW = dt.datetime(2026, 10, 25, 6, tzinfo=dt.UTC)


def test_a_signed_token_verifies_until_it_expires() -> None:
    token = links.sign("abc_-123", SECRET, NOW)
    assert links.verify(token, SECRET, NOW) == "abc_-123"
    later = NOW + dt.timedelta(days=links.LINK_DAYS, seconds=1)
    assert links.verify(token, SECRET, later) is None


@pytest.mark.parametrize("mangle", [
    lambda t: t[:-1] + ("0" if t[-1] != "0" else "1"),
    lambda t: "someone_else" + t[t.index("."):],
    lambda t: t.replace(t.split(".")[1], str(int(t.split(".")[1]) + 86400)),
    lambda t: t.split(".")[0],
    lambda t: "",
])  # fmt: skip
def test_a_tampered_token_does_not_verify(mangle) -> None:
    assert links.verify(mangle(links.sign("abc", SECRET, NOW)), SECRET, NOW) is None


def test_another_secret_does_not_verify() -> None:
    assert links.verify(links.sign("abc", SECRET, NOW), "other", NOW) is None


@pytest.fixture
def chat(tmp_path: Path) -> Chat:
    services = Services(tmp_path / "data", "https://nw.example", link_secret=SECRET)
    chat = Chat(tmp_path, services)
    onboard(chat)
    return chat


@pytest.fixture
def client(chat: Chat) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[settings] = lambda: Settings(
        chat.store.path.parent, None, None, "https://nw.example", SECRET
    )
    return TestClient(app)


def page_path(store: Store) -> str:
    profile = store.get_profile(USER)
    assert profile is not None
    return f"/u/{links.sign(profile.link_token, SECRET, dt.datetime.now(dt.UTC))}"


def test_the_user_page_shows_the_plan_and_the_last_brief(chat: Chat, client) -> None:
    chat.say("/brief")
    response = client.get(page_path(chat.store))
    assert response.status_code == 200
    assert (
        "Balanced. 20% safe money (liquid, gilt, FD), 70% broad index funds, "
        "10% single shares or themes" in response.text
    )
    assert "Your plan: Balanced, the one you chose." in response.text
    assert "Research, not advice" not in response.text
    assert response.headers["x-robots-tag"] == "noindex"


def test_a_tampered_link_gets_the_friendly_404(chat: Chat, client) -> None:
    response = client.get(page_path(chat.store)[:-2] + "zz")
    assert response.status_code == 404
    assert "This link has expired or isn't right." in html.unescape(response.text)
    assert "Research, not advice" not in response.text


def test_plan_command_hands_out_a_working_link(chat: Chat, client) -> None:
    url = page_link(chat)
    assert url.startswith("https://nw.example/u/")
    assert client.get(url.removeprefix("https://nw.example")).status_code == 200


def page_link(chat: Chat) -> str:
    """The page link /plan sends, read from the message it built."""
    chat.say("/plan")
    m = next(m for m in reversed(chat.bot.messages) if m.title == "Your plan")
    return next(b.url for b in m.body if isinstance(b, Link))


def plan_link(chat: Chat) -> str:
    return page_link(chat).removeprefix("https://nw.example")


def sent_links(chat: Chat) -> list[str]:
    """Every /u path the bot has sent, from message bodies and buttons alike."""
    urls = [b.url for m in chat.bot.messages for b in m.body if isinstance(b, Link)]
    urls += [b.url for _, _, rows in chat.bot.sent for row in rows for b in row if b.url]
    return [u.removeprefix("https://nw.example") for u in urls if "/u/" in u]


def test_every_link_sent_keeps_working_after_newer_ones(chat: Chat, client) -> None:
    """Live 404: each /plan, brief and plan question minted a new token, so the link the user
    opened a minute later was already retired."""
    chat.say("/brief")
    chat.say("/plan")
    chat.store.save_profile(replace(chat.profile, step=Step.DONE))  # leave plan editing
    chat.say("what is my plan?")
    chat.say("/brief")
    paths = sent_links(chat)
    assert len(paths) >= 3
    assert [client.get(p).status_code for p in paths] == [200] * len(paths)


@pytest.mark.parametrize("token", ["abc.².sig", "abc.1999999999.sïg", "äbc.1999999999.sig"])
def test_a_non_ascii_link_gets_the_friendly_404_not_a_500(client, token: str) -> None:
    assert client.get(f"/u/{token}").status_code == 404


@pytest.mark.parametrize("page", ["", "/holdings"])
def test_a_stopped_users_pages_get_the_friendly_404(chat: Chat, client, page: str) -> None:
    path = page_path(chat.store) + page
    chat.say("/stop")
    response = client.get(path)
    assert response.status_code == 404
    assert "This link has expired or isn't right." in html.unescape(response.text)
