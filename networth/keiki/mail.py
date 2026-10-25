"""Proactive email through Keiki: queue the text, ask Keiki for a turn, send it on that turn.

    mail = Mail(store, KeikiApi(api_key, agent_id))
    mail.queue(profile, reply)        # a brief, an alert or a watch message
    mail.flush(address, turn_client)  # first thing in every Keiki turn for that contact

An external harness can only send inside a turn, so a proactive message waits in the outbox
and a Keiki notice starts a turn for the contact. That turn reaches /keiki/turn like any other,
and its handler flushes the outbox first. Each row goes out under the idempotency key
outbox:<id>, so a flush retried after a crash never sends a row twice.
"""

from __future__ import annotations

import logging
from typing import Final

from networth.app.store import Profile, Store
from networth.bot.onboarding import Reply
from networth.keiki.client import KeikiApi, TurnClient
from networth.keiki.render import plain

log = logging.getLogger("networth.keiki")

NOTICE: Final = (
    "A queued Networth message is waiting for this contact. Run a turn so Networth can send it."
)


class Mail:
    def __init__(self, store: Store, api: KeikiApi) -> None:
        self._store = store
        self._api = api

    def queue(self, profile: Profile, reply: Reply) -> bool:
        """False when the user has no bound email. A failed notice still leaves the row queued,
        so the user's next email turn delivers it."""
        address = self._store.contact_for(profile.user_id)
        if address is None:
            return False
        self._store.queue_mail(profile.user_id, address, plain(reply.text, reply.buttons))
        # ponytail: delivery of a queued mail depends on Keiki dispatching the notice turn to
        # us. If it never does, the mail goes out on the contact's next inbound email.
        try:
            outcome = self._api.notice(address, NOTICE)
        except Exception as exc:  # noqa: BLE001 - the row is queued; the next turn sends it
            outcome = f"failed: {type(exc).__name__}"
        log.info("keiki notice for %s: %s", profile.user_id, outcome)
        return True

    def flush(self, address: str, client: TurnClient) -> int:
        """Send every queued row for this contact, oldest first. Stops at the first failure;
        the rest wait for the next turn."""
        sent = 0
        for row in self._store.pending_mail(address):
            try:
                client.send(row.text, f"outbox:{row.id}")
            except Exception as exc:  # noqa: BLE001 - unsent rows stay queued
                log.warning("outbox %s not sent: %s", row.id, type(exc).__name__)
                break
            self._store.mark_mail_sent(row.id)
            sent += 1
        return sent
