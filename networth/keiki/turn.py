"""One Keiki turn, end to end: flush queued email, find who wrote, answer through the same
pipeline as Telegram, then complete the turn. Email and Slack arrive the same way and get the
same plain text.

    harness.start(lambda: run_turn(turn, store, services, harness.client(url, token), now))

The reply goes through KeikiTurnBot, a Bot whose send_message posts the plain render of our
message to the turn, so commands, onboarding and chat answers (intent, handler, guard) run
unchanged. A contact we have never seen gets an email-native profile and the short setup in
onboard.py. A /link code from Telegram, sent by email, points the contact at that Telegram
user instead, even when the contact already had an email-native profile. After five wrong codes
in an hour, the contact's codes are not tried and the message is answered as any other.

Every turn appends one line to data/keiki_turns.jsonl: the turn and trace ids, the hashed user
id, the channel type, which kind of turn, the chat intent and guard verdict, the model cost,
and the outcome. Never the text, the address or a token. Cost is the sum of llm_calls.jsonl
records written during the turn.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, Literal

from networth import chat
from networth.app.services import Services
from networth.app.store import Channel, Profile, Status, Step, Store, new_email_profile
from networth.bot import commands
from networth.bot.message import Message, say
from networth.bot.message import plain as plain_text
from networth.bot.onboarding import Outcome, Reply
from networth.bot.telegram import Keyboard
from networth.keiki import onboard
from networth.keiki.client import ClientFactory, TurnClient
from networth.keiki.mail import NOTICE
from networth.keiki.render import plain
from networth.keiki.verify import Keys
from networth.keiki.wire import KeikiTurn, strip_quoted
from networth.net import read_records

log = logging.getLogger("networth.keiki")

# welcome: a first message from a new contact, answered when it asks something, then the
# short setup starts. onboarding: an answer to a setup question.
Kind = Literal["chat", "command", "welcome", "onboarding", "link", "notice"]
# ponytail: one process-wide lock, so turns run one at a time. Per-turn cost attribution reads
# the call log by time window, and that is only exact while no other turn overlaps.
TURN_LOCK: Final = threading.Lock()
LINK_CODE: Final = re.compile(r"(?<!\d)\d{6}(?!\d)")
# A /link code is read only from a short line near the top, so a number inside a question never
# redeems one and a footer the mail client added never hides one.
LINK_MESSAGE_MAX: Final = 40
LINK_LINES: Final = 3
LINKED: Final = {
    "en": "Linked. Your plan, language and what you left out now carry over here too. Briefs and "
    "alerts stay on Telegram until you reply /sendto email.",
    "hi": "लिंक हो गया। आपका प्लान, भाषा और जो आपने बाहर रखा, वह अब यहाँ भी लागू है। ब्रीफ़ और "
    "अलर्ट तब तक Telegram पर आएँगे, जब तक आप /sendto email नहीं भेजते।",
    "hinglish": "Link ho gaya. Aapka plan, language aur jo aapne bahar rakha, woh ab yahan bhi "
    "lagu hai. Briefs aur alerts tab tak Telegram par aayenge, jab tak aap /sendto email nahin "
    "bhejte.",
}


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

    def send_message(self, chat_id: int, message: Message, buttons: Keyboard = ()) -> dict:
        self._sent += 1
        self._client.send(plain(plain_text(message), buttons), f"{self._turn_id}:{self._sent}")
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
    intent: str | None = None  # set when a chat answer ran
    guard: str | None = None  # which words went out: model, rewrite, template or fixed


def inbound_text(turn: KeikiTurn) -> str:
    return "\n".join(strip_quoted(t) for t in turn.texts).strip()


def send_outcome(turn: commands.Turn, outcome: Outcome) -> Profile:
    profile = turn.save(outcome.profile)
    for reply in outcome.replies:
        turn.send(profile, reply)
    return profile


def welcome(turn: commands.Turn, address: str, text: str) -> Handled:
    """A first email: answer it when it asks something (a greeting or a command gets no
    answer), then start the short setup, so "What happened today?" from a stranger is answered,
    not deferred."""
    profile = turn.save(new_email_profile(address, turn.now))
    turn.store.bind_contact(address, profile.user_id)
    turn.store.log_message(profile.user_id, "in", text)
    cfg = turn.services.cfg
    asks = not text.startswith("/")  # a command needs a finished setup, as on Telegram
    limit = cfg.product.chat_max_per_hour if cfg else None
    if asks and (limit is None or turn.store.claim_answer(profile.user_id, turn.clock, limit)):
        turn.later.append(lambda: first_answer(turn, profile, text))
    turn.later.append(lambda: send_outcome(turn, onboard.start(profile)))
    return Handled("welcome", profile.user_id)


def first_answer(turn: commands.Turn, profile: Profile, text: str) -> None:
    try:
        reply, intent, used = chat.respond_traced(turn.store, profile, text, False,
                                                  turn.services, turn.clock)  # fmt: skip
    except Exception:
        log.exception("first answer for %s failed", profile.user_id)
        return
    if intent is not chat.Intent.OTHER:
        turn.trace.update(intent=intent.value, guard=used)
        turn.send(profile, reply)


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


def link_code(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()][:LINK_LINES]
    found = (LINK_CODE.search(line) for line in lines if len(line) <= LINK_MESSAGE_MAX)
    return next((m.group() for m in found if m), None)


def link(turn: commands.Turn, address: str, text: str) -> Handled | None:
    """Bind the contact to the user whose /link code the text carries, if it carries one."""
    code = link_code(text)
    user_id = turn.store.redeem_link_code(code, turn.clock, address) if code else None
    profile = turn.store.get_profile(user_id) if user_id else None
    if profile is None:
        return None
    turn.store.bind_contact(address, profile.user_id)
    turn.store.log_message(profile.user_id, "in", text)
    turn.send(profile, Reply(say(LINKED, profile.lang)))
    return Handled("link", profile.user_id)


def route(turn: commands.Turn, address: str, text: str) -> Handled:
    if linked := link(turn, address, text):
        return linked
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
        services.mail.flush(turn.contact, client)
    text = inbound_text(turn)
    if not text or text == NOTICE:
        return Handled("notice", store.contact_user(turn.contact))
    io = commands.Turn(store, KeikiTurnBot(client, turn.turn_id), now, services)
    handled = route(io, turn.contact, text)
    for job in io.later:
        job()
    return replace(handled, intent=io.trace.get("intent"), guard=io.trace.get("guard"))


def _fail(client: TurnClient, exc: Exception) -> None:
    try:
        client.complete("failed", error=type(exc).__name__)
    except Exception as again:  # noqa: BLE001 - Keiki times the turn out on its own
        log.warning("keiki complete failed: %s", type(again).__name__)


def cost_between(call_log: Path, start: dt.datetime, end: dt.datetime) -> float:
    """The cost of every model and search call logged from start (to the second) to end."""
    since = start.replace(microsecond=0)
    total = sum(r.cost_usd for r in read_records(call_log)
                if since <= dt.datetime.fromisoformat(r.ts) <= end)  # fmt: skip
    return round(total, 6)


def record_turn(services: Services, turn: KeikiTurn, handled: Handled | None, outcome: str,
                start: dt.datetime, end: dt.datetime) -> None:  # fmt: skip
    row = {
        "ts": end.isoformat(timespec="seconds"), "turn_id": turn.turn_id,
        "trace_id": turn.trace_id, "user_id": handled.user_id if handled else None,
        "channel": turn.channel, "kind": handled.kind if handled else None,
        "intent": handled.intent if handled else None,
        "guard": handled.guard if handled else None,
        "cost_usd": cost_between(services.call_log, start, end), "held_back": turn.held_back,
        "outcome": outcome,
    }  # fmt: skip
    services.turn_log.parent.mkdir(parents=True, exist_ok=True)
    with services.turn_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def run_turn(turn: KeikiTurn, store: Store, services: Services, client: TurnClient,
             now: str) -> str:  # fmt: skip
    """'completed' or 'failed'. A failure is logged and reported to Keiki, never raised."""
    with TURN_LOCK:
        start, handled, outcome = dt.datetime.now(dt.UTC), None, "completed"
        try:
            handled = handle(turn, store, services, client, now)
            client.complete("completed")
        except Exception as exc:  # noqa: BLE001 - a background turn has no caller to raise to
            log.exception("keiki turn %s failed", turn.turn_id)
            _fail(client, exc)
            outcome = "failed"
        try:
            record_turn(services, turn, handled, outcome, start, dt.datetime.now(dt.UTC))
        except Exception:  # noqa: BLE001 - a lost log line never fails the turn
            log.exception("keiki turn %s not logged", turn.turn_id)
        return outcome
