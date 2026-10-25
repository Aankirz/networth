"""One tap to the dashboard: /dashboard and its chat phrases, the site setting, the chat menu
button and the command list. Fake Telegram; no network."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient

from networth.app import links
from networth.app.main import create_app
from networth.app.services import Services
from networth.app.settings import Settings
from networth.app.store import Store
from networth.bot.commands import COMMAND_LIST
from networth.bot.telegram import Button, TelegramClient, TelegramError
from tests.test_onboarding import CHAT, Chat, FakeBot, onboard

SECRET = "test-signing-secret-not-real"
SITE = "https://networth-eight-pied.vercel.app"
SERVER = "https://nw.example"
COMMAND_NAME = re.compile(r"^[a-z0-9_]{1,32}$")


def chat_on(tmp_path: Path, site: str | None = SITE, public: str = SERVER) -> Chat:
    services = Services(tmp_path / "data", public, link_secret=SECRET, site_url=site)
    chat = Chat(tmp_path, services)
    onboard(chat)
    return chat


def url_buttons(chat: Chat) -> list[Button]:
    return [b for _, _, kb in chat.bot.sent for row in kb for b in row if b.url]


def token_of(url: str, base: str) -> str | None:
    assert url.startswith(f"{base}/u/"), url
    return links.verify(url.removeprefix(f"{base}/u/"), SECRET, dt.datetime.now(dt.UTC))


# --- /dashboard and its phrases --------------------------------------------------------------


def test_dashboard_sends_one_button_to_the_stored_token(tmp_path: Path) -> None:
    chat = chat_on(tmp_path)
    chat.say("/dashboard")
    (button,) = chat.bot.sent[-1][2][0]
    assert button.label == "My page"
    assert token_of(button.url or "", SITE) == chat.profile.link_token
    chat.say("/plan")
    assert token_of(button.url or "", SITE) == chat.profile.link_token, "another /plan keeps it"


@pytest.mark.parametrize("phrase", ["my dashboard", "mera dashboard", "open my page",
                                    "मेरा डैशबोर्ड"])  # fmt: skip
def test_dashboard_phrases_in_chat_send_the_same_button(tmp_path: Path, phrase: str) -> None:
    chat = chat_on(tmp_path)
    chat.say(phrase)
    (button,) = chat.bot.sent[-1][2][0]
    assert token_of(button.url or "", SITE) == chat.profile.link_token


def test_dashboard_before_setup_asks_to_finish(tmp_path: Path) -> None:
    chat = Chat(tmp_path, Services(tmp_path / "data", SERVER, link_secret=SECRET))
    chat.say("/start")
    chat.say("/dashboard")
    assert chat.bot.last == "Let's finish setting up first."


def test_with_no_way_to_sign_a_link_dashboard_points_at_telegram(tmp_path: Path) -> None:
    chat = Chat(tmp_path, Services(tmp_path / "data", SERVER))
    onboard(chat)
    chat.say("mera dashboard")
    assert chat.bot.last.startswith("Your dashboard link comes from Telegram")
    assert not chat.bot.sent[-1][2]


# --- NETWORTH_SITE_URL -----------------------------------------------------------------------


def test_the_site_url_setting_is_read_and_trimmed(tmp_path: Path) -> None:
    env = {"NETWORTH_SITE_URL": f"{SITE}/"}
    assert Settings.from_env(env, tmp_path / ".env").site_url == SITE
    assert Settings.from_env({}, tmp_path / ".env").site_url is None
    assert Settings.from_env({"NETWORTH_SITE_URL": ""}, tmp_path / ".env").site_url is None


def test_page_links_use_the_site_when_set_and_the_server_when_not(tmp_path: Path) -> None:
    on_site = chat_on(tmp_path / "a")
    on_site.say("/plan")
    on_server = chat_on(tmp_path / "b", site=None)
    on_server.say("/plan")
    assert f"{SITE}/u/" in on_site.bot.texts[-2]
    assert f"{SERVER}/u/" in on_server.bot.texts[-2] and SITE not in on_server.bot.texts[-2]


def test_the_brief_page_button_follows_the_site_setting(tmp_path: Path) -> None:
    chat = chat_on(tmp_path)
    chat.say("/brief")
    mine = [b for b in url_buttons(chat) if b.label == "My page"]
    assert mine and token_of(mine[-1].url or "", SITE) == chat.profile.link_token


def test_settings_carry_the_site_into_services(tmp_path: Path) -> None:
    settings = Settings(tmp_path, None, None, SERVER, SECRET, site_url=SITE)
    services = Services.from_settings(settings)
    assert services.page_base == SITE
    assert Services(tmp_path, SERVER).page_base == SERVER


# --- the chat menu button --------------------------------------------------------------------


def test_finishing_setup_sets_the_menu_button_once(tmp_path: Path) -> None:
    chat = chat_on(tmp_path)
    assert len(chat.bot.menus) == 1
    chat_id, label, url = chat.bot.menus[0]
    assert (chat_id, label) == (CHAT, "My page")
    assert token_of(url or "", SITE) == chat.profile.link_token


def test_no_https_page_leaves_the_menu_alone(tmp_path: Path) -> None:
    chat = chat_on(tmp_path, site=None, public="http://localhost:8080")
    assert chat.bot.menus == []


def test_dashboard_sets_the_menu_again_and_stop_resets_it(tmp_path: Path) -> None:
    chat = chat_on(tmp_path)
    chat.say("/dashboard")
    assert len(chat.bot.menus) == 2
    chat.say("/stop")
    assert chat.bot.menus[-1] == (CHAT, "My page", None)


class FailingMenu(FakeBot):
    def set_chat_menu_button(self, chat_id: int, text: str, url: str | None) -> None:
        raise TelegramError("setChatMenuButton", "Bad Request: web app url invalid")


def test_a_failed_menu_call_never_blocks_the_reply(tmp_path: Path) -> None:
    chat = Chat(tmp_path, Services(tmp_path / "data", SERVER, link_secret=SECRET))
    chat.bot = FailingMenu()
    onboard(chat)
    chat.say("/dashboard")
    assert chat.bot.sent[-1][2][0][0].label == "My page"


def posting() -> tuple[TelegramClient, list[tuple[str, dict]]]:
    seen: list[tuple[str, dict]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append((request.url.path.rsplit("/", 1)[-1], json.loads(request.content)))
        return httpx2.Response(200, json={"ok": True, "result": True})

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    return TelegramClient("123:TEST", client=client), seen


def test_the_menu_button_posts_telegrams_exact_shape() -> None:
    bot, seen = posting()
    bot.set_chat_menu_button(7, "My page", f"{SITE}/u/t.1.s")
    bot.set_chat_menu_button(7, "My page", None)
    assert seen == [
        ("setChatMenuButton", {"chat_id": 7, "menu_button": {
            "type": "web_app", "text": "My page", "web_app": {"url": f"{SITE}/u/t.1.s"}}}),
        ("setChatMenuButton", {"chat_id": 7, "menu_button": {"type": "default"}}),
    ]  # fmt: skip


# --- the command list ------------------------------------------------------------------------


def test_the_command_list_is_valid_and_names_dashboard() -> None:
    bot, seen = posting()
    bot.set_my_commands(COMMAND_LIST)
    ((method, params),) = seen
    assert method == "setMyCommands"
    names = [c["command"] for c in params["commands"]]
    assert "dashboard" in names and len(names) == len(set(names))
    assert all(COMMAND_NAME.match(n) for n in names)
    assert all(1 <= len(c["description"]) <= 256 for c in params["commands"])


UNLISTED = {"/link_broker"}  # SnapTrade is dropped; a typed /link_broker still gets a kind line


def test_every_listed_command_is_one_the_bot_answers() -> None:
    from networth.bot.commands import COMMANDS

    assert {f"/{name}" for name, _ in COMMAND_LIST} == set(COMMANDS) - UNLISTED


@pytest.mark.parametrize("lang", ["en", "hi", "hinglish"])
def test_link_broker_is_neither_listed_nor_in_help(lang: str) -> None:
    from networth.bot.commands import COMMANDS, help_message
    from networth.bot.message import plain

    assert "link_broker" not in dict(COMMAND_LIST)
    assert "/link_broker" not in plain(help_message(lang))
    assert "/link_broker" in COMMANDS, "a typed /link_broker is still answered"


def test_the_server_sends_the_command_list_on_start(tmp_path: Path) -> None:
    bot = FakeBot()
    with TestClient(create_app(Store(tmp_path), bot, "s")):
        pass
    assert bot.commands == [COMMAND_LIST]


def test_help_names_dashboard_and_follow_ups(tmp_path: Path) -> None:
    chat = chat_on(tmp_path)
    chat.say("/help")
    assert "/dashboard" in chat.bot.last and "follow up" in chat.bot.last
