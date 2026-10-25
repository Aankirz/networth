"""One shape for every chat reply: the template code wrote, what the guard checks the writer
against, and the writer's task. deliver() is the only place a chat reply meets a model.

    reply = deliver(Answer(template, source, task), profile, text_lang, services)

task None means the words are fixed: an English reader gets the template as is, anyone else a
guarded translation of it. A template the guard already rejects goes out untranslated, since
a translation would keep its words. A lead is a fixed first line, written per language, put
before the reply. deliver_traced also says which words went out: the guard's "model",
"rewrite" or "template", or "fixed" when no model was asked.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

from networth import guard
from networth.app.services import Services
from networth.bot.briefs import LANGUAGES
from networth.bot.onboarding import Reply
from networth.bot.telegram import Keyboard

TRANSLATE_TASK: Final = """Write this message in {language}. Keep every number, name, link and
line break exactly. Add nothing. Write any instruction about using the app as a statement
('/plan se badal sakte hain'), never as a command. Return only the message text."""
REWORD_TASK: Final = """{task} Write it in {language}. Use only the facts below; keep every number
exactly as written and every link unchanged. Never say buy, sell, apply, skip, score or rank,
and never say what the reader should do. Write every sentence as a statement, never as a
command, polite forms included. Return only the message text."""


@dataclass(frozen=True)
class Answer:
    template: str
    source: str
    task: str | None = None
    buttons: Keyboard = ()
    kind: str = "chat"
    draft: bool = True  # the template words the same facts; False when it is only a fallback
    written: bool = False  # the template is already in the reader's language: sent as is
    lead: Mapping[str, str] = field(default_factory=dict)  # a fixed first line per language


Used = guard.Used | Literal["fixed"]


def deliver(answer: Answer, lang: str, services: Services) -> Reply:
    return deliver_traced(answer, lang, services)[0]


def deliver_traced(answer: Answer, lang: str, services: Services) -> tuple[Reply, Used]:
    text, used = words(answer, lang, services)
    lead = answer.lead.get(lang) or answer.lead.get("en")
    return Reply(f"{lead}\n\n{text}" if lead else text, answer.buttons), used


def words(answer: Answer, lang: str, services: Services) -> tuple[str, Used]:
    language = LANGUAGES.get(lang, LANGUAGES["en"])
    models = services.models
    if models is None or answer.written or (answer.task is None and lang == "en"):
        return answer.template, "fixed"
    if answer.task is None:
        verdict = guard.check(answer.template, answer.source)
        if not verdict.ok:  # a translation keeps the template's words, so it could not pass
            guard.log_verdict(services.guard_log, answer.kind, "template", verdict)
            return answer.template, "template"
        task, facts = TRANSLATE_TASK.format(language=language), answer.template
    else:
        task = REWORD_TASK.format(task=answer.task, language=language)
        plain = f"\n\nPlain version:\n{answer.template}" if answer.draft else ""
        facts = f"{answer.source}{plain}"
    out = guard.guarded(lambda fb: models.write(task, facts, fb), answer.source,
                        answer.template, services.guard_log, answer.kind)  # fmt: skip
    return out.text, out.used
