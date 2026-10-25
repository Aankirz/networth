"""Google sign-in on the site: the signed token every /api/web route needs, the /weblink code
that ties a Google account to a bot user, per-user chat memory, and the two ways the link goes
(/erase on Telegram and "Forget me" on the site). Fake models, no network."""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from networth.app.settings import Settings
from networth.chat import Intent
from networth.web import api, session
from networth.web.routes import settings
from tests.test_chat import FakeChatModels
from tests.test_links import SECRET
from tests.test_onboarding import USER, handle_update, text_update
from tests.test_web_api import NOW, OTHER_CHAT, OTHER_USER, World, cfg, origins  # noqa: F401 - fixtures

WEB_SECRET = "test-web-secret-0123456789abcdef"
ANA = "google-sub-ana"
BEN = "google-sub-ben"
CODE = re.compile(r"\b(\d{6})\b")
ROUTES = [
    ("get", "/api/web/me", None),
    ("post", "/api/web/link", {"code": "123456"}),
    ("post", "/api/web/forget", None),
    ("get", "/api/web/dashboard", None),
    ("post", "/api/web/chat", {"text": "What happened today?"}),
    ("post", "/api/web/command", {"name": "brief"}),
]


def token(subject: str, *, secret: str = WEB_SECRET, life_s: int = 60, name: str = "Ana") -> str:
    exp = int(dt.datetime.now(dt.UTC).timestamp()) + life_s
    payload = json.dumps({"sub": subject, "name": name, "exp": exp}).encode()
    body = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    return f"v1.{body}.{session.mac(secret, f'v1.{body}')}"


class Web(World):
    """The API world with the site's signing secret set, and helpers that act as one Google
    account signed in on the site."""

    def __init__(self, tmp_path: Path, cfg, models: FakeChatModels) -> None:  # noqa: F811
        super().__init__(tmp_path, cfg, models)
        data = tmp_path / "data"
        self.client.app.dependency_overrides[settings] = lambda: Settings(  # type: ignore[attr-defined]
            data, None, None, None, SECRET, web_secret=WEB_SECRET
        )

    def call(self, subject: str, method: str, path: str, body: dict | None = None):
        headers = {"Authorization": f"Bearer {token(subject)}"}
        return self.client.request(method, path, json=body, headers=headers)

    def weblink(self, chat_id: int | None = None) -> str:
        """The code the bot sends for /weblink, from the user's own chat."""
        if chat_id is None:
            self.a.say("/weblink")
        else:
            handle_update(text_update("/weblink", chat_id), self.store, self.a.bot, NOW,
                          self.services)  # fmt: skip
        match = CODE.search(self.a.bot.last)
        assert match, f"a code in {self.a.bot.last!r}"
        # The test bot's clock is a fixed morning, while the API redeems against the real clock,
        # so the code gets its ten minutes from now.
        expires = (dt.datetime.now(dt.UTC) + dt.timedelta(minutes=10)).isoformat()
        with self.store._connect() as conn:  # noqa: SLF001
            conn.execute("UPDATE link_codes SET expires_at = ? WHERE code = ?",
                         (expires, match.group(1)))  # fmt: skip
        return match.group(1)

    def link(self, subject: str, code: str):
        return self.call(subject, "post", "/api/web/link", {"code": code})


@pytest.fixture
def web(tmp_path: Path, cfg) -> Web:  # noqa: F811
    return Web(tmp_path, cfg, FakeChatModels(Intent.OTHER.value))


# A forged or missing session ----------------------------------------------------------------


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
def test_every_web_route_refuses_a_missing_session(web: Web, method, path, body) -> None:
    response = web.client.request(method, path, json=body)
    assert response.status_code == 401
    assert response.json()["error"] == "signed_out"


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
@pytest.mark.parametrize("forged", [
    token(ANA, secret="not-the-site's-secret"),
    token(ANA, life_s=-5),
    token(ANA, life_s=3600),
    "v1.e30.AAAA",
    "Bearer-less nonsense",
])  # fmt: skip
def test_every_web_route_refuses_a_forged_session(web: Web, method, path, body, forged) -> None:
    headers = {"Authorization": f"Bearer {forged}"}
    response = web.client.request(method, path, json=body, headers=headers)
    assert response.status_code == 401


def test_a_server_without_the_secret_refuses_everyone(web: Web, tmp_path: Path) -> None:
    web.client.app.dependency_overrides[settings] = lambda: Settings(  # type: ignore[attr-defined]
        tmp_path / "data", None, None, None, SECRET
    )
    assert web.call(ANA, "get", "/api/web/me").status_code == 401


def test_the_token_names_the_user_never_the_body(web: Web) -> None:
    web.link(ANA, web.weblink())
    response = web.call(BEN, "post", "/api/web/chat", {"text": "hi", "user_id": USER})
    assert response.status_code == 403
    assert response.json()["error"] == "not_linked"


# Linking ------------------------------------------------------------------------------------


def test_signed_in_and_unlinked_is_told_how_to_link(web: Web) -> None:
    assert web.call(ANA, "get", "/api/web/me").json() == {"linked": False, "name": "Ana"}
    dashboard = web.call(ANA, "get", "/api/web/dashboard")
    assert dashboard.status_code == 403
    assert "Send /weblink to @networth_professor_bot" in json.dumps(dashboard.json())


