"""One Keiki turn, end to end: flush queued email, find who wrote, answer through the same
pipeline as Telegram, then complete the turn.

    harness.start(lambda: run_turn(turn, store, services, harness.client(url, token), now))

The reply goes through KeikiTurnBot, a Bot whose send_message posts our exact text to the
turn, so commands, onboarding and chat answers (intent, handler, guard) run unchanged. A
contact we have never seen gets an email-native profile and the short setup in onboard.py.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Final, Literal

from networth.app.services import Services
from networth.app.store import Channel, Profile, Status, Step, Store, new_email_profile
from networth.bot import commands
from networth.bot.onboarding import Outcome
from networth.bot.telegram import Keyboard
from networth.keiki import onboard
from networth.keiki.client import ClientFactory, TurnClient
from networth.keiki.mail import NOTICE
from networth.keiki.render import plain
from networth.keiki.verify import Keys
from networth.keiki.wire import KeikiTurn, strip_quoted

log = logging.getLogger("networth.keiki")

Kind = Literal["chat", "command", "onboarding", "link", "notice"]
# ponytail: one process-wide lock, so turns run one at a time. Per-turn cost attribution reads
# the call log by time window, and that is only exact while no other turn overlaps.
TURN_LOCK: Final = threading.Lock()


def spawn(work: Callable[[], None]) -> None:
    threading.Thread(target=work, name="keiki-turn", daemon=True).start()


@dataclass(frozen=True)
class Harness:
    """What /keiki/turn needs: whose turns to accept, how to check them, how to answer them."""

    agent_id: str
    keys: Keys
    hmac_secret: str | None = None
    client: ClientFactory = TurnClient
    start: Callable[[Callable[[], None]], None] = spawn


class KeikiTurnBot:
    """networth.bot.telegram.Bot inside one turn. chat_id is ignored: a turn has one contact."""

    def __init__(self, client: TurnClient, turn_id: str) -> None:
        self._client = client
        self._turn_id = turn_id
        self._sent = 0

    def send_message(self, chat_id: int, text: str, buttons: Keyboard = ()) -> dict:
        self._sent += 1
        self._client.send(plain(text, buttons), f"{self._turn_id}:{self._sent}")
        return {"message_id": self._sent}

    def answer_callback(self, callback_id: str, text: str | None = None) -> None:
        return None

    def edit_buttons(self, chat_id: int, message_id: int, buttons: Keyboard) -> None:
        return None

    def set_webhook(self, url: str, secret_token: str) -> None:
        raise NotImplementedError("not on a Keiki turn")

    def delete_webhook(self) -> None:
        raise NotImplementedError("not on a Keiki turn")

    def get_updates(self, offset: int | None, timeout_s: int) -> list[dict]:
        raise NotImplementedError("not on a Keiki turn")

    def download_file(self, file_id: str) -> bytes:
        raise NotImplementedError("not on a Keiki turn")


@dataclass(frozen=True)
class Handled:
    kind: Kind
    user_id: str | None = None


def inbound_text(turn: KeikiTurn) -> str:
    return "\n".join(strip_quoted(t) for t in turn.texts).strip()


def send_outcome(turn: commands.Turn, outcome: Outcome) -> Profile:
    profile = turn.save(outcome.profile)
    for reply in outcome.replies:
        turn.send(profile, reply)
    return profile


def welcome(turn: commands.Turn, address: str, text: str) -> Handled:
    profile = turn.save(new_email_profile(address, turn.now))
    turn.store.bind_contact(address, profile.user_id)
    turn.store.log_message(profile.user_id, "in", text)
    send_outcome(turn, onboard.start(profile))
    return Handled("onboarding", profile.user_id)


def email_setup(turn: commands.Turn, profile: Profile, text: str) -> bool:
    """The short setup for a profile that began by email: /start restarts it, and any other
    answer before it is done advances it. False when the message is not setup's to handle."""
    if profile.channel != Channel.EMAIL:
        return False
    if commands.command_name(text) == "/start":
        send_outcome(turn, onboard.start(replace(profile, status=Status.ACTIVE)))
        return True
    if profile.step is Step.DONE or text.startswith("/") or profile.status is Status.STOPPED:
        return False
    send_outcome(turn, onboard.advance_email(profile, text))
    return True


def route(turn: commands.Turn, address: str, text: str) -> Handled:
    user_id = turn.store.contact_user(address)
    profile = turn.store.get_profile(user_id) if user_id else None
    if profile is None:
        return welcome(turn, address, text)
    turn.store.log_message(profile.user_id, "in", text)
    if email_setup(turn, profile, text):
        return Handled("onboarding", profile.user_id)
    kind: Kind = ("command" if text.startswith("/")
                  else "chat" if profile.step is Step.DONE else "onboarding")  # fmt: skip
    commands.on_profile_text(turn, profile, text, False)
    return Handled(kind, profile.user_id)


def handle(turn: KeikiTurn, store: Store, services: Services, client: TurnClient,
           now: str) -> Handled:  # fmt: skip
    if services.mail is not None:
        services.mail.flush(turn.conversation_id, client)
    text = inbound_text(turn)
    if not text or text == NOTICE:
        return Handled("notice", store.contact_user(turn.conversation_id))
    io = commands.Turn(store, KeikiTurnBot(client, turn.turn_id), now, services)
    handled = route(io, turn.conversation_id, text)
    for job in io.later:
        job()
    return handled


def _fail(client: TurnClient, exc: Exception) -> None:
    try:
        client.complete("failed", error=type(exc).__name__)
    except Exception as again:  # noqa: BLE001 - Keiki times the turn out on its own
        log.warning("keiki complete failed: %s", type(again).__name__)


def run_turn(turn: KeikiTurn, store: Store, services: Services, client: TurnClient,
             now: str) -> str:  # fmt: skip
    """'completed' or 'failed'. A failure is logged and reported to Keiki, never raised."""
    with TURN_LOCK:
        try:
            handle(turn, store, services, client, now)
            client.complete("completed")
        except Exception as exc:  # noqa: BLE001 - a background turn has no caller to raise to
            log.exception("keiki turn %s failed", turn.turn_id)
            _fail(client, exc)
            return "failed"
        return "completed"
