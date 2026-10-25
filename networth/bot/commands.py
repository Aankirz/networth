"""The bot's IO shell: a raw Telegram update in, stored state and sent messages out.

    handle_update(update, store, bot)

The update is parsed here, at the boundary, into Text, Tap or Media. Onboarding answers go to
the pure onboarding.advance; commands are one COMMANDS entry each. Every outgoing message goes
through outbox.send(), the one gate that keeps a stopped user silent and a paused user free
of proactive messages. State is saved before anything is sent, so a failed send never loses an
answer. Chat answers search and call models, so they run after the update lock is released and
one slow tip check never holds up another user's setup.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Final

from networth import brief, chat
from networth.app.services import Services
from networth.app.store import (
    Channel,
    Plan,
    Profile,
    Status,
    Step,
    Store,
    new_profile,
    now_iso,
    user_id_for,
)
from networth.bot import briefs, watches
from networth.bot import holdings as holdings_flow
from networth.bot.message import FOOTER, Link, Message, say
from networth.bot.onboarding import (
    CALLBACK_PREFIX,
    Outcome,
    Reply,
    advance,
    day_label,
    plan_line,
    with_lead,
)
from networth.bot.onboarding import prompt as ask_for
from networth.bot.outbox import send
from networth.bot.telegram import Bot, Button, Keyboard, MenuBot, TelegramError
from networth.chat import dashboard
from networth.chat.answer import deliver
from networth.chat.today import YOUR_PAGE
from networth.holdings import snaptrade

log = logging.getLogger("networth.bot")

STALE_TAP: Final = {
    "en": "That question has moved on.",
    "hi": "वह सवाल आगे बढ़ चुका है।",
    "hinglish": "Woh sawaal aage badh chuka hai.",
}
NOT_A_PHOTO: Final = {
    "en": "I can read photos and text. A screenshot or some pasted text works.",
    "hi": "मैं फ़ोटो और टेक्स्ट पढ़ सकता हूँ। स्क्रीनशॉट या पेस्ट किया हुआ टेक्स्ट भेज सकते हैं।",
    "hinglish": "Main photo aur text padh sakta hoon. Screenshot ya paste kiya hua text bhej "
    "sakte hain.",
}
TRY_AGAIN: Final = {
    "en": "That one didn't go through on my side. Give it a minute and ask me again.",
    "hi": "यह मेरी तरफ़ से नहीं हो पाया। एक मिनट बाद फिर से पूछ सकते हैं।",
    "hinglish": "Yeh meri taraf se nahin ho paaya. Ek minute baad phir se pooch sakte hain.",
}
TOO_MANY: Final = {
    "en": "That's a lot of questions in one hour, so I'm taking a short break. I'll answer again "
    "in a little while.",
    "hi": "एक घंटे में काफ़ी सवाल हो गए, इसलिए मैं थोड़ा रुक रहा हूँ। थोड़ी देर में फिर जवाब दूँगा।",
    "hinglish": "Ek ghante mein kaafi sawaal ho gaye, isliye main thoda ruk raha hoon. Thodi der "
    "mein phir jawab doonga.",
}
PLAN_KEPT: Final = {
    "en": "Got it. Your plan stays just as it is.",
    "hi": "ठीक है। आपका प्लान जैसा है वैसा ही रहेगा।",
    "hinglish": "Theek hai. Aapka plan jaisa hai waisa hi rahega.",
}
HELP_LEAD: Final = {"en": "Here's what I can do.", "hi": "मैं ये काम कर सकता हूँ।",
                    "hinglish": "Main yeh kaam kar sakta hoon."}  # fmt: skip
HELP_ASK: Final = {
    "en": 'Ask "What happened today?" or "Why?"\n'
    "Forward me a tip, and I'll check who reported it\n"
    "Send an IPO page, a link or a screenshot, and I'll explain it\n"
    "Ask anything about money, then follow up: why, simpler, in Hindi",
    "hi": 'आप पूछ सकते हैं "आज क्या हुआ?" या "क्यों?"\n'
    "कोई टिप फ़ॉरवर्ड करने पर मैं देखूँगा कि उसे किसने रिपोर्ट किया\n"
    "IPO पेज, लिंक या स्क्रीनशॉट भेजने पर मैं उसे समझा दूँगा\n"
    "पैसे से जुड़ा कोई भी सवाल पूछ सकते हैं, फिर आगे पूछ सकते हैं: क्यों, और आसान, Hinglish में",
    "hinglish": 'Aap pooch sakte hain "Aaj kya hua?" ya "Kyun?"\n'
    "Koi tip forward karne par main dekhoonga ki use kisne report kiya\n"
    "IPO page, link ya screenshot bhejne par main use samjha doonga\n"
    "Paise se juda koi bhi sawaal pooch sakte hain, phir aage pooch sakte hain: kyun, aur "
    "aasaan, English mein",
}
HELP_COMMANDS: Final = {
    "en": "/brief this month's brief\n/plan see or change your plan\n"
    "/dashboard one tap to your own page\n"
    "/range what your plan could become, replayed over past months\n"
    "/pause pause briefs and alerts\n/resume turn them back on\n/stop stop all messages\n"
    "/erase delete everything I have about you\n"
    "/start set up again or see your answers\n/link a code to use me by email too\n"
    "/sendto email or /sendto telegram, where briefs and alerts go\n"
    "/watch something, to hear once when a confirmed story about it appears\n"
    "/watches see or stop your watches\n/unwatch 1 stop a watch by its number\n"
    "/holdings what you hold, read from a screenshot you send",
    "hi": "/brief इस महीने का ब्रीफ़\n/plan अपना प्लान देखना या बदलना\n"
    "/dashboard एक टैप में आपका अपना पेज\n"
    "/range पुराने महीनों को दोहराकर, आपका प्लान कहाँ तक पहुँच सकता है\n"
    "/pause ब्रीफ़ और अलर्ट रोकना\n/resume उन्हें फिर से चालू करना\n/stop सारे मैसेज बंद करना\n"
    "/erase आपके बारे में मेरे पास जो कुछ है, सब मिटाना\n"
    "/start फिर से सेटअप, या अपने जवाब देखना\n/link ईमेल पर भी इस्तेमाल के लिए कोड\n"
    "/sendto email या /sendto telegram, ब्रीफ़ और अलर्ट किस जगह आते हैं\n"
    "/watch किसी चीज़ पर, उसकी पुष्ट ख़बर आने पर एक बार सुनने के लिए\n"
    "/watches अपनी वॉच देखना या बंद करना\n/unwatch 1 नंबर से कोई वॉच बंद करना\n"
    "/holdings आपके पास क्या है, आपके भेजे स्क्रीनशॉट से",
    "hinglish": "/brief is mahine ka brief\n/plan apna plan dekhna ya badalna\n"
    "/dashboard ek tap mein aapka apna page\n"
    "/range purane mahinon ko dohraakar, aapka plan kahan tak pahunch sakta hai\n"
    "/pause briefs aur alerts rokna\n/resume unhe phir se chalu karna\n"
    "/stop saare messages band karna\n"
    "/erase aapke baare mein mere paas jo kuch hai, sab mitana\n"
    "/start phir se setup, ya apne jawab dekhna\n"
    "/link email par bhi use karne ke liye code\n"
    "/sendto email ya /sendto telegram, briefs aur alerts kis jagah aate hain\n"
    "/watch kisi cheez par, uski confirmed story aane par ek baar sunne ke liye\n"
    "/watches apni watches dekhna ya band karna\n/unwatch 1 number se koi watch band karna\n"
    "/holdings aapke paas kya hai, aapke bheje screenshot se",
}
UNKNOWN_COMMAND: Final = {
    "en": "I don't know that one yet. /help shows everything I can do.",
    "hi": "यह कमांड मुझे अभी नहीं आती। /help में मेरे सारे काम दिखते हैं।",
    "hinglish": "Yeh command mujhe abhi nahin aati. /help mein mere saare kaam dikhte hain.",
}
FINISH_FIRST: Final = {
    "en": "Let's finish setting up first.",
    "hi": "पहले आपका सेटअप पूरा कर लेते हैं।",
    "hinglish": "Pehle aapka setup poora kar lete hain.",
}
PAUSED: Final = {
    "en": "Paused. No briefs or alerts until you send /resume. You can still ask me anything.",
    "hi": "रोक दिया। जब तक आप /resume नहीं भेजते, ब्रीफ़ और अलर्ट नहीं आएँगे। आप फिर भी मुझसे कुछ भी पूछ सकते हैं।",
    "hinglish": "Rok diya. Jab tak aap /resume nahin bhejte, briefs aur alerts nahin aayenge. Aap "
    "phir bhi mujhse kuch bhi pooch sakte hain.",
}
STOPPED: Final = {
    "en": "Stopped. I won't message you again. /start brings me back any time.",
    "hi": "बंद कर दिया। मैं अब आपको मैसेज नहीं करूँगा। /start से कभी भी वापस आ सकते हैं।",
    "hinglish": "Band kar diya. Main ab aapko message nahin karoonga. /start se kabhi bhi wapas "
    "aa sakte hain.",
}
WELCOME_BACK: Final = {"en": "Welcome back.", "hi": "फिर से स्वागत है।",
                       "hinglish": "Phir se swagat hai."}  # fmt: skip
BACK_ON: Final = {"en": "Back on.", "hi": "फिर से चालू।", "hinglish": "Phir se chalu."}
CHECK_IN: Final = {
    "en": "I'll check in on the {day}.",
    "hi": "मैं {day} तारीख़ को मैसेज करूँगा।",
    "hinglish": "Main {day} tareekh ko message karoonga.",
}
UNAVAILABLE: Final = {
    "en": "That isn't working on my side right now. You can try again in a little while.",
    "hi": "यह अभी मेरी तरफ़ से नहीं चल रहा। थोड़ी देर बाद फिर कोशिश कर सकते हैं।",
    "hinglish": "Yeh abhi meri taraf se nahin chal raha. Thodi der baad phir try kar sakte hain.",
}
LINK_ON_TELEGRAM: Final = {
    "en": "Linking starts on Telegram: send /link there, then email me the code.",
    "hi": "लिंक करना Telegram से शुरू होता है: वहाँ /link भेजने पर कोड मिलेगा, फिर वह कोड मुझे ईमेल कर सकते हैं।",
    "hinglish": "Linking Telegram se shuru hoti hai: wahan /link bhejne par code milega, phir "
    "woh code mujhe email kar sakte hain.",
}
LINK_CODE: Final = {
    "en": "Your code is {code}. Email it to {where} within {minutes} minutes. It works once. "
    "After that, your plan, language and what you left out carry over there too.",
    "hi": "आपका कोड {code} है। इसे {minutes} मिनट के अंदर {where} पर ईमेल कर सकते हैं। यह एक ही "
    "बार चलता है। उसके बाद आपका प्लान, भाषा और जो आपने बाहर रखा, वह वहाँ भी लागू होगा।",
    "hinglish": "Aapka code {code} hai. Ise {minutes} minute ke andar {where} par email kar "
    "sakte hain. Yeh ek hi baar chalta hai. Uske baad aapka plan, language aur jo aapne bahar "
    "rakha, woh wahan bhi lagu hoga.",
}
DESTINATIONS: Final = {"email": Channel.EMAIL, "telegram": Channel.TELEGRAM}
DESTINATION_NAMES: Final = {
    Channel.EMAIL: {"en": "your email", "hi": "आपके ईमेल", "hinglish": "aapke email"},
    Channel.TELEGRAM: {"en": "Telegram", "hi": "Telegram", "hinglish": "Telegram"},
}
SENT_TO: Final = {
    "en": "Done. Briefs and alerts now go to {where}.",
    "hi": "हो गया। अब ब्रीफ़ और अलर्ट {where} पर आएँगे।",
    "hinglish": "Ho gaya. Ab briefs aur alerts {where} par aayenge.",
}
SENDTO_USAGE: Final = {
    "en": "/sendto email or /sendto telegram chooses where briefs and alerts go.",
    "hi": "/sendto email या /sendto telegram से चुन सकते हैं कि ब्रीफ़ और अलर्ट किस जगह आते हैं।",
    "hinglish": "/sendto email ya /sendto telegram se chun sakte hain ki briefs aur alerts kis "
    "jagah aate hain.",
}
UNREACHABLE: Final = {
    Channel.EMAIL: {
        "en": "Your email isn't linked yet: send /link on Telegram, then email me the code.",
        "hi": "आपका ईमेल अभी लिंक नहीं है: Telegram पर /link भेजकर कोड मुझे ईमेल कर सकते हैं।",
        "hinglish": "Aapka email abhi link nahin hai: Telegram par /link bhejkar code mujhe email "
        "kar sakte hain.",
    },
    Channel.TELEGRAM: {
        "en": "You haven't used Networth on Telegram yet, so briefs stay on email.",
        "hi": "आपने अभी Telegram पर Networth इस्तेमाल नहीं किया, इसलिए ब्रीफ़ ईमेल पर ही आएँगे।",
        "hinglish": "Aapne abhi Telegram par Networth use nahin kiya, isliye briefs email par hi "
        "aayenge.",
    },
}
ERASE_PREFIX: Final = "er"
ERASE_ASK: Final = {
    "en": "This deletes everything I have about you: your setup answers, plan, chats, watches, "
    "holdings and any broker link. It can't be undone. /stop only pauses messages and keeps "
    "your setup.",
    "hi": "इससे आपके बारे में मेरे पास जो कुछ है, सब मिट जाएगा: सेटअप के जवाब, प्लान, बातचीत, वॉच, "
    "होल्डिंग्स और कोई भी ब्रोकर लिंक। यह वापस नहीं होगा। /stop सिर्फ़ मैसेज रोकता है और सेटअप रखता है।",
    "hinglish": "Isse aapke baare mein mere paas jo kuch hai, sab mit jayega: setup ke jawab, "
    "plan, chats, watches, holdings aur koi bhi broker link. Yeh wapas nahin hoga. /stop sirf "
    "messages rokta hai aur setup rakhta hai.",
}
ERASE_YES: Final = {"en": "Delete everything", "hi": "सब मिटाना है", "hinglish": "Sab mitana hai"}
ERASE_NO: Final = {"en": "Keep it", "hi": "रहने दें", "hinglish": "Rehne do"}
ERASED: Final = {
    "en": "Done. Everything I had about you is deleted. If you ever want to start again, /start "
    "is here.",
    "hi": "हो गया। आपके बारे में मेरे पास जो कुछ था, सब मिट गया। फिर से शुरू करना हो तो /start है।",
    "hinglish": "Ho gaya. Aapke baare mein mere paas jo kuch tha, sab mit gaya. Phir se shuru "
    "karna ho toh /start hai.",
}
ERASE_KEPT: Final = {
    "en": "Nothing was deleted. Everything stays as it was.",
    "hi": "कुछ नहीं मिटा। सब कुछ पहले जैसा है।",
    "hinglish": "Kuch nahin mita. Sab kuch pehle jaisa hai.",
}
# The BotFather command list, also sent with setMyCommands when the server starts.
COMMAND_LIST: Final = (
    ("brief", "This month's brief"),
    ("plan", "See or change your plan"),
    ("dashboard", "One tap to your own page"),
    ("range", "What your plan could become, replayed over past months"),
    ("holdings", "What you hold, read from a screenshot"),
    ("watch", "Hear once when a confirmed story about something appears"),
    ("watches", "See or stop your watches"),
    ("unwatch", "Stop a watch by its number"),
    ("link", "A code to use Networth by email too"),
    ("sendto", "Where briefs and alerts go: email or telegram"),
    ("pause", "Pause briefs and alerts"),
    ("resume", "Turn briefs and alerts back on"),
    ("stop", "Stop all messages"),
    ("erase", "Delete everything Networth has about you"),
    ("start", "Set up again or see your answers"),
    ("help", "Everything Networth can do"),
)
PRIVATE_ONLY: Final = (
    "I only answer in a private chat. Message me directly and we'll start there.\n"
    "मैं सिर्फ़ प्राइवेट चैट में जवाब देता हूँ। मुझे सीधे मैसेज करने पर वहीं से बात शुरू होगी।"
)
PRIVATE: Final = "private"
IMAGE_MIME: Final = "image/"
PLAN_TITLE: Final = {"en": "Your plan", "hi": "आपका प्लान", "hinglish": "Aapka plan"}
PAGE_NOTE: Final = {
    "en": "Your page has your plan and your latest brief.",
    "hi": "आपके पेज पर आपका प्लान और ताज़ा ब्रीफ़ है।",
    "hinglish": "Aapke page par aapka plan aur latest brief hai.",
}


def help_message(lang: str | None) -> Message:
    return Message(body=(say(HELP_LEAD, lang), say(HELP_ASK, lang), say(HELP_COMMANDS, lang)),
                   footer=say(FOOTER, lang))  # fmt: skip


@dataclass(frozen=True)
class Text:
    chat_id: int
    text: str
    is_forward: bool


@dataclass(frozen=True)
class Tap:
    chat_id: int
    callback_id: str
    data: str
    message_id: int | None


@dataclass(frozen=True)
class Media:
    chat_id: int
    file_id: str | None  # a photo's largest size or an image document; None for the rest


@dataclass(frozen=True)
class NotPrivate:
    """A message or a tap from a group or a channel: answered once, never stored."""

    chat_id: int
    callback_id: str | None


Incoming = Text | Tap | Media | NotPrivate


def _private(message: dict) -> bool:
    """A chat with no type, as in older updates, counts as private."""
    return (message.get("chat") or {}).get("type", PRIVATE) == PRIVATE


def _image_file_id(message: dict) -> str | None:
    """The largest PhotoSize, or a document whose mime_type is an image."""
    photos = message.get("photo")
    largest = photos[-1] if isinstance(photos, list) and photos else {}
    document = message.get("document")
    if not largest and isinstance(document, dict):
        mime = document.get("mime_type")
        largest = document if isinstance(mime, str) and mime.startswith(IMAGE_MIME) else {}
    file_id = largest.get("file_id") if isinstance(largest, dict) else None
    return file_id if isinstance(file_id, str) else None


def parse_update(update: dict) -> Incoming | None:
    """Only new messages and button taps matter; edits, joins and the rest are None."""
    if tap := update.get("callback_query"):
        message = tap.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        if chat_id is None:
            return None
        if not _private(message):
            return NotPrivate(int(chat_id), str(tap["id"]))
        return Tap(int(chat_id), str(tap["id"]), str(tap.get("data") or ""),
                   message.get("message_id"))  # fmt: skip
    message = update.get("message")
    if not message or (message.get("chat") or {}).get("id") is None:
        return None
    chat_id = int(message["chat"]["id"])
    if not _private(message):
        return NotPrivate(chat_id, None)
    if isinstance(message.get("text"), str):
        is_forward = "forward_origin" in message or "forward_date" in message
        return Text(chat_id, message["text"], is_forward)
    return Media(chat_id, _image_file_id(message))


@dataclass(frozen=True)
class Turn:
    """One update's worth of IO: where to save, where to send, the time it arrived, the slow
    work to run once the update lock is released, and what the chat answer used (its intent
    and guard verdict), which a Keiki turn logs."""

    store: Store
    bot: Bot
    now: str
    services: Services
    later: list[Callable[[], None]] = field(default_factory=list)
    trace: dict[str, str] = field(default_factory=dict)

    @property
    def clock(self) -> dt.datetime:
        return dt.datetime.fromisoformat(self.now)

    def answer(self, profile: Profile, make: Callable[[], Reply]) -> None:
        """Queue a slow reply; a failure still tells the user something went wrong. Past the
        hourly cap the user gets a polite note and no paid call runs."""
        cfg = self.services.cfg
        if cfg is not None and not self.store.claim_answer(
            profile.user_id, self.clock, cfg.product.chat_max_per_hour
        ):
            self.send(profile, Reply(say(TOO_MANY, profile.lang)))
            return

        def job() -> None:
            try:
                reply = make()
            except Exception:
                log.exception("chat answer for %s failed", profile.user_id)
                reply = Reply(say(TRY_AGAIN, profile.lang))
            self.send(profile, reply)

        self.later.append(job)

    def send(self, profile: Profile, reply: Reply) -> bool:
        return send(self.store, self.bot, profile, reply)

    def save(self, profile: Profile) -> Profile:
        profile = replace(profile, updated_at=self.now)
        self.store.save_profile(profile)
        return profile

    def plan(self, profile: Profile) -> Plan | None:
        return self.store.get_plan(profile.user_id)

    def commit(self, before: Plan | None, outcome: Outcome) -> Profile:
        if outcome.plan is not None and outcome.plan != before:
            self.store.save_plan(outcome.plan)
        return self.save(outcome.profile)


def profile_for(turn: Turn, chat_id: int) -> Profile:
    existing = turn.store.get_profile(user_id_for(chat_id))
    return existing or turn.save(new_profile(chat_id, turn.now))


# ponytail: one process-wide lock, so two taps never read the same step at once. One container
# serves every user; per-chat locks are the upgrade if throughput ever matters.
HANDLE_LOCK: Final = threading.Lock()


def handle_update(
    update: dict, store: Store, bot: Bot, now: str | None = None,
    services: Services | None = None,
) -> None:  # fmt: skip
    turn = Turn(store, bot, now or now_iso(), services or Services(store.path.parent))
    with HANDLE_LOCK:
        update_id = update.get("update_id")
        if isinstance(update_id, int) and not store.claim_update(update_id):
            return
        dispatch(update, turn)
    for job in turn.later:
        job()


def dispatch(update: dict, turn: Turn) -> None:
    incoming = parse_update(update)
    if incoming is None:
        return
    match incoming:
        case Tap():
            on_tap(turn, incoming)
        case Text():
            on_text(turn, incoming)
        case Media():
            on_media(turn, incoming)
        case NotPrivate():
            on_not_private(turn, incoming)


def on_not_private(turn: Turn, msg: NotPrivate) -> None:
    if msg.callback_id is not None:
        turn.bot.answer_callback(msg.callback_id, PRIVATE_ONLY)
    else:
        turn.bot.send_message(msg.chat_id, Message(body=(PRIVATE_ONLY,)))


def on_text(turn: Turn, msg: Text) -> None:
    profile = profile_for(turn, msg.chat_id)
    turn.store.log_message(profile.user_id, "in", msg.text)
    on_profile_text(turn, profile, msg.text.strip(), msg.is_forward)


def on_profile_text(turn: Turn, profile: Profile, text: str, is_forward: bool) -> None:
    """One typed message from a known profile, on Telegram or inside a Keiki turn."""
    if text.startswith("/"):
        run_command(turn, profile, text)
    elif profile.status is Status.STOPPED:
        return
    elif profile.step is not Step.DONE:
        plan, before = turn.plan(profile), profile.step
        outcome = advance(profile, plan, text, turn.now)
        profile = turn.commit(plan, outcome)
        if outcome.toast and not outcome.replies:
            ask = ask_for(profile, outcome.plan)
            turn.send(profile, with_lead(f"{outcome.toast}.", ask))
        for reply in outcome.replies:
            turn.send(profile, reply)
        finished_setup(turn, before, profile)
    elif (fixed := holdings_flow.typed_fix(turn.store, profile, text)) is not None:
        turn.send(profile, fixed)
    else:
        turn.answer(profile, lambda: chat_reply(turn, profile, text, is_forward))


def chat_reply(turn: Turn, profile: Profile, text: str, is_forward: bool) -> Reply:
    reply, intent, used = chat.respond_traced(turn.store, profile, text, is_forward,
                                              turn.services, turn.clock)  # fmt: skip
    turn.trace.update(intent=intent.value, guard=used)
    return reply


def parse_callback(data: str) -> tuple[str, str] | None:
    parts = data.split(":", 2)
    if len(parts) != 3 or parts[0] != CALLBACK_PREFIX:
        return None
    return parts[1], parts[2]


def on_brief_tap(turn: Turn, profile: Profile, tap: Tap) -> None:
    """Invest as planned only acknowledges: the user invests in their own app."""
    turn.bot.answer_callback(tap.callback_id)
    if tap.data == f"{brief.CALLBACK_PREFIX}:plan":
        cmd_plan(turn, profile, "")
    elif tap.data == f"{brief.CALLBACK_PREFIX}:range":
        cmd_range(turn, profile, "")
    elif tap.data == f"{brief.CALLBACK_PREFIX}:ok":
        turn.send(profile, Reply(say(PLAN_KEPT, profile.lang)))


def on_tap(turn: Turn, tap: Tap) -> None:
    profile = profile_for(turn, tap.chat_id)
    turn.store.log_message(profile.user_id, "in", tap.data)
    if tap.data.startswith(f"{ERASE_PREFIX}:"):
        turn.bot.answer_callback(tap.callback_id)
        if tap.data == f"{ERASE_PREFIX}:yes":
            erase(turn, profile)
        else:
            tell(turn, profile, ERASE_KEPT)
        return
    if profile.status is not Status.STOPPED and tap.data.startswith(watches.STOP_PREFIX):
        turn.bot.answer_callback(tap.callback_id)
        turn.send(profile, Reply(watches.stop_tapped(turn.store, profile, tap.data)))
        return
    if profile.status is not Status.STOPPED and tap.data.startswith(f"{brief.CALLBACK_PREFIX}:"):
        on_brief_tap(turn, profile, tap)
        return
    if profile.status is not Status.STOPPED and tap.data.startswith(f"{holdings_flow.TAP_PREFIX}:"):
        turn.bot.answer_callback(tap.callback_id)
        later(turn, profile, "holdings tap", lambda: holdings_flow.tapped(
            turn.store, profile, tap.data, turn.services, turn.clock))  # fmt: skip
        return
    parsed = parse_callback(tap.data)
    if profile.status is Status.STOPPED or parsed is None:
        turn.bot.answer_callback(tap.callback_id)
        return
    step, value = parsed
    plan = turn.plan(profile)
    if step != profile.step:
        turn.bot.answer_callback(tap.callback_id, say(STALE_TAP, profile.lang))
        if profile.step is not Step.DONE:
            turn.send(profile, ask_for(profile, plan))
        return
    before = profile.step
    outcome = advance(profile, plan, value, turn.now)
    profile = turn.commit(plan, outcome)
    turn.bot.answer_callback(tap.callback_id, outcome.toast)
    if outcome.edit_buttons is not None and tap.message_id is not None:
        turn.bot.edit_buttons(tap.chat_id, tap.message_id, outcome.edit_buttons)
    for reply in outcome.replies:
        turn.send(profile, reply)
    finished_setup(turn, before, profile)


def on_media(turn: Turn, media: Media) -> None:
    profile = turn.store.get_profile(user_id_for(media.chat_id))
    if profile is None or profile.step is not Step.DONE or profile.status is Status.STOPPED:
        return
    if media.file_id is None:
        turn.send(profile, Reply(say(NOT_A_PHOTO, profile.lang)))
        return
    file_id = media.file_id
    turn.answer(profile, lambda: holdings_flow.photo_reply(
        turn.store, profile, turn.bot.download_file(file_id), turn.services))  # fmt: skip


def later(turn: Turn, profile: Profile, what: str, make: Callable[[], Reply]) -> None:
    """Network work after the update lock, with no hourly claim; a failure says try again."""

    def job() -> None:
        try:
            reply = make()
        except Exception as exc:  # noqa: BLE001 - the user still hears something went wrong
            log.warning("%s for %s failed: %s", what, profile.user_id, type(exc).__name__)
            reply = Reply(say(TRY_AGAIN, profile.lang))
        turn.send(profile, reply)

    turn.later.append(job)


def set_menu(turn: Turn, profile: Profile, on: bool = True) -> None:
    """The chat's menu button: a web app opening the user's signed page, or Telegram's default.
    Only an HTTPS page can open as a web app. A failure is logged by method only and never
    holds up a reply."""
    if not isinstance(turn.bot, MenuBot) or profile.chat_id == 0:
        return
    url = turn.services.page_url(profile.link_token, turn.clock) if on else None
    if on and not (url and url.startswith("https://")):
        return
    try:
        turn.bot.set_chat_menu_button(profile.chat_id, say(brief.BUTTONS["page"], profile.lang),
                                      url)  # fmt: skip
    except TelegramError as exc:
        log.warning("telegram %s: %s", exc.method, exc.description)
    except Exception as exc:  # noqa: BLE001 - the menu is a convenience, the reply still goes
        log.warning("menu button for %s failed: %s", profile.user_id, type(exc).__name__)


def finished_setup(turn: Turn, before: Step, profile: Profile) -> None:
    if before is not Step.DONE and profile.step is Step.DONE:
        set_menu(turn, profile)


# --- commands ------------------------------------------------------------------------------


def cmd_start(turn: Turn, profile: Profile, args: str) -> None:
    returning = profile.status is Status.STOPPED
    was_done = profile.step is Step.DONE
    profile = replace(profile, status=Status.ACTIVE) if returning else profile
    if was_done:
        profile = replace(profile, step=Step.CONFIRM)
    profile = turn.save(profile)
    ask = ask_for(profile, turn.plan(profile))
    if returning and was_done:
        ask = with_lead(say(WELCOME_BACK, profile.lang), ask)
    turn.send(profile, ask)


def cmd_plan(turn: Turn, profile: Profile, args: str) -> None:
    plan = turn.plan(profile)
    if profile.step is not Step.DONE or plan is None:
        ask = ask_for(profile, plan)
        turn.send(profile, with_lead(say(FINISH_FIRST, profile.lang), ask))
        return
    profile = turn.save(replace(profile, step=Step.PLAN))
    page = turn.services.page_url(profile.link_token, turn.clock)
    lang = profile.lang
    mine = (say(PAGE_NOTE, lang), Link(say(YOUR_PAGE, lang), page)) if page else ()
    turn.send(profile, Reply(Message(say(PLAN_TITLE, lang), (f"{plan_line(plan, lang)}.", *mine),
                                     footer=say(FOOTER, lang))))  # fmt: skip
    turn.send(profile, ask_for(profile, plan))


def cmd_pause(turn: Turn, profile: Profile, args: str) -> None:
    profile = turn.save(replace(profile, status=Status.PAUSED))
    turn.send(profile, Reply(say(PAUSED, profile.lang)))


def cmd_resume(turn: Turn, profile: Profile, args: str) -> None:
    profile = turn.save(replace(profile, status=Status.ACTIVE))
    lang = profile.lang
    day = day_label(profile.invest_day or 1, lang)
    check_in = f" {say(CHECK_IN, lang).format(day=day)}" if profile.invest_day else ""
    turn.send(profile, Reply(f"{say(BACK_ON, lang)}{check_in}"))


def cmd_stop(turn: Turn, profile: Profile, args: str) -> None:
    """Forgets the broker link at SnapTrade and retires the page link before the stopped save,
    which deletes the holdings. A failed SnapTrade delete never stops the stop."""
    turn.send(profile, Reply(say(STOPPED, profile.lang)))
    try:
        snaptrade.forget_snaptrade(profile.user_id, turn.store, client=turn.services.snaptrade)
    except Exception as exc:  # noqa: BLE001 - the row stays for a later retry
        log.warning("snaptrade forget for %s failed: %s", profile.user_id, type(exc).__name__)
    turn.store.new_link_token(profile.user_id)
    turn.save(replace(profile, status=Status.STOPPED))
    set_menu(turn, profile, on=False)


def tell(turn: Turn, profile: Profile, words: dict[str, str], buttons: Keyboard = ()) -> None:
    """Straight to the bot, not through outbox.send: a stopped user may still erase, and
    nothing about the exchange is logged to a user who is being forgotten."""
    turn.bot.send_message(profile.chat_id, Message(body=(say(words, profile.lang),)), buttons)


def erase(turn: Turn, profile: Profile) -> None:
    """The broker link at SnapTrade first: if that fails nothing is deleted, so the remote
    user is never orphaned. Then the menu, then every row."""
    try:
        snaptrade.forget_snaptrade(profile.user_id, turn.store, client=turn.services.snaptrade)
    except Exception as exc:  # noqa: BLE001 - nothing is deleted, the user can try again
        log.warning("snaptrade forget for %s failed: %s", profile.user_id, type(exc).__name__)
        tell(turn, profile, TRY_AGAIN)
        return
    set_menu(turn, profile, on=False)
    turn.store.erase_user(profile.user_id)
    tell(turn, profile, ERASED)


def cmd_erase(turn: Turn, profile: Profile, args: str) -> None:
    """A confirm button on Telegram; "/erase yes" is the typed confirm, as email has no
    buttons."""
    if args.strip().lower() in ("yes", "confirm"):
        erase(turn, profile)
        return
    lang = profile.lang
    buttons = ((Button(say(ERASE_YES, lang), f"{ERASE_PREFIX}:yes"),
                Button(say(ERASE_NO, lang), f"{ERASE_PREFIX}:no")),)  # fmt: skip
    tell(turn, profile, ERASE_ASK, buttons)


def cmd_dashboard(turn: Turn, profile: Profile, args: str) -> None:
    """One button to the user's own page, and the chat menu set to open it too."""
    if profile.step is not Step.DONE:
        turn.send(profile, Reply(say(FINISH_FIRST, profile.lang)))
        return
    lang = profile.lang or "en"
    turn.send(profile, deliver(dashboard.dashboard(profile, turn.services, turn.clock, lang), lang,
                               turn.services))  # fmt: skip
    set_menu(turn, profile)


