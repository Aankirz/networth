"""The voice, checked everywhere: every fixed template in the message code, every web template,
and one sample of every message type in English, Hindi and Hinglish.

Templates: no "!", no hype words, no lean words or colour marks, the guard's word rules pass,
and "Research, not advice" only in FOOTER itself. Samples: the footer once, at the end, on the
messages that need it (the brief, alerts, watch hits, chat answers, /help, /plan, setup done)
and never on a question, a retry or an ack. The HTML render carries no number the plain one
lacks.
"""

from __future__ import annotations

import html as htmllib
import importlib
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest

from networth import config, guard
from networth.app.services import Services
from networth.app.store import Plan, Step, new_profile
from networth.bot import commands, onboarding
from networth.bot.alerts import alert_message
from networth.bot.message import FOOTER, LANGS, Message, plain
from networth.bot.telegram import html
from networth.chat import explain, tip, today
from networth.chat.answer import Answer, deliver
from networth.keiki import onboard as email_onboard
from tests.test_alerts import insight
from tests.test_brief import event_brief
from tests.test_onboarding import NOW, Chat, onboard
from tests.test_watch import story, watches
from tests.watcher_fakes import FAKE_ENV

REPO = Path(__file__).resolve().parents[1]
MODULES = (
    "networth.bot.alerts", "networth.bot.briefs", "networth.bot.commands",
    "networth.bot.onboarding", "networth.bot.watches", "networth.brief",
    "networth.brief.lines", "networth.chat", "networth.chat.answer", "networth.chat.explain",
    "networth.chat.tip", "networth.chat.today", "networth.keiki.onboard", "networth.keiki.turn",
    "networth.memory", "networth.sim", "networth.watch",
)  # fmt: skip
HYPE: Final = re.compile(
    r"\b(unlock\w*|boost\w*|smart move|don'?t miss|hurry|act now|exclusive|amazing|"
    r"skyrocket\w*)\b",
    re.IGNORECASE,
)
LEAN: Final = re.compile(r"\blean(s|ing)?\b|🟢|🔴|⚪", re.IGNORECASE)
FOOTERS: Final = tuple(FOOTER.values())
DEVANAGARI: Final = re.compile("[ऀ-ॿ]")
TAG: Final = re.compile(r"<[^>]+>")
SCRIPT: Final = re.compile(r"<script.*?</script>", re.DOTALL)
# Upper-case constants that are not words a user reads: a model's input frame, a character set.
NOT_WORDS: Final = {"STATE", "EDGES"}


def strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, tuple | list):
        for v in value:
            yield from strings(v)
    elif hasattr(value, "__dataclass_fields__") and not isinstance(value, type):
        for name in value.__dataclass_fields__:
            yield from strings(getattr(value, name))


def templates() -> Iterator[tuple[str, str, str]]:
    """(module, name, text) for every module-level upper-case table of words. Model tasks are
    instructions to a model, not words a user reads, so they are left out."""
    for module_name in MODULES:
        module = importlib.import_module(module_name)
        for name, value in vars(module).items():
            if (not name.isupper() or name.endswith("_TASK") or name in NOT_WORDS
                    or isinstance(value, re.Pattern)):  # fmt: skip
                continue
            for text in strings(value):
                yield module_name, name, text


TEMPLATES = list(templates())


def test_the_walk_sees_every_message_table() -> None:
    names = {name for _, name, _ in TEMPLATES}
    assert {"FOOTER", "HELP_COMMANDS", "TEXT", "RETRY", "NOT_A_JUDGE", "TITLE", "LINES",
            "WATCHING", "BEAT", "LINKED", "EMAIL_TEXT"} <= names  # fmt: skip
    assert len(TEMPLATES) > 400


def test_no_template_shouts_hypes_or_leans() -> None:
    bad = [(m, n, t) for m, n, t in TEMPLATES if "!" in t or HYPE.search(t) or LEAN.search(t)]
    assert bad == []


def test_every_template_passes_the_guards_word_rules() -> None:
    bad = [(m, n, t, guard.check(t, t).problems) for m, n, t in TEMPLATES
           if not guard.check(t, t).ok]  # fmt: skip
    assert bad == []


def test_research_not_advice_lives_only_in_the_footer_table() -> None:
    bad = [(m, n, t) for m, n, t in TEMPLATES
           if n != "FOOTER" and any(f in t for f in FOOTERS)]  # fmt: skip
    assert bad == []


def test_no_web_template_shouts_hypes_or_leans() -> None:
    pages = sorted((REPO / "networth/web/templates").glob("*.html"))
    assert len(pages) > 5
    for page in pages:
        text = SCRIPT.sub("", page.read_text(encoding="utf-8"))
        text = text.replace("<!", "").replace("!=", "")
        assert "!" not in text, page.name
        assert not HYPE.search(text) and not LEAN.search(text), page.name


# --- one sample of every message type, in every language -----------------------------------


@pytest.fixture
def cfg() -> config.Config:
    return config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)


