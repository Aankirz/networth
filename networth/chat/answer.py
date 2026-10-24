"""One shape for every chat reply: the template code wrote, what the guard checks the writer
against, and the writer's task. deliver() is the only place a chat reply meets a model.

    reply = deliver(Answer(template, source, task), profile, text_lang, services)

task None means the words are fixed: an English reader gets the template as is, anyone else a
guarded translation of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from networth import guard
from networth.app.services import Services
from networth.bot.briefs import LANGUAGES
from networth.bot.onboarding import Reply
from networth.bot.telegram import Keyboard

TRANSLATE_TASK: Final = """Write this message in {language}. Keep every number, name, link and
line break exactly. Add nothing. Return only the message text."""
REWORD_TASK: Final = """{task} Write it in {language}. Use only the facts below; keep every number
exactly as written and every link unchanged. Never say buy, sell, apply, skip, score or rank,
and never say what the reader should do. Return only the message text."""


@dataclass(frozen=True)
class Answer:
    template: str
    source: str
    task: str | None = None
    buttons: Keyboard = ()
    kind: str = "chat"
    draft: bool = True  # the template words the same facts; False when it is only a fallback


def deliver(answer: Answer, lang: str, services: Services) -> Reply:
    language = LANGUAGES.get(lang, LANGUAGES["en"])
    models = services.models
    if models is None or (answer.task is None and lang == "en"):
        return Reply(answer.template, answer.buttons)
    if answer.task is None:
        task, facts = TRANSLATE_TASK.format(language=language), answer.template
    else:
        task = REWORD_TASK.format(task=answer.task, language=language)
        plain = f"\n\nPlain version:\n{answer.template}" if answer.draft else ""
        facts = f"{answer.source}{plain}"
    out = guard.guarded(lambda fb: models.write(task, facts, fb), answer.source,
                        answer.template, services.guard_log, answer.kind)  # fmt: skip
    return Reply(out.text, answer.buttons)