def cmd_brief(turn: Turn, profile: Profile, args: str) -> None:
    local = briefs.local_now(profile, turn.clock)

    def job() -> None:
        try:
            briefs.send_brief(turn.store, turn.bot, profile, turn.services, local)
        except Exception:
            log.exception("brief for %s failed", profile.user_id)
            turn.send(profile, Reply(say(TRY_AGAIN, profile.lang)))

    turn.later.append(job)


def cmd_range(turn: Turn, profile: Profile, args: str) -> None:
    """Fixed sentences, so no model and no hourly claim; the replay runs after the lock."""
    if profile.step is not Step.DONE:
        turn.send(profile, Reply(say(FINISH_FIRST, profile.lang)))
        return

    def job() -> None:
        try:
            answer = chat.today.plan_range(turn.store, profile, profile.lang or "en")
            reply = deliver(answer, profile.lang or "en", turn.services)
        except Exception:
            log.exception("range for %s failed", profile.user_id)
            reply = Reply(say(TRY_AGAIN, profile.lang))
        turn.send(profile, reply)

    turn.later.append(job)


def cmd_holdings(turn: Turn, profile: Profile, args: str) -> None:
    if profile.step is not Step.DONE:
        turn.send(profile, Reply(say(FINISH_FIRST, profile.lang)))
        return
    later(turn, profile, "holdings", lambda: holdings_flow.report_reply(
        turn.store, profile, turn.services, turn.clock))  # fmt: skip


