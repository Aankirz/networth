"""Keiki turn signatures: Ed25519 against a JWKS we publish ourselves, and the optional HMAC."""

from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from networth.keiki.verify import Keys, verify
from tests.keiki_fakes import (
    HMAC_SECRET,
    NOW,
    ed25519_headers,
    fake_keys,
    hmac_headers,
    jwks,
)

BODY = b'{"type":"keiki.turn","turnId":"t1"}'


def test_a_valid_ed25519_signature_is_trusted() -> None:
    assert verify(ed25519_headers(BODY), BODY, NOW, fake_keys(), None) is None


def test_a_valid_hmac_signature_is_trusted_when_the_secret_is_set() -> None:
    assert verify(hmac_headers(BODY), BODY, NOW, fake_keys(), HMAC_SECRET) is None


def test_an_hmac_signature_alone_is_not_enough_without_our_secret() -> None:
    assert verify(hmac_headers(BODY), BODY, NOW, fake_keys(), None) == "unsigned"


def test_a_changed_body_fails_both_signatures() -> None:
    headers = {**ed25519_headers(BODY), **hmac_headers(BODY)}
    assert verify(headers, BODY + b" ", NOW, fake_keys(), HMAC_SECRET) == "bad_signature"


def test_a_signature_by_another_key_is_rejected() -> None:
    forged = ed25519_headers(BODY, key=Ed25519PrivateKey.generate())
    assert verify(forged, BODY, NOW, fake_keys(), None) == "bad_signature"


def test_the_turn_token_is_part_of_what_is_signed() -> None:
    headers = {**ed25519_headers(BODY), "Keiki-Turn-Token": "another-token"}
    assert verify(headers, BODY, NOW, fake_keys(), None) == "bad_signature"


def test_a_signature_older_than_five_minutes_is_stale() -> None:
    assert verify(ed25519_headers(BODY, t=NOW - 301), BODY, NOW, fake_keys(), None) == "stale"
    assert verify(hmac_headers(BODY, t=NOW + 301), BODY, NOW, fake_keys(), HMAC_SECRET) == "stale"


def test_a_request_with_no_signature_is_unsigned() -> None:
    assert verify({}, BODY, NOW, fake_keys(), HMAC_SECRET) == "unsigned"


def test_an_unknown_kid_is_rejected_after_one_refresh() -> None:
    fetches: list[int] = []
    keys = Keys(lambda: fetches.append(1) or jwks("published-kid"), clock=lambda: 0.0)
    headers = ed25519_headers(BODY, kid="never-published")
    assert verify(headers, BODY, NOW, keys, None) == "unknown_kid"
    assert verify(headers, BODY, NOW, keys, None) == "unknown_kid"
    assert len(fetches) == 1, "a second unknown kid within a minute does not refetch"


def test_a_rotated_key_is_picked_up_on_its_first_use() -> None:
    published = ["old-kid"]
    clock = [0.0]
    keys = Keys(lambda: jwks(published[0]), clock=lambda: clock[0])
    assert verify(ed25519_headers(BODY, kid="old-kid"), BODY, NOW, keys, None) is None
    published[0], clock[0] = "new-kid", 61.0
    assert verify(ed25519_headers(BODY, kid="new-kid"), BODY, NOW, keys, None) is None


def test_header_names_match_in_any_case() -> None:
    headers = {k.lower(): v for k, v in ed25519_headers(BODY).items()}
    assert verify(headers, BODY, NOW, fake_keys(), None) is None
