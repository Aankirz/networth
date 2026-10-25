"""One shape for every chat reply: the template code wrote, the same words in each language, what
the guard checks the writer against, and the writer's task. deliver() is the only place a chat
reply meets a model, and it hands back a Message: the words as the body, any code-owned link
after them, and no footer: the owner dropped every disclaimer (2026-10-25).

    reply = deliver(Answer(template, source, task, words=by_lang), text_lang, services)
    reply = deliver(Answer.fixed(TABLE), "hinglish", services)    # fixed words, no model

task None means the words are fixed: the reader gets their language's version as is, and code
writes every fixed answer in English, Hindi and Hinglish, so nothing is translated. With a
task, the model writes in the reader's language; when the guard falls back, the reader gets the
template in their own language. The model writes plain text only: markup in it
is escaped at the Telegram boundary and shows as text. deliver_traced also says which words went
out: the guard's "model", "rewrite" or "template", or "fixed" when no model was asked.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

from networth import guard
from networth.app.services import Services
from networth.bot.message import DISCLAIMER, Link, Message, say
from networth.bot.onboarding import Reply
from networth.bot.telegram import Keyboard

LANGUAGES: Final = {
    "en": "English",
    "hi": "Hindi in Devanagari script",
    "hinglish": "Hinglish: Hindi in Roman script, with English for money terms",
}
REWORD_TASK: Final = """{task} Write it in {language}, as plain text with no markup. Use only the
facts below; keep every number exactly as written and every link unchanged. Never say buy, sell,
apply, skip, score or rank, and never say what the reader should do. Write every sentence as a
statement, never as a command, polite forms included. Add no disclaimer or caveat about advice.
Return only the message text."""
VIEW_TASK: Final = """{task} Write it in {language}, as plain text with no markup. Use only the
facts below; keep every number exactly as written and every link unchanged. Keep Networth's read
as the first sentence, saying plainly what Networth would do. Never promise a return or a price,
and add no disclaimer or caveat about advice. Return only the message text."""


@dataclass(frozen=True)
class Answer:
    template: str
    source: str
    task: str | None = None
    buttons: Keyboard = ()
    kind: str = "chat"
    draft: bool = True  # the template words the same facts; False when it is only a fallback
    words: Mapping[str, str] = field(default_factory=dict)  # the template, per language
    lead: Mapping[str, str] = field(default_factory=dict)  # a fixed first line per language
    link: Link | None = None  # one code-owned link after the words, its preview kept
    card: Mapping[str, object] | None = None  # a market answer's typed card, for charts
    view: bool = False  # Networth's read on a stock: the guard lets view words through
    footer: bool = (
        True  # ponytail: ignored, no footer since 2026-10-25; bot/holdings still passes it
    )

    @classmethod
    def fixed(cls, words: Mapping[str, str], **kwargs: object) -> Answer:
        """Fixed words written in every language: no model, no translation."""
        return cls(words["en"], words["en"], words=words, **kwargs)  # type: ignore[arg-type]

    def written(self, lang: str) -> str | None:
        """The template in this language, if code wrote one."""
        return self.words.get(lang) or (self.template if lang == "en" else None)


Used = guard.Used | Literal["fixed"]


def deliver(answer: Answer, lang: str, services: Services) -> Reply:
    return deliver_traced(answer, lang, services)[0]


def without_disclaimer(text: str) -> str:
    """The text with any disclaimer sentence a model added taken out: the owner wants none."""
    return re.sub(r"[ \t]{2,}", " ", DISCLAIMER.sub("", text)).strip()


def deliver_traced(answer: Answer, lang: str, services: Services) -> tuple[Reply, Used]:
    text, used = words(answer, lang, services)
    lead = say(answer.lead, lang) if answer.lead else ""
    body = tuple(b for b in (lead, without_disclaimer(text), answer.link) if b)
    message = Message(body=body, preview=answer.link.url if answer.link else None)
    return Reply(message, answer.buttons, answer.card), used


def words(answer: Answer, lang: str, services: Services) -> tuple[str, Used]:
    mine = answer.written(lang)
    models = services.models
    if models is None or answer.task is None:
        return mine or answer.template, "fixed"
    task = (VIEW_TASK if answer.view else REWORD_TASK).format(
        task=answer.task, language=LANGUAGES.get(lang, LANGUAGES["en"])
    )
    plain = f"\n\nPlain version:\n{answer.template}" if answer.draft else ""
    out = guard.guarded(lambda fb: models.write(task, f"{answer.source}{plain}", fb),
                        answer.source, mine or answer.template, services.guard_log,
                        answer.kind, view=answer.view)  # fmt: skip
    return out.text, out.used
