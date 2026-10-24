"""Jev against the cheap model on the chat intent pick, on labelled messages.

    uv run python -m evals.intent_accuracy

Both pickers get the same state, question and criteria networth.chat sends. Prints accuracy
and latency per picker and writes evals/intent_results.json. The result decides
product.use_jev_for_intent in config.toml.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path
from typing import Final

from networth.app.settings import ENV_FILE, read_dotenv
from networth.chat import CRITERIA, QUESTION, STATE, Intent, jev
from networth.config import DATA_DIR, load_config
from networth.llm import OpenAIModels

T, W, X, E, P, NA = (Intent.WHAT_HAPPENED_TODAY, Intent.WHY, Intent.TIP_CHECK,
                    Intent.EXPLAIN_THIS, Intent.PLAN_QUESTION, Intent.OTHER)  # fmt: skip
# (message, forwarded, label)
LABELLED: Final = (
    ("What happened in the market today?", False, T),
    ("any big news today?", False, T),
    ("aaj market mein kya hua?", False, T),
    ("आज बाजार में क्या हुआ?", False, T),
    ("kal se ab tak koi badi khabar?", False, T),
    ("How did Nifty do this week?", False, T),
    ("Why did you say banks beat the Nifty?", False, W),
    ("why?", False, W),
    ("yeh 14 of 22 kahan se aaya?", False, W),
    ("ऐसा क्यों कहा आपने?", False, W),
    ("where does that history line come from?", False, W),
    ("Why is my brief talking about the RBI?", False, W),
    ("Tata Motors will double in 3 months, insider info", True, X),
    ("RBI ne repo rate badha diya, banks girenge", True, X),
    ("Breaking: SEBI bans F&O trading from Monday", True, X),
    ("Is it true that the government is merging SBI and PNB?", False, X),
    ("सुना है सोना 1 लाख पार जाएगा, सच है?", False, X),
    ("Bhai group mein aaya hai ki Adani ka FPO cancel ho gaya, sach hai kya?", False, X),
    ("What is a DRHP?", False, E),
    ("PAT ka matlab kya hota hai?", False, E),
    ("https://www.chittorgarh.com/ipo/acme-foods-ipo/1234/", False, E),
    (
        "Acme Foods IPO. Price band ₹95 to ₹100. Lot size 150. Issue size ₹1,200 crore. Retail "
        "quota 35%. GMP ₹22. Subscription opens Oct 28.",
        True,
        E,
    ),
    ("SIP aur lumpsum mein kya farak hai?", False, E),
    ("यह ग्रे मार्केट प्रीमियम क्या होता है?", False, E),
    ("What is my plan again?", False, P),
    ("How much am I investing each month?", False, P),
    ("mera investing day kab hai?", False, P),
    ("मेरा प्लान क्या है?", False, P),
    ("can you remind me what split I chose?", False, P),
    ("did I leave out crypto?", False, P),
    ("hi", False, NA),
    ("thanks!", False, NA),
    ("shukriya bhai", False, NA),
    ("who made you?", False, NA),
    ("Write me a poem about the monsoon", False, NA),
    ("नमस्ते", False, NA),
)


def state_for(text: str, forwarded: bool) -> str:
    kind = "A message the user forwarded" if forwarded else "The user wrote"
    return STATE.format(kind=kind, text=text[:2000])


def main() -> int:
    env = {**read_dotenv(ENV_FILE), **os.environ}
    cfg = load_config()
    call_log = Path(DATA_DIR) / "llm_calls.jsonl"
    models = OpenAIModels(cfg, call_log)
    rows = []
    for text, forwarded, label in LABELLED:
        state = state_for(text, forwarded)
        pick = jev.choose(state, QUESTION, CRITERIA, env, deadline_s=10, log_path=call_log)
        started = time.monotonic()
        model = models.pick(QUESTION, CRITERIA, state)
        model_ms = round((time.monotonic() - started) * 1000)
        rows.append({"text": text, "label": label.value,
                     "jev": pick.name if pick else None,
                     "jev_confidence": pick.confidence if pick else None,
                     "jev_ms": pick.latency_ms if pick else None,
                     "model": model, "model_ms": model_ms})  # fmt: skip
        print(f"{label.value:20} jev={rows[-1]['jev']!s:20} model={model!s:20} {text[:50]}")
    summary = {}
    for who in ("jev", "model"):
        right = sum(r[who] == r["label"] for r in rows)
        times = [r[f"{who}_ms"] for r in rows if r[f"{who}_ms"] is not None]
        summary[who] = {"correct": right, "total": len(rows), "accuracy": right / len(rows),
                        "median_ms": statistics.median(times) if times else None,
                        "max_ms": max(times) if times else None}  # fmt: skip
    floor = cfg.product.jev_min_confidence
    confident = [r for r in rows if r["jev_confidence"] is not None
                 and r["jev_confidence"] >= floor]  # fmt: skip
    right = sum(r["jev"] == r["label"] for r in confident)
    summary["jev_confident"] = {"floor": floor, "n": len(confident), "correct": right}
    print(json.dumps(summary, indent=2))
    out = Path(__file__).with_name("intent_results.json")
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
