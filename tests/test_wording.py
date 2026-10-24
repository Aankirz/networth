"""No user-facing string may tell the user what to do with their money.

Two nets: every string literal in the bot and server code (docstrings aside), and every text
and button label the bot actually sent across a full onboarding and every command.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.test_onboarding import Chat, onboard

REPO = Path(__file__).resolve().parents[1]
SOURCES = sorted([*REPO.glob("networth/bot/*.py"), *REPO.glob("networth/app/*.py")])
BANNED = re.compile(
    r"\b(buy|sell|guaranteed|sure shot|should|can['’]t lose|multibagger|target price)\b",
    re.IGNORECASE,
)


def docstring_nodes(tree: ast.AST) -> set[int]:
    owners = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    ids: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None) if isinstance(node, owners) else None
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            ids.add(id(body[0].value))
    return ids


def literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = docstring_nodes(tree)
    strings = (
        n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    )
    return [n.value for n in strings if id(n) not in skip]


def test_the_scan_sees_the_bot_code() -> None:
    names = {p.name for p in SOURCES}
    assert {"onboarding.py", "commands.py", "main.py"} <= names
    assert BANNED.search("You Should BUY now") and not BANNED.search("Research, not advice.")


def test_no_banned_words_in_source_strings() -> None:
    hits = [(p.name, s) for p in SOURCES for s in literals(p) if BANNED.search(s)]
    assert hits == []


def test_no_banned_words_in_anything_sent(tmp_path: Path) -> None:
    chat = Chat(tmp_path)
    chat.say("/help")
    onboard(chat, confirm=False)
    chat.tap("ob:confirm:fix")
    chat.tap("ob:confirm:plan")
    chat.tap("ob:plan:own")
    chat.say("nonsense")
    chat.say("20 70 10")
    chat.tap("ob:confirm:ok")
    for line in ("/plan", "/pause", "/resume", "what happened today", "hi", "/nope", "/stop"):
        chat.say(line)
    chat.say("/start")
    sent = chat.bot.texts + chat.bot.labels() + [t for _, t in chat.bot.answers if t]
    assert len(sent) > 30
    assert [s for s in sent if BANNED.search(s)] == []