def cmd_link_broker(turn: Turn, profile: Profile, args: str) -> None:
    if profile.step is not Step.DONE:
        turn.send(profile, Reply(say(FINISH_FIRST, profile.lang)))
        return
    later(turn, profile, "link_broker", lambda: holdings_flow.link_broker_reply(
        turn.store, profile, turn.services))  # fmt: skip


def cmd_help(turn: Turn, profile: Profile, args: str) -> None:
    turn.send(profile, Reply(help_message(profile.lang)))


def cmd_unknown(turn: Turn, profile: Profile, args: str) -> None:
    turn.send(profile, Reply(say(UNKNOWN_COMMAND, profile.lang)))


def cmd_link(turn: Turn, profile: Profile, args: str) -> None:
    """A single-use code that ties the user's email to this Telegram profile."""
    cfg = turn.services.cfg
    lang = profile.lang
    if profile.step is not Step.DONE:
        turn.send(profile, Reply(say(FINISH_FIRST, lang)))
    elif profile.channel == Channel.EMAIL:
        turn.send(profile, Reply(say(LINK_ON_TELEGRAM, lang)))
    elif cfg is None:
        turn.send(profile, Reply(say(UNAVAILABLE, lang)))
    else:
        minutes = cfg.product.link_code_minutes
        code = turn.store.new_link_code(profile.user_id, turn.clock, dt.timedelta(minutes=minutes))
        where = turn.services.keiki_email or "Networth's email"
        turn.send(profile, Reply(say(LINK_CODE, lang).format(code=code, where=where,
                                                            minutes=minutes)))  # fmt: skip


