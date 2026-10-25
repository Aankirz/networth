"""The bot's IO shell: a raw Telegram update in, stored state and sent messages out.

    handle_update(update, store, bot)

The update is parsed here, at the boundary, into Text, Tap or Media. Onboarding answers go to
the pure onboarding.advance; commands are one COMMANDS entry each. Every outgoing message goes
through outbox.send(), the one gate that keeps a stopped user silent and a paused user free
of proactive messages. State is saved before anything is sent, so a failed send never loses an
answer. Chat answers search and call models, so they run after the update lock is released and
one slow tip check never holds up another user's setup.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Final

from networth import brief, chat
from networth.app import links
from networth.app.services import Services
from networth.app.store import (
    Channel,
    Plan,
    Profile,
    Status,
    Step,
    Store,
    new_profile,
    now_iso,
    user_id_for,
)
from networth.bot import briefs, watches
from networth.bot.onboarding import CALLBACK_PREFIX, Outcome, Reply, advance, ordinal, plan_line
from networth.bot.onboarding import prompt as ask_for
from networth.bot.outbox import send
from networth.bot.telegram import Bot

log = logging.getLogger("networth.bot")

STALE_TAP: Final = "That question has moved on."
NOT_A_PHOTO: Final = "I can read photos and text. Send a screenshot, or paste the text."
TRY_AGAIN: Final = "Something went wrong on my side. Please try again in a minute."
TOO_MANY: Final = (
    "That is a lot of questions in one hour, so I am taking a short break. Ask me again in a "
    "little while and I will answer."
)
PLAN_KEPT: Final = "Noted. Your plan stays as it is."
HELP: Final = (
    "Here's what I can do.\n\n"
    'Ask "What happened today?" or "Why?"\n'
    "Forward me a tip and I'll check who reported it\n"
    "Send an IPO page, a link or a screenshot and I'll explain it\n\n"
    "/brief this month's brief\n"
    "/plan see or change your plan\n"
    "/range what your plan could become, replayed over past months\n"
    "/pause pause briefs and alerts\n"
    "/resume turn them back on\n"
    "/stop stop all messages\n"
    "/start set up again or see your answers\n"
    "/link get a code to use me by email too\n"
    "/sendto email or /sendto telegram, where briefs and alerts go\n"
    "/watch something to hear once when a confirmed story about it appears\n"
    "/watches see or stop your watches\n"
    "/unwatch 1 stop a watch by its number\n\n"
    "Research, not advice."
)
UNKNOWN_COMMAND: Final = "I don't know that one yet. Type /help to see what I can do."
FINISH_FIRST: Final = "Let's finish setting up first."
PAUSED: Final = (
    "Paused. I won't send briefs or alerts until you type /resume. You can still ask me things."
)
STOPPED: Final = "Stopped. I won't message you again. Type /start any time to come back."
WELCOME_BACK: Final = "Welcome back."
UNAVAILABLE: Final = "That isn't available right now. Please try again later."
LINK_ON_TELEGRAM: Final = "Linking starts on Telegram: type /link there, then email me the code."
LINK_CODE: Final = (
    "Your code is {code}. Email it to {where} within {minutes} minutes. It works once. After "
    "that, your plan, language and what you left out apply there too."
)
DESTINATIONS: Final = {"email": Channel.EMAIL, "telegram": Channel.TELEGRAM}
DESTINATION_NAMES: Final = {Channel.EMAIL: "your email", Channel.TELEGRAM: "Telegram"}
SENDTO_USAGE: Final = "Type /sendto email or /sendto telegram to choose where briefs and alerts go."
UNREACHABLE: Final = {
    Channel.EMAIL: "Link your email first: type /link on Telegram and email me the code.",
    Channel.TELEGRAM: "You haven't used Networth on Telegram yet, so briefs stay on email.",
}


@dataclass(frozen=True)
class Text:
    chat_id: int
    text: str
    is_forward: bool


@dataclass(frozen=True)
class Tap:
    chat_id: int
    callback_id: str
    data: str
    message_id: int | None


@dataclass(frozen=True)
class Media:
    chat_id: int
    file_id: str | None  # the largest size of a photo; None for stickers, voice and the rest


Incoming = Text | Tap | Media


def parse_update(update: dict) -> Incoming | None:
    """Only new messages and button taps matter; edits, joins and the rest are None."""
    if tap := update.get("callback_query"):
        message = tap.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        if chat_id is None:
            return None
        return Tap(int(chat_id), str(tap["id"]), str(tap.get("data") or ""),
                   message.get("message_id"))  # fmt: skip
    message = update.get("message")
    if not message or (message.get("chat") or {}).get("id") is None:
        return None
    chat_id = int(message["chat"]["id"])
    if isinstance(message.get("text"), str):
        is_forward = "forward_origin" in message or "forward_date" in message
        return Text(chat_id, message["text"], is_forward)
    photos = message.get("photo")
    largest = photos[-1] if isinstance(photos, list) and photos else {}
    file_id = largest.get("file_id") if isinstance(largest, dict) else None
    return Media(chat_id, file_id if isinstance(file_id, str) else None)


@dataclass(frozen=True)
class Turn:
    """One update's worth of IO: where to save, where to send, the time it arrived, the slow
    work to run once the update lock is released, and what the chat answer used (its intent
    and guard verdict), which a Keiki turn logs."""

    store: Store
    bot: Bot
    now: str
    services: Services
    later: list[Callable[[], None]] = field(default_factory=list)
    trace: dict[str, str] = field(default_factory=dict)

    @property
    def clock(self) -> dt.datetime:
        return dt.datetime.fromisoformat(self.now)

    def answer(self, profile: Profile, make: Callable[[], Reply]) -> None:
        """Queue a slow reply; a failure still tells the user something went wrong. Past the
        hourly cap the user gets a polite note and no paid call runs."""
        cfg = self.services.cfg
        if cfg is not None and not self.store.claim_answer(
            profile.user_id, self.clock, cfg.product.chat_max_per_hour
        ):
            self.send(profile, Reply(TOO_MANY))
            return

        def job() -> None:
            try:
                reply = make()
            except Exception:
                log.exception("chat answer for %s failed", profile.user_id)
                reply = Reply(TRY_AGAIN)
            self.send(profile, reply)

        self.later.append(job)

    def send(self, profile: Profile, reply: Reply) -> bool:
        return send(self.store, self.bot, profile, reply)

    def save(self, profile: Profile) -> Profile:
        profile = replace(profile, updated_at=self.now)
        self.store.save_profile(profile)
        return profile

    def plan(self, profile: Profile) -> Plan | None:
        return self.store.get_plan(profile.user_id)

    def commit(self, before: Plan | None, outcome: Outcome) -> Profile:
        if outcome.plan is not None and outcome.plan != before:
            self.store.save_plan(outcome.plan)
        return self.save(outcome.profile)


def profile_for(turn: Turn, chat_id: int) -> Profile:
    existing = turn.store.get_profile(user_id_for(chat_id))
    return existing or turn.save(new_profile(chat_id, turn.now))


# ponytail: one process-wide lock, so two taps never read the same step at once. One container
# serves every user; per-chat locks are the upgrade if throughput ever matters.
HANDLE_LOCK: Final = threading.Lock()


def handle_update(
    update: dict, store: Store, bot: Bot, now: str | None = None,
    services: Services | None = None,
) -> None:  # fmt: skip
    turn = Turn(store, bot, now or now_iso(), services or Services(store.path.parent))
    with HANDLE_LOCK:
        update_id = update.get("update_id")
        if isinstance(update_id, int) and not store.claim_update(update_id):
            return
        dispatch(update, turn)
    for job in turn.later:
        job()


def dispatch(update: dict, turn: Turn) -> None:
    incoming = parse_update(update)
    if incoming is None:
        return
    match incoming:
        case Tap():
            on_tap(turn, incoming)
        case Text():
            on_text(turn, incoming)
        case Media():
            on_media(turn, incoming)


def on_text(turn: Turn, msg: Text) -> None:
    profile = profile_for(turn, msg.chat_id)
    turn.store.log_message(profile.user_id, "in", msg.text)
    on_profile_text(turn, profile, msg.text.strip(), msg.is_forward)


def on_profile_text(turn: Turn, profile: Profile, text: str, is_forward: bool) -> None:
    """One typed message from a known profile, on Telegram or inside a Keiki turn."""
    if text.startswith("/"):
        run_command(turn, profile, text)
    elif profile.status is Status.STOPPED:
        return
    elif profile.step is not Step.DONE:
        plan = turn.plan(profile)
        outcome = advance(profile, plan, text, turn.now)
        profile = turn.commit(plan, outcome)
        if outcome.toast and not outcome.replies:
            ask = ask_for(profile, outcome.plan)
            turn.send(profile, Reply(f"{outcome.toast}.\n\n{ask.text}", ask.buttons))
        for reply in outcome.replies:
            turn.send(profile, reply)
    else:
        turn.answer(profile, lambda: chat_reply(turn, profile, text, is_forward))


def chat_reply(turn: Turn, profile: Profile, text: str, is_forward: bool) -> Reply:
    reply, intent, used = chat.respond_traced(turn.store, profile, text, is_forward,
                                              turn.services, turn.clock)  # fmt: skip
    turn.trace.update(intent=intent.value, guard=used)
    return reply


def parse_callback(data: str) -> tuple[str, str] | None:
    parts = data.split(":", 2)
    if len(parts) != 3 or parts[0] != CALLBACK_PREFIX:
        return None
    return parts[1], parts[2]


def on_brief_tap(turn: Turn, profile: Profile, tap: Tap) -> None:
    """Invest as planned only acknowledges: the user invests in their own app."""
    turn.bot.answer_callback(tap.callback_id)
    if tap.data == f"{brief.CALLBACK_PREFIX}:plan":
        cmd_plan(turn, profile, "")
    elif tap.data == f"{brief.CALLBACK_PREFIX}:range":
        cmd_range(turn, profile, "")
    elif tap.data == f"{brief.CALLBACK_PREFIX}:ok":
        turn.send(profile, Reply(PLAN_KEPT))


def on_tap(turn: Turn, tap: Tap) -> None:
    profile = profile_for(turn, tap.chat_id)
    turn.store.log_message(profile.user_id, "in", tap.data)
    if profile.status is not Status.STOPPED and tap.data.startswith(watches.STOP_PREFIX):
        turn.bot.answer_callback(tap.callback_id)
        turn.send(profile, Reply(watches.stop_tapped(turn.store, profile, tap.data)))
        return
    if profile.status is not Status.STOPPED and tap.data.startswith(f"{brief.CALLBACK_PREFIX}:"):
        on_brief_tap(turn, profile, tap)
        return
    parsed = parse_callback(tap.data)
    if profile.status is Status.STOPPED or parsed is None:
        turn.bot.answer_callback(tap.callback_id)
        return
    step, value = parsed
    plan = turn.plan(profile)
    if step != profile.step:
        turn.bot.answer_callback(tap.callback_id, STALE_TAP)
        if profile.step is not Step.DONE:
            turn.send(profile, ask_for(profile, plan))
        return
    outcome = advance(profile, plan, value, turn.now)
    profile = turn.commit(plan, outcome)
    turn.bot.answer_callback(tap.callback_id, outcome.toast)
    if outcome.edit_buttons is not None and tap.message_id is not None:
        turn.bot.edit_buttons(tap.chat_id, tap.message_id, outcome.edit_buttons)
    for reply in outcome.replies:
        turn.send(profile, reply)


def on_media(turn: Turn, media: Media) -> None:
    profile = turn.store.get_profile(user_id_for(media.chat_id))
    if profile is None or profile.step is not Step.DONE or profile.status is Status.STOPPED:
        return
    if media.file_id is None:
        turn.send(profile, Reply(NOT_A_PHOTO))
        return
    file_id = media.file_id
    turn.answer(profile, lambda: chat.respond_image(profile, turn.bot.download_file(file_id),
                                                    turn.services))  # fmt: skip


# --- commands ------------------------------------------------------------------------------


def cmd_start(turn: Turn, profile: Profile, args: str) -> None:
    returning = profile.status is Status.STOPPED
    was_done = profile.step is Step.DONE
    profile = replace(profile, status=Status.ACTIVE) if returning else profile
    if was_done:
        profile = replace(profile, step=Step.CONFIRM)
    profile = turn.save(profile)
    ask = ask_for(profile, turn.plan(profile))
    text = f"{WELCOME_BACK}\n\n{ask.text}" if returning and was_done else ask.text
    turn.send(profile, Reply(text, ask.buttons))


def cmd_plan(turn: Turn, profile: Profile, args: str) -> None:
    plan = turn.plan(profile)
    if profile.step is not Step.DONE or plan is None:
        ask = ask_for(profile, plan)
        turn.send(profile, Reply(f"{FINISH_FIRST}\n\n{ask.text}", ask.buttons))
        return
    profile = turn.save(replace(profile, step=Step.PLAN))
    page = None
    if turn.services.public_url and turn.services.link_secret:
        profile = replace(profile, link_token=turn.store.new_link_token(profile.user_id))
        page = links.page_url(turn.services.public_url, profile.link_token,
                              turn.services.link_secret, turn.clock)  # fmt: skip
    mine = f"\n\nYour page, with your plan and latest brief: {page}" if page else ""
    turn.send(profile, Reply(f"Your plan: {plan_line(plan)}.{mine}"))
    turn.send(profile, ask_for(profile, plan))


def cmd_pause(turn: Turn, profile: Profile, args: str) -> None:
    profile = turn.save(replace(profile, status=Status.PAUSED))
    turn.send(profile, Reply(PAUSED))


def cmd_resume(turn: Turn, profile: Profile, args: str) -> None:
    profile = turn.save(replace(profile, status=Status.ACTIVE))
    day = f" I'll check in on the {ordinal(profile.invest_day)}." if profile.invest_day else ""
    turn.send(profile, Reply(f"Back on.{day}"))


def cmd_stop(turn: Turn, profile: Profile, args: str) -> None:
    turn.send(profile, Reply(STOPPED))
    turn.save(replace(profile, status=Status.STOPPED))


def cmd_brief(turn: Turn, profile: Profile, args: str) -> None:
    local = briefs.local_now(profile, turn.clock)

    def job() -> None:
        try:
            briefs.send_brief(turn.store, turn.bot, profile, turn.services, local)
        except Exception:
            log.exception("brief for %s failed", profile.user_id)
            turn.send(profile, Reply(TRY_AGAIN))

    turn.later.append(job)


def cmd_range(turn: Turn, profile: Profile, args: str) -> None:
    """Fixed sentences, so no model and no hourly claim; the replay runs after the lock."""
    if profile.step is not Step.DONE:
        turn.send(profile, Reply(FINISH_FIRST))
        return

    def job() -> None:
        try:
            reply = chat.today.plan_range(turn.store, profile, profile.lang or "en").template
        except Exception:
            log.exception("range for %s failed", profile.user_id)
            reply = TRY_AGAIN
        turn.send(profile, Reply(reply))

    turn.later.append(job)


def cmd_help(turn: Turn, profile: Profile, args: str) -> None:
    turn.send(profile, Reply(HELP))


def cmd_unknown(turn: Turn, profile: Profile, args: str) -> None:
    turn.send(profile, Reply(UNKNOWN_COMMAND))


def cmd_link(turn: Turn, profile: Profile, args: str) -> None:
    """A single-use code that ties the user's email to this Telegram profile."""
    cfg = turn.services.cfg
    if profile.step is not Step.DONE:
        turn.send(profile, Reply(FINISH_FIRST))
    elif profile.channel == Channel.EMAIL:
        turn.send(profile, Reply(LINK_ON_TELEGRAM))
    elif cfg is None:
        turn.send(profile, Reply(UNAVAILABLE))
    else:
        minutes = cfg.product.link_code_minutes
        code = turn.store.new_link_code(profile.user_id, turn.clock, dt.timedelta(minutes=minutes))
        where = turn.services.keiki_email or "Networth's email"
        turn.send(profile, Reply(LINK_CODE.format(code=code, where=where, minutes=minutes)))