def test_a_weblink_code_shows_the_linked_user_their_own_plan(web: Web) -> None:
    code = web.weblink()
    assert "within 10 minutes" in web.a.bot.last
    assert web.link(ANA, code).json() == {"linked": True, "name": "Ana"}
    assert web.call(ANA, "get", "/api/web/me").json()["linked"] is True
    board = web.call(ANA, "get", "/api/web/dashboard").json()
    assert (
        board["profile"]["plan"]
        == "Balanced. 20% safe money (liquid, gilt, FD), 70% broad index funds, "
        "10% single shares or themes"
    )
    assert board["sample"] is False


def test_the_link_is_keyed_by_the_google_subject(web: Web) -> None:
    web.link(ANA, web.weblink())
    with web.store._connect() as conn:  # noqa: SLF001
        rows = conn.execute("SELECT subject, user_id, name FROM web_logins").fetchall()
    assert [tuple(r) for r in rows] == [(ANA, USER, "Ana")]


def test_a_used_code_is_refused_in_plain_words(web: Web) -> None:
    code = web.weblink()
    assert web.link(ANA, code).status_code == 200
    again = web.link(BEN, code)
    assert again.status_code == 400
    assert again.json()["error"] == "bad_code"
    assert "works once" in json.dumps(again.json())
    assert web.call(BEN, "get", "/api/web/me").json()["linked"] is False


def test_an_expired_code_is_refused_in_plain_words(web: Web) -> None:
    eleven_ago = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=11)
    code = web.store.new_link_code(USER, eleven_ago, dt.timedelta(minutes=10))
    response = web.link(ANA, code)
    assert response.status_code == 400
    assert "only for 10 minutes" in json.dumps(response.json())


@pytest.mark.parametrize("wrong", ["not-a-code", "12345", "1234567"])
def test_a_wrong_code_is_refused_in_plain_words(web: Web, wrong: str) -> None:
    web.weblink()
    response = web.link(ANA, wrong)
    assert response.status_code == 400
    assert "Send /weblink to the bot for a new one." in json.dumps(response.json())


def test_a_wrong_six_digit_code_is_refused_and_counted(web: Web) -> None:
    code = web.weblink()
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    assert web.link(ANA, wrong).status_code == 400
    with web.store._connect() as conn:  # noqa: SLF001
        misses = conn.execute("SELECT COUNT(*) FROM link_misses WHERE address = ?",
                              (api.WEB_CONTACT_PREFIX + ANA,)).fetchone()[0]  # fmt: skip
    assert misses == 1


def test_five_wrong_codes_stop_that_google_account_guessing(web: Web) -> None:
    code = web.weblink()
    for n in range(1, 6):
        web.link(ANA, f"{(int(code) + n) % 1_000_000:06d}")
    assert web.link(ANA, code).status_code == 400
    assert web.link(BEN, code).status_code == 200


# Per-user chat ------------------------------------------------------------------------------


def test_a_linked_users_web_chat_remembers_the_turn_before(tmp_path: Path, cfg) -> None:  # noqa: F811
    web = Web(tmp_path, cfg, FakeChatModels(Intent.OTHER.value))
    web.link(ANA, web.weblink())
    assert web.call(ANA, "post", "/api/web/chat", {"text": "What is an IPO?"}).status_code == 200
    since = (dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)).isoformat()
    remembered = [t.text for t in web.store.recent_turns(USER, since, 10)]
    assert "What is an IPO?" in remembered


def test_a_second_google_account_cannot_see_the_first_users_chat_or_dashboard(web: Web) -> None:
    web.link(ANA, web.weblink())
    web.call(ANA, "post", "/api/web/chat", {"text": "What is an IPO?"})
    assert web.call(BEN, "get", "/api/web/dashboard").status_code == 403
    assert web.call(BEN, "post", "/api/web/chat", {"text": "what about it?"}).status_code == 403
    web.link(BEN, web.weblink(OTHER_CHAT))
    board = web.call(BEN, "get", "/api/web/dashboard").json()
    assert board["profile"]["plan"].startswith("Steady.")
    assert "Balanced" not in json.dumps(board)
    since = (dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)).isoformat()
    assert "What is an IPO?" not in [t.text for t in web.store.recent_turns(OTHER_USER, since, 10)]


def test_the_shared_demo_user_can_never_be_linked(web: Web) -> None:
    api.demo_user(Settings(web.services.data_dir, None, None, None, SECRET))
    code = web.store.new_link_code(api.DEMO_USER, dt.datetime.now(dt.UTC), dt.timedelta(minutes=10))
    assert web.link(ANA, code).status_code == 400


# The link goes ------------------------------------------------------------------------------


def test_forget_me_removes_the_link_and_keeps_the_bot_user(web: Web) -> None:
    web.link(ANA, web.weblink())
    assert web.call(ANA, "post", "/api/web/forget").json() == {"linked": False}
    assert web.call(ANA, "get", "/api/web/me").json()["linked"] is False
    assert web.call(ANA, "get", "/api/web/dashboard").status_code == 403
    assert web.store.get_profile(USER) is not None


def test_erase_on_telegram_removes_the_google_link(web: Web) -> None:
    web.link(ANA, web.weblink())
    web.a.say("/erase yes")
    assert web.store.user_for_web_login(ANA) is None
    assert web.call(ANA, "get", "/api/web/me").json()["linked"] is False


def test_a_stopped_user_is_no_longer_reachable_from_the_web(web: Web) -> None:
    web.link(ANA, web.weblink())
    profile = web.store.get_profile(USER)
    assert profile is not None
    web.store.save_profile(replace(profile, status=api.Status.STOPPED))
    assert web.call(ANA, "get", "/api/web/dashboard").status_code == 403