def reachable(turn: Turn, profile: Profile, channel: Channel) -> bool:
    if channel is Channel.EMAIL:
        return turn.store.contact_for(profile.user_id) is not None
    return profile.chat_id != 0


def cmd_sendto(turn: Turn, profile: Profile, args: str) -> None:
    channel = DESTINATIONS.get(args.strip().lower())
    if channel is None:
        turn.send(profile, Reply(say(SENDTO_USAGE, profile.lang)))
    elif not reachable(turn, profile, channel):
        turn.send(profile, Reply(say(UNREACHABLE[channel], profile.lang)))
    else:
        profile = turn.save(replace(profile, deliver_to=channel))
        where = say(DESTINATION_NAMES[channel], profile.lang)
        turn.send(profile, Reply(say(SENT_TO, profile.lang).format(where=where)))


def cmd_watch(turn: Turn, profile: Profile, args: str) -> None:
    if profile.step is not Step.DONE:
        turn.send(profile, Reply(say(FINISH_FIRST, profile.lang)))
        return
    rules = turn.services.cfg.product if turn.services.cfg else None
    turn.send(profile, Reply(watches.set_watch(turn.store, profile, args, turn.now, rules)))


def cmd_watches(turn: Turn, profile: Profile, args: str) -> None:
    turn.send(profile, watches.list_reply(turn.store, profile))


