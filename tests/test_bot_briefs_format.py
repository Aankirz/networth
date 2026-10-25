"""A brief stored by an older deploy is written afresh on the next /brief, not resent."""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

from networth.bot import briefs
from tests.test_chat import FakeChatModels, cfg, talk  # noqa: F401 - cfg is a fixture
from tests.test_onboarding import NOW

LEGACY = (
    "Investing day, Oct 25. ₹1,00,000 ready.\n\nWhere history leans after months like this:\n"
    "🟢 Banks beat the market in 6 of 9 similar months."
)


def legacy_inputs_key(chat) -> str:
    """The key the code before FORMAT_KEY wrote: the profile and plan, nothing about the code."""
    plan = chat.store.get_plan(chat.profile.user_id)
    used = [getattr(chat.profile, f) for f in briefs.BRIEF_INPUTS]
    used += [plan.name, sorted(plan.targets_pct.items()), plan.max_drop_ok]
    return hashlib.sha256(repr(used).encode()).hexdigest()[: briefs.INPUTS_KEY_CHARS]


def test_a_legacy_brief_is_rewritten_the_same_day_and_still_claims_the_day(
    tmp_path: Path, cfg  # noqa: F811
) -> None:  # fmt: skip
    chat = talk(tmp_path, cfg, FakeChatModels())
    local = briefs.local_now(chat.profile, dt.datetime.fromisoformat(NOW))
    day, uid = local.date().isoformat(), chat.profile.user_id
    assert chat.store.claim_brief(uid, day)
    chat.store.save_brief(uid, day, LEGACY, "template", legacy_inputs_key(chat))

    chat.say("/brief")

    assert chat.bot.last.startswith("Morning. Here's your brief for this month.")
    assert "🟢" not in chat.bot.last and "leans" not in chat.bot.last
    sent = len(chat.bot.sent)
    assert not briefs.send_brief(chat.store, chat.bot, chat.profile, chat.services, local,
                                 proactive=True)  # fmt: skip
    assert len(chat.bot.sent) == sent, "the claim still stops a second scheduled brief"


def test_a_brief_from_the_current_code_is_resent_as_stored(tmp_path: Path, cfg) -> None:  # noqa: F811
    chat = talk(tmp_path, cfg, FakeChatModels())
    chat.say("/brief")
    chat.say("/brief")
    assert chat.bot.messages[-1] == chat.bot.messages[-2]
