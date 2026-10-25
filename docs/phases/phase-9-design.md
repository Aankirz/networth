# Phase 9 design · the conversation shape

This is the data shape and routing, written down before any code. The brief is `docs/phases/phase-9-conversation.md`.

## The constraint that shapes everything

The web contract pins the `Intent` enum. `tests/test_web_api_contract.py` checks that `site/lib/contract.ts` declares every value, and `site/` is out of bounds this phase. So no new `Intent` value can exist. Every new kind of answer reports `Intent.OTHER`, which the site already draws as a text card. The finer kind lives in a second enum, `Talk`, that only the server sees.

## The data shape

One turn is one message, in or out:

```python
@dataclass(frozen=True)
class ChatTurn:  # networth/app/store.py, next to Watch and Message
    role: Literal["user", "bot"]
    text: str  # the user's words, or the bot's sent body without the footer
    intent: str  # the Intent or Talk value that answered, e.g. "what_happened_today", "follow_up"
    at: str  # ISO time, UTC
```

The window is the user's newest turns, oldest first: `tuple[ChatTurn, ...]`.

| Cap | Value | Why |
|---|---|---|
| Count | 8 turns (4 exchanges) | The longest chain the brief asks for is 3 questions deep. 8 turns holds that plus one exchange of context, and keeps a prompt near 5,000 characters at worst. |
| Age | 24 hours | "This morning's answer" still resolves in the evening, and nothing older than a day comes back. A new day starts clean. |
| Stored text | 1,200 characters per turn | A pasted IPO page can be 8,000 characters. The window keeps the start of it, not the whole page. |
| Prompt text | 600 characters per turn | Long histories are cut before they reach a model, never sent whole. |
| Follow-up gap | 30 minutes | A follow-up resolves against the last answer only while the conversation is live. After 30 minutes, "why?" means the brief again, as it does today. |

## Where it lives

A `turns` table in `networth/app/store.py`: `id`, `user_id`, `role`, `text`, `intent` and `at`, indexed on `(user_id, id)`.

- **Only that user's rows.** Every read and write is keyed by `user_id`. The demo user is `web:demo`, so its turns never mix with a real user's.
- **Gone on `/stop`.** `turns` joins `FORGOTTEN_ON_STOP`, so the stopped save deletes it in the same transaction as holdings.
- **Pruned on write.** `add_turns` inserts the exchange, then deletes this user's rows that are past the age cap or older than the newest 8, all in one transaction. Running it twice converges on the same window.
- **Never logged.** The turn text goes only to this table and to the model request. The guard log, the call log and the web and Keiki turn logs keep trace id, intent and verdict, as today.

## Routing

The routing table is `Talk`, a closed set with one handler each:

| Talk | Answers | Words |
|---|---|---|
| `follow_up` | "why?", "and the US?", "explain that simpler", "in Hindi please" | The writer, sourced only from the previous exchange |
| `money` | Concepts, how a thing works, what to read before deciding | The writer. An IPO question starts from a fixed IPO explainer in three languages, so a guard fallback is still a real answer. |
| `should_i` | "Should I apply for the LIC IPO?" | A fixed decline line in three languages, then the `money` answer |
| `greeting`, `thanks`, `about` | "hi", "thanks", "who are you" | Fixed, three languages |
| `off_topic` | Code, recipes, homework | One fixed kind line and a nudge back |
| `dashboard` | "mera dashboard", "open my page" | Fixed words and one button to the signed page |

`respond_traced` keeps its signature, so Telegram, Keiki and the web gain the conversation with no edits there:

1. Read the window.
2. Rules, with no model: dashboard phrases. Then a follow-up when the last bot turn is under 30 minutes old and the message is short and reads like one ("why?", "and …", "explain that", "simpler", "in Hinglish"). With a model and a live conversation, one cheap `pick` decides follow-up or new for any other short message.
3. Otherwise `classify`, unchanged, picks the `Intent`. Jev's measured accuracy still holds.
4. An `OTHER` pick is refined into a `Talk` kind. Rules handle exact small talk and "should I", then one cheap `pick` handles the rest. With no models and no rule match it stays the scope line, as today. A short, unforwarded "should I" question classified as `EXPLAIN_THIS` is refined too.
5. The handler builds an `Answer`, and `deliver_traced` puts it through `guard.guarded` as every chat answer does. The exchange is saved to the window.

The reply language honours an explicit ask ("in Hindi please", "explain that in Hinglish") before the script and Hinglish-word rules.

## The dashboard link

`NETWORTH_SITE_URL` (for example `https://networth-eight-pied.vercel.app`) sets where page links point. Unset, links stay on the server's own `/u` page. `Services.page_base` is the one place that decides, and every page link the bot builds reads it. The link is always `links.sign(profile.link_token, …)`, the stored token signed, so issuing a link never retires another one.

Telegram allows a per-chat menu button of type `web_app` with any HTTPS URL (`setChatMenuButton`, `MenuButtonWebApp`, `WebAppInfo.url` "An HTTPS URL of a Web App"). The bot sets one when onboarding finishes and again on `/dashboard`, and resets it to `default` on `/stop`. With no HTTPS page link it leaves the default commands menu alone.

## What this does not do

- The web demo shares one sample user, so demo visitors share one window. `networth/web/api.py` would need to pass a visitor-scoped user id to separate them. That file is outside this phase.
- Briefs and alerts are not written into the window, so a follow-up to a brief is answered by the existing `why` handler.
