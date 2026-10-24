"""The bot's IO shell: a raw Telegram update in, stored state and sent messages out.

    handle_update(update, store, bot)

The update is parsed here, at the boundary, into Text, Tap or Media. Onboarding answers go to
the pure onboarding.advance; commands are one COMMANDS entry each. Every outgoing message goes
through send(), the one gate that keeps a stopped user silent and a paused user free of
proactive messages. State is saved before anything is sent, so a failed send never loses an
answer.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Final

from networth.app.store import Plan, Profile, Status, Step, Store, new_profile, now_iso, user_id_for
from networth.bot.onboarding import CALLBACK_PREFIX, Outcome, Reply, advance, ordinal, plan_line
from networth.bot.onboarding import prompt as ask_for
from networth.bot.telegram import Bot

STALE_TAP: Final = "That question has moved on."
COMING_SOON: Final = (
    "Good question. Daily answers and tip checks are coming soon. "
    "I'll let you know when they're ready."
)
NO_FREE_CHAT: Final = (
    "I can't chat freely yet. That's coming soon. Type /help to see what I can do."
)
TODAY_PHRASES: Final = ("what happened today", "aaj market")
HELP: Final = (
    "Here's what I can do.\n\n"
    "/plan see or change your plan\n"
    "/pause pause briefs and alerts\n"
    "/resume turn them back on\n"
    "/stop stop all messages\n"
    "/start set up again or see your answers\n\n"
    'Soon you\'ll be able to ask "What happened today?" or forward me a tip to check.\n\n'
    "Research, not advice."
)
UNKNOWN_COMMAND: Final = "I don't know that one yet. Type /help to see what I can do."
FINISH_FIRST: Final = "Let's finish setting up first."
PAUSED: Final = (
    "Paused. I won't send briefs or alerts until you type /resume. You can still ask me things."
)
STOPPED: Final = "Stopped. I won't message you again. Type /start any time to come back."
WELCOME_BACK: Final = "Welcome back."


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
    return Media(chat_id)


def send(
    store: Store, bot: Bot, profile: Profile, reply: Reply, *, proactive: bool = False
) -> bool:
    """The only way a message leaves the bot. False, and nothing sent, when the user said no."""
    if profile.status is Status.STOPPED or (proactive and profile.status is Status.PAUSED):
        return False
    bot.send_message(profile.chat_id, reply.text, reply.buttons)
    store.log_message(profile.user_id, "out", reply.text)
    return True


@dataclass(frozen=True)
class Turn:
    """One update's worth of IO: where to save, where to send, and the time it arrived."""

    store: Store
    bot: Bot
    now: str

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


def handle_update(update: dict, store: Store, bot: Bot, now: str | None = None) -> None:
    incoming = parse_update(update)
    if incoming is None:
        return
    turn = Turn(store, bot, now or now_iso())
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
    text = msg.text.strip()
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
    elif msg.is_forward or any(p in text.lower() for p in TODAY_PHRASES):
        turn.send(profile, Reply(COMING_SOON))
    else:
        turn.send(profile, Reply(NO_FREE_CHAT))


def parse_callback(data: str) -> tuple[str, str] | None:
    parts = data.split(":", 2)
    if len(parts) != 3 or parts[0] != CALLBACK_PREFIX:
        return None
    return parts[1], parts[2]


def on_tap(turn: Turn, tap: Tap) -> None:
    profile = profile_for(turn, tap.chat_id)
    turn.store.log_message(profile.user_id, "in", tap.data)
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
    if profile is not None and profile.step is Step.DONE:
        turn.send(profile, Reply(COMING_SOON))


# --- commands ------------------------------------------------------------------------------


def cmd_start(turn: Turn, profile: Profile) -> None:
    returning = profile.status is Status.STOPPED
    was_done = profile.step is Step.DONE
    profile = replace(profile, status=Status.ACTIVE) if returning else profile
    if was_done:
        profile = replace(profile, step=Step.CONFIRM)
    profile = turn.save(profile)
    ask = ask_for(profile, turn.plan(profile))
    text = f"{WELCOME_BACK}\n\n{ask.text}" if returning and was_done else ask.text
    turn.send(profile, Reply(text, ask.buttons))


def cmd_plan(turn: Turn, profile: Profile) -> None:
    plan = turn.plan(profile)
    if profile.step is not Step.DONE or plan is None:
        ask = ask_for(profile, plan)
        turn.send(profile, Reply(f"{FINISH_FIRST}\n\n{ask.text}", ask.buttons))
        return
    profile = turn.save(replace(profile, step=Step.PLAN))
    turn.send(profile, Reply(f"Your plan: {plan_line(plan)}."))
    turn.send(profile, ask_for(profile, plan))


def cmd_pause(turn: Turn, profile: Profile) -> None:
    profile = turn.save(replace(profile, status=Status.PAUSED))
    turn.send(profile, Reply(PAUSED))


def cmd_resume(turn: Turn, profile: Profile) -> None:
    profile = turn.save(replace(profile, status=Status.ACTIVE))
    day = f" I'll check in on the {ordinal(profile.invest_day)}." if profile.invest_day else ""
    turn.send(profile, Reply(f"Back on.{day}"))


def cmd_stop(turn: Turn, profile: Profile) -> None:
    turn.send(profile, Reply(STOPPED))
    turn.save(replace(profile, status=Status.STOPPED))


def cmd_help(turn: Turn, profile: Profile) -> None:
    turn.send(profile, Reply(HELP))


def cmd_unknown(turn: Turn, profile: Profile) -> None:
    turn.send(profile, Reply(UNKNOWN_COMMAND))


COMMANDS: Final[dict[str, Callable[[Turn, Profile], None]]] = {
    "/start": cmd_start,
    "/plan": cmd_plan,
    "/pause": cmd_pause,
    "/resume": cmd_resume,
    "/stop": cmd_stop,
    "/help": cmd_help,
}


def command_name(text: str) -> str:
    """'/start@networth_professor_bot payload' -> '/start'."""
    return text.split(maxsplit=1)[0].split("@", 1)[0].lower()


def run_command(turn: Turn, profile: Profile, text: str) -> None:
    name = command_name(text)
    if profile.status is Status.STOPPED and name != "/start":
        return
    COMMANDS.get(name, cmd_unknown)(turn, profile)