def reachable(turn: Turn, profile: Profile, channel: Channel) -> bool:
    if channel is Channel.EMAIL:
        return turn.store.contact_for(profile.user_id) is not None
    return profile.chat_id != 0


def cmd_sendto(turn: Turn, profile: Profile, args: str) -> None:
    channel = DESTINATIONS.get(args.strip().lower())
    if channel is None:
        turn.send(profile, Reply(SENDTO_USAGE))
    elif not reachable(turn, profile, channel):
        turn.send(profile, Reply(UNREACHABLE[channel]))
    else:
        profile = turn.save(replace(profile, deliver_to=channel))
        turn.send(
            profile, Reply(f"Done. Briefs and alerts now go to {DESTINATION_NAMES[channel]}.")
        )


def cmd_watch(turn: Turn, profile: Profile, args: str) -> None:
    if profile.step is not Step.DONE:
        turn.send(profile, Reply(FINISH_FIRST))
        return
    rules = turn.services.cfg.product if turn.services.cfg else None
    turn.send(profile, Reply(watches.set_watch(turn.store, profile, args, turn.now, rules)))


def cmd_watches(turn: Turn, profile: Profile, args: str) -> None:
    turn.send(profile, watches.list_reply(turn.store, profile))


def cmd_unwatch(turn: Turn, profile: Profile, args: str) -> None:
    turn.send(profile, Reply(watches.stop_nth(turn.store, profile, args)))


COMMANDS: Final[dict[str, Callable[[Turn, Profile, str], None]]] = {
    "/start": cmd_start,
    "/brief": cmd_brief,
    "/plan": cmd_plan,
    "/range": cmd_range,
    "/pause": cmd_pause,
    "/resume": cmd_resume,
    "/stop": cmd_stop,
    "/help": cmd_help,
    "/link": cmd_link,
    "/sendto": cmd_sendto,
    "/watch": cmd_watch,
    "/watches": cmd_watches,
    "/unwatch": cmd_unwatch,
}


def command_name(text: str) -> str:
    """'/start@networth_professor_bot payload' -> '/start'."""
    return text.split(maxsplit=1)[0].split("@", 1)[0].lower()


def run_command(turn: Turn, profile: Profile, text: str) -> None:
    name = command_name(text)
    if profile.status is Status.STOPPED and name != "/start":
        return
    parts = text.split(maxsplit=1)
    COMMANDS.get(name, cmd_unknown)(turn, profile, parts[1] if len(parts) > 1 else "")