@pytest.fixture
def chat(tmp_path: Path, cfg: config.Config, monkeypatch: pytest.MonkeyPatch) -> Chat:
    from networth import sim
    from tests.test_sim import varying

    monkeypatch.setattr(sim, "load_table", varying)
    chat = Chat(tmp_path, Services(tmp_path / "data", "https://nw.example", cfg=cfg,
                                   link_secret="s" * 32))  # fmt: skip
    onboard(chat)
    return chat


def in_lang(chat: Chat, lang: str) -> Chat:
    chat.store.save_profile(replace(chat.profile, lang=lang))
    return chat


def last_titled(chat: Chat, title: str) -> Message:
    return next(m for m in reversed(chat.bot.messages) if m.title == title)


def watch_hit(chat: Chat, lang: str) -> Message:
    in_lang(chat, lang).say("/watch RBI rate changes")
    story(chat, "s1", "RBI raises repo rate to 5.50%", type="rbi_hike")
    assert watches(chat) == 1
    return chat.bot.messages[-1]


def plan_message(chat: Chat, lang: str) -> Message:
    in_lang(chat, lang).say("/plan")
    return last_titled(chat, commands.PLAN_TITLE[lang])


def range_message(chat: Chat, lang: str) -> Message:
    in_lang(chat, lang).say("/range")
    return chat.bot.messages[-1]


def fixed(table: Mapping[str, str]) -> Callable[[Chat, str], Message]:
    def build(chat: Chat, lang: str) -> Message:
        reply = deliver(Answer.fixed(table), lang, chat.services)
        assert isinstance(reply.message, Message)
        return reply.message

    return build


def done(chat: Chat, lang: str) -> Message:
    return onboarding.done_message(replace(chat.profile, lang=lang))


def email_done(chat: Chat, lang: str) -> Message:
    return email_onboard.done_message(replace(chat.profile, lang=lang))


WITH_FOOTER: Final[dict[str, Callable[[Chat, str], Message]]] = {
    "brief": lambda chat, lang: event_brief().message(lang),
    "alert": lambda chat, lang: alert_message(insight(9), lang),
    "watch hit": watch_hit,
    "help": lambda chat, lang: commands.help_message(lang),
    "/plan": plan_message,
    "setup done": done,
    "email setup done": email_done,
    "today": fixed(today.NOT_READ),
    "why": fixed(today.NO_LEAD),
    "tip": fixed(tip.CANT_SEARCH),
    "explain": fixed(explain.CANT_FETCH),
    "plan question": fixed(today.NOT_A_JUDGE),
    "range": range_message,
    "range not ready": fixed(today.RANGE_NOT_READY),
    "scope": fixed(today.SCOPE),
}


def asking(step: Step) -> Callable[[Chat, str], Message]:
    def build(chat: Chat, lang: str) -> Message:
        p = replace(chat.profile, lang=lang, step=step)
        message = onboarding.prompt(p, chat.plan).message
        assert isinstance(message, Message)
        return message

    return build


def retry(chat: Chat, lang: str) -> Message:
    p = replace(chat.profile, lang=lang, step=Step.AMOUNT)
    message = onboarding.advance(p, chat.plan, "lots", NOW).replies[0].message
    assert isinstance(message, Message)
    return message


def ack(table: Mapping[str, str]) -> Callable[[Chat, str], Message]:
    def build(chat: Chat, lang: str) -> Message:
        message = onboarding.Reply(table[lang]).message
        assert isinstance(message, Message)
        return message

    return build


WITHOUT_FOOTER: Final[dict[str, Callable[[Chat, str], Message]]] = {
    **{f"asks {step}": asking(step) for step in onboarding.QUESTIONS},
    "retry": retry,
    "paused": ack(commands.PAUSED),
    "stopped": ack(commands.STOPPED),
    "try again": ack(commands.TRY_AGAIN),
    "too many": ack(commands.TOO_MANY),
    "unknown command": ack(commands.UNKNOWN_COMMAND),
    "plan kept": ack(commands.PLAN_KEPT),
}


def footers_in(m: Message) -> int:
    return sum(plain(m).count(f) for f in FOOTERS)


def check_language(m: Message, lang: str) -> None:
    body = plain(replace(m, footer=""))
    if lang == "hi":
        assert DEVANAGARI.search(body), body


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("kind", list(WITH_FOOTER))
def test_each_answer_type_ends_with_one_footer_in_its_language(chat: Chat, kind: str,
                                                               lang: str) -> None:  # fmt: skip
    m = WITH_FOOTER[kind](chat, lang)
    assert m.footer == FOOTER[lang]
    assert footers_in(m) == 1 and plain(m).endswith(FOOTER[lang])
    check_language(m, lang)


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("kind", list(WITHOUT_FOOTER))
def test_questions_retries_and_acks_carry_no_footer(chat: Chat, kind: str, lang: str) -> None:
    m = WITHOUT_FOOTER[kind](chat, lang)
    assert footers_in(m) == 0 and m.footer == ""
    if kind != f"asks {Step.LANG}":  # the language question is bilingual by design
        check_language(m, lang)