def cmd_unwatch(turn: Turn, profile: Profile, args: str) -> None:
    turn.send(profile, Reply(watches.stop_nth(turn.store, profile, args)))


COMMANDS: Final[dict[str, Callable[[Turn, Profile, str], None]]] = {
    "/start": cmd_start,
    "/brief": cmd_brief,
    "/plan": cmd_plan,
    "/dashboard": cmd_dashboard,
    "/range": cmd_range,
    "/pause": cmd_pause,
    "/resume": cmd_resume,
    "/stop": cmd_stop,
    "/erase": cmd_erase,
    "/help": cmd_help,
    "/link": cmd_link,
    "/sendto": cmd_sendto,
    "/watch": cmd_watch,
    "/watches": cmd_watches,
    "/unwatch": cmd_unwatch,
    "/holdings": cmd_holdings,
    "/link_broker": cmd_link_broker,
}


def command_name(text: str) -> str:
    """'/start@networth_professor_bot payload' -> '/start'."""
    return text.split(maxsplit=1)[0].split("@", 1)[0].lower()


def run_command(turn: Turn, profile: Profile, text: str) -> None:
    name = command_name(text)
    if profile.status is Status.STOPPED and name not in ("/start", "/erase"):
        return
    parts = text.split(maxsplit=1)
    COMMANDS.get(name, cmd_unknown)(turn, profile, parts[1] if len(parts) > 1 else "")
