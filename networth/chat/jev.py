"""Jev, TypeSafe's typed-decision model, for closed choices such as the chat intent.

    pick = choose(state, question, criteria, env, deadline_s=4, log_path=call_log)

The question is TypeSafe's own `Choice` shape from typesafe_sdk, sent through the Vercel AI
Gateway's /evaluate endpoint with AI_GATEWAY_API_KEY, AI_GATEWAY_BASE_URL and JEV_MODEL. The
pattern follows ~/Desktop/zoya/zoya/decisions.py. Any error, timeout or malformed reply is
None, so the caller falls back to the model. Each call is logged to llm_calls.jsonl as role
"jev"; the gateway reports no price, so its cost is recorded as 0.

APIs: https://docs.typesafe.ai/introduction/quickstart, https://vercel.com/docs/ai-gateway
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import httpx2
from typesafe_sdk import Choice

from networth import net

log = logging.getLogger("networth.chat")

MS_PER_S: Final = 1000
CONNECT_TIMEOUT_S: Final = 3.0
KEYS: Final = ("AI_GATEWAY_API_KEY", "AI_GATEWAY_BASE_URL", "JEV_MODEL")


@dataclass(frozen=True)
class Pick:
    name: str
    confidence: float
    latency_ms: int


def configured(env: Mapping[str, str]) -> bool:
    return all(env.get(k) for k in KEYS)


def choose(
    state: str,
    question: str,
    criteria: Mapping[str, str],
    env: Mapping[str, str],
    *,
    deadline_s: float,
    log_path: Path,
    client: httpx2.Client | None = None,
) -> Pick | None:
    if not configured(env):
        return None
    body = {
        "model": env["JEV_MODEL"],
        "state": state,
        "questions": {
            "pick": Choice(instructions=question, criteria=dict(criteria)).model_dump(
                exclude_none=True
            )
        },
    }
    url = env["AI_GATEWAY_BASE_URL"].rstrip("/") + "/evaluate"
    headers = {"Authorization": f"Bearer {env['AI_GATEWAY_API_KEY']}"}
    http = client or net.ipv4_client(deadline_s, CONNECT_TIMEOUT_S)
    started = time.monotonic()

    def post() -> tuple[dict, net.Usage]:
        response = http.post(url, json=body, headers=headers, timeout=deadline_s)
        response.raise_for_status()
        return response.json(), net.Usage()

    try:
        reply = net.metered(post, call="jev_pick", role="jev", model=env["JEV_MODEL"],
                            deadline_s=deadline_s, log_path=log_path)  # fmt: skip
        answer = reply["answers"]["pick"]
        name, confidence = str(answer["choice"]), float(answer.get("confidence", 0.0))
    except Exception as exc:  # noqa: BLE001 - every failure means "let the model decide"
        log.warning("jev unavailable: %s", type(exc).__name__)
        return None
    if name not in criteria:
        return None
    return Pick(name, confidence, round((time.monotonic() - started) * MS_PER_S))