def numbers_in_html(m: Message) -> set[float]:
    return guard.numbers(htmllib.unescape(TAG.sub(" ", html(m))))


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("kind", list(WITH_FOOTER))
def test_the_html_render_holds_no_number_the_plain_one_lacks(chat: Chat, kind: str,
                                                             lang: str) -> None:  # fmt: skip
    m = WITH_FOOTER[kind](chat, lang)
    text = plain(m)
    assert numbers_in_html(m) <= guard.numbers(text)
    assert guard.check(text, text).ok, guard.check(text, text).problems


# --- onboarding in the user's language -----------------------------------------------------


def test_setup_asks_the_language_first_in_both_scripts(chat: Chat) -> None:
    fresh = new_profile(7, NOW)
    reply = onboarding.prompt(fresh, None)
    assert fresh.step is Step.LANG
    assert "Which language" in reply.text and DEVANAGARI.search(reply.text)
    assert [b.label for row in reply.buttons for b in row] == ["English", "हिंदी", "Hinglish"]


HINGLISH_TAPS = ("ob:lang:hinglish", "ob:goal:house", "ob:horizon:4", "ob:amount:100000",
                 "ob:day:1", "ob:drop:20", "ob:exclude:crypto", "ob:exclude:done",
                 "ob:plan:balanced")  # fmt: skip


def test_a_hinglish_setup_asks_and_sums_up_in_hinglish(tmp_path: Path) -> None:
    chat = Chat(tmp_path)
    chat.say("/start")
    chat.tap(HINGLISH_TAPS[0])
    assert chat.bot.last.startswith("Setup ke liye kuch chhote sawaal.")
    assert "Ghar" in chat.bot.labels()
    for data in HINGLISH_TAPS[1:]:
        chat.tap(data)
    assert chat.bot.last.startswith("Mere paas yeh hai.")
    assert "Har mahine: ₹1,00,000, 1 tareekh ko" in chat.bot.last
    assert "Bahar rakha: Crypto" in chat.bot.last
    chat.tap("ob:confirm:ok")
    assert chat.bot.messages[-1].title == "Sab taiyaar hai."
    assert chat.bot.last.endswith("Research hai, advice nahin.")


def test_typed_local_labels_and_english_words_both_parse(tmp_path: Path) -> None:
    chat = Chat(tmp_path)
    chat.say("/start")
    for answer in ("हिंदी", "घर", "5", "1 lakh", "1", "20", "हो गया", "balanced"):
        chat.say(answer)
    p = chat.profile
    assert (p.lang, p.goal, p.horizon_years, p.monthly_amount) == ("hi", "house", 5, 100_000)
    assert p.step is Step.CONFIRM and chat.bot.last.startswith("मेरे पास यह है।")
    chat.say("सही है")
    assert chat.profile.step is Step.DONE


def test_a_hindi_retry_is_in_hindi_and_keeps_the_question(tmp_path: Path) -> None:
    chat = Chat(tmp_path)
    chat.say("/start")
    for data in ("ob:lang:hi", "ob:goal:house", "ob:horizon:4"):
        chat.tap(data)
    chat.say("बहुत सारा")
    assert chat.bot.last.startswith("यह रक़म समझ नहीं आई।")
    assert "आप हर महीने लगभग कितना निवेश करते हैं?" in chat.bot.last
    assert chat.bot.sent[-1][2], "the retry keeps the buttons"


def test_fixing_an_answer_from_the_summary_uses_local_labels(chat: Chat) -> None:
    in_lang(chat, "hinglish")
    chat.store.save_profile(replace(chat.profile, step=Step.CONFIRM))
    chat.say("kuch badalna hai")
    assert chat.bot.last == "Kya badalna hai?"
    assert "Samay" in chat.bot.labels()
    chat.say("samay")
    assert chat.profile.step is Step.HORIZON


def test_the_email_setup_asks_the_language_first(tmp_path: Path) -> None:
    from networth.app.store import new_email_profile

    out = email_onboard.start(new_email_profile("a@example.com", NOW))
    assert out.profile.step is Step.LANG
    assert email_onboard.EMAIL_STEPS[0] is Step.LANG


def test_the_plan_line_names_the_buckets_in_hindi() -> None:
    plan = Plan("u", "balanced", {"safety": 20, "core": 70, "growth": 10}, 20, NOW)
    assert onboarding.plan_line(plan, "hi") == "Balanced. 20% सुरक्षा, 70% कोर, 10% ग्रोथ"
    assert onboarding.plan_line(plan) == "Balanced. 20% safety, 70% core, 10% growth"


def test_the_late_day_retry_is_local(tmp_path: Path) -> None:
    p = replace(new_profile(7, NOW), lang="hinglish", step=Step.DAY)
    reply = onboarding.advance(p, None, "31", NOW).replies[0]
    assert reply.text.startswith("1 se 28 tak ki koi tareekh chun sakte hain")
