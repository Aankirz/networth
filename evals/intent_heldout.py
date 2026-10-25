"""Held-out intent messages, written on 2026-10-25 after the criteria edit in 7885c91 and
before any run on them. Never tune the criteria against these; add a new set instead.

Each row is (message, forwarded, label).
"""

from __future__ import annotations

from typing import Final

from networth.chat import Intent

T, W, X, E, P, NA = (Intent.WHAT_HAPPENED_TODAY, Intent.WHY, Intent.TIP_CHECK,
                     Intent.EXPLAIN_THIS, Intent.PLAN_QUESTION, Intent.OTHER)  # fmt: skip

HELDOUT: Final = (
    ("anything important in the markets since morning?", False, T),
    ("Sensex aaj upar gaya ya neeche?", False, T),
    ("आज की बड़ी खबरें बताओ", False, T),
    ("What's the latest on the Fed?", False, T),
    ("how come the brief mentioned tariffs?", False, W),
    ("normal 59% matlab kya, yeh number kahan se?", False, W),
    ("यह आंकड़ा किस आधार पर है?", False, W),
    ("what's the source for that line about IT stocks?", False, W),
    ("Forwarded as received: LIC policy holders will get 20% bonus from Diwali", True, X),
    ("Paytm band ho raha hai kal se, sab paisa nikalo jaldi!!", True, X),
    ("Heard Reliance is announcing a bonus issue tomorrow, true?", False, X),
    ("सरकार ने म्यूचुअल फंड पर नया टैक्स लगा दिया, क्या यह सच है?", True, X),
    ("HDFC Bank merger with ICICI confirmed, WhatsApp pe aaya", True, X),
    (
        "Zentech Labs Ltd IPO. Price band ₹410-432. Lot 34 shares. Issue opens Nov 3. "
        "Anchor portion 60% of QIB. Listing on BSE and NSE.",
        True,
        E,
    ),
    ("what does 'offer for sale' mean in an IPO?", False, E),
    ("NAV aur expense ratio samjha do", False, E),
    ("https://www.moneycontrol.com/news/business/ipo/zentech-labs-ipo-details-123.html", False, E),
    ("बोनस शेयर क्या होता है?", False, E),
    ("am I down for the 25th or the 1st?", False, P),
    ("mera monthly amount kitna set hai?", False, P),
    ("what's my risk setting?", False, P),
    ("good morning", False, NA),
    ("can you book me a cab?", False, NA),
    ("ok samajh gaya, thanks", False, NA),
)
