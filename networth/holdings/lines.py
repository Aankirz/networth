"""The holdings report as fixed sentences in English, Hindi and Hinglish.

    lines = holdings_lines(report, "hi")       # every number is a HoldingsReport field
    about = explain_lines(report, 3, "en")     # one holding, in plain words

Only report fields fill the gaps, so guard.check(line, repr(report)) passes for every line.
The mix next to the plan is stated as two facts, never as a gap to close. Hindi keeps ASCII
digits. Rupees use Indian grouping (sim.rupees), dollars US grouping, whole units.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Final

from networth.holdings.model import BUCKETS, PriceFrom
from networth.holdings.report import History, HoldingsReport, NoHistory, Row
from networth.holdings.returns import Return
from networth.sim import Lang, rupees
from networth.web.fmt import MINUS, indian_grouping, western_grouping

HINDI_MONTHS: Final = "जनवरी फ़रवरी मार्च अप्रैल मई जून जुलाई अगस्त सितंबर अक्टूबर नवंबर दिसंबर".split()

LINES: Final[Mapping[str, Mapping[str, str]]] = {
    "en": {
        "head": "What you hold, valued on {date}: {count} holdings.",
        "row": "{n}. {name} ({bucket}): {units} units at an average cost of {avg_cost}. Put in "
        "{invested}, worth {value} now, {gain} ({ret}). Price {price}.",
        "total": "In total: put in {invested}, worth {value} now, {gain} ({ret}).",
        "mix_head": "Your mix by value now, next to the plan you saved:",
        "mix": "Your plan says {plan}% {bucket}. Your holdings are {held}% {bucket}.",
        "hit": "In {held_hit}% of paths a mix like your holdings fell {fall}% or more at some "
        "point. Your saved plan: {plan_hit}%.",
        "fall": "The typical worst fall: {held_fall}% for a mix like your holdings, "
        "{plan_fall}% for your saved plan.",
        "median": "The middle case after {years} years of {amount} a month: {held_median} for "
        "a mix like your holdings, {plan_median} for your saved plan. Money put in: {invested}.",
        "method": "Both replay real past months from {start} to {end}, {paths} times, using "
        "index prices, not your funds' own.",
        "not_rupees": "What history says about a mix like this is in rupees only for now.",
        "no_amount": "What history says needs your monthly amount and time; /start in the bot "
        "adds them.",
        "no_table": "What history says is not ready on this server yet.",
        "looked_up": "Prices looked up on {date}: {looked_up} of {count} holdings.",
        "from_source": "Prices from your {source}: {from_source} of {count} holdings.",
        "unpriced": "No current price: {unpriced} of {count} holdings, valued at what they cost.",
        "label": "This is what you hold and what history says about a mix like it. It is not "
        "advice. What you do is your choice. Research, not advice.",
        "decline": "I don't rate holdings or say what to do with them. Here is what you hold "
        "and what history says about a mix like it.",
        "no_report": "Send a screenshot of your holdings in the bot, then confirm it.",
        "xirr": "{pct}% a year, XIRR",
        "simple": "{pct}% in total, a simple return as no start date was shown",
        "short": "{pct}% so far, held under a year, so not a yearly rate",
        "price_looked_up": "looked up on {date}",
        "price_screenshot": "from your screenshot",
        "price_broker": "from your broker",
        "price_none": "not shown, so it is valued at what it cost",
        "screenshot": "screenshot",
        "snaptrade": "broker",
        "safety": "safe money (liquid, gilt, FD)",
        "core": "broad index funds",
        "growth": "single shares or themes",
        "about_safety": "Safe money is meant to stay steady: fixed deposits, liquid, gilt and debt "
        "funds, and gold.",
        "about_core": "Broad index funds hold the whole market: index funds and ETFs with many "
        "large companies.",
        "about_growth": "Single shares or themes rise and fall more: single company shares, mid "
        "and small cap funds and sector funds.",
    },
    "hi": {
        "head": "आपके पास क्या है, {date} की कीमत पर: {count} होल्डिंग्स।",
        "row": "{n}. {name} ({bucket}): {units} यूनिट, औसत लागत {avg_cost}। लगाया {invested}, "
        "अभी कीमत {value}, {gain} ({ret})। कीमत {price}।",
        "total": "कुल मिलाकर: लगाया {invested}, अभी कीमत {value}, {gain} ({ret})।",
        "mix_head": "अभी की कीमत के हिसाब से आपका मिश्रण, आपके सेव किए प्लान के साथ:",
        "mix": "आपका प्लान कहता है {plan}% {bucket}। आपकी होल्डिंग्स {held}% {bucket} हैं।",
        "hit": "{held_hit}% रास्तों में आपकी होल्डिंग्स जैसा मिश्रण कभी न कभी {fall}% या उससे "
        "ज़्यादा गिरा। आपका सेव किया प्लान: {plan_hit}%।",
        "fall": "आम तौर पर सबसे बड़ी गिरावट: आपकी होल्डिंग्स जैसे मिश्रण के लिए {held_fall}%, "
        "आपके सेव किए प्लान के लिए {plan_fall}%।",
        "median": "हर महीने {amount}, {years} साल बाद बीच वाला हाल: आपकी होल्डिंग्स जैसे मिश्रण के "
        "लिए {held_median}, आपके सेव किए प्लान के लिए {plan_median}। लगाया गया कुल पैसा: "
        "{invested}।",
        "method": "दोनों में {start} से {end} तक के असली पुराने महीने {paths} बार दोहराए गए हैं, "
        "इंडेक्स की कीमतों से, आपके फ़ंड की अपनी कीमतों से नहीं।",
        "not_rupees": "ऐसे मिश्रण के बारे में इतिहास अभी सिर्फ़ रुपयों में है।",
        "no_amount": "इतिहास के लिए आपकी मासिक रकम और समय अभी नहीं है; बॉट में /start से ये जुड़ जाते हैं।",
        "no_table": "इतिहास अभी इस सर्वर पर तैयार नहीं है।",
        "looked_up": "{date} को देखी गई कीमतें: {count} में से {looked_up} होल्डिंग्स।",
        "from_source": "आपके {source} से ली गई कीमतें: {count} में से {from_source} होल्डिंग्स।",
        "unpriced": "अभी की कीमत नहीं: {count} में से {unpriced} होल्डिंग्स, लागत पर गिनी गईं।",
        "label": "यह वह है जो आपके पास है, और इतिहास ऐसे मिश्रण के बारे में क्या कहता है। यह सलाह "
        "नहीं है। आप क्या करते हैं, यह आपकी पसंद है। रिसर्च, सलाह नहीं।",
        "decline": "मैं होल्डिंग्स को रेट नहीं करता, न यह बताता हूँ कि इनका क्या करना है। यह रहा "
        "कि आपके पास क्या है और इतिहास ऐसे मिश्रण के बारे में क्या कहता है।",
        "no_report": "बॉट में आपकी होल्डिंग्स का स्क्रीनशॉट आने और आपके कन्फ़र्म करने के बाद यह "
        "रिपोर्ट यहाँ दिखेगी।",
        "xirr": "{pct}% सालाना, XIRR",
        "simple": "कुल {pct}%, सीधा रिटर्न, क्योंकि निवेश की तारीख नहीं दिखी",
        "short": "अब तक {pct}%, एक साल से कम समय, इसलिए सालाना दर नहीं",
        "price_looked_up": "{date} को देखी गई",
        "price_screenshot": "आपके स्क्रीनशॉट से",
        "price_broker": "आपके ब्रोकर से",
        "price_none": "नहीं दिखी, इसलिए लागत पर गिना गया",
        "screenshot": "स्क्रीनशॉट",
        "snaptrade": "ब्रोकर",
        "safety": "सुरक्षित पैसा (लिक्विड, गिल्ट, FD)",
        "core": "ब्रॉड इंडेक्स फ़ंड",
        "growth": "अलग शेयर या थीम",
        "about_safety": "सुरक्षित पैसा स्थिर रहने के लिए है: एफ़डी, लिक्विड, गिल्ट और डेट फ़ंड, और सोना।",
        "about_core": "ब्रॉड इंडेक्स फ़ंड पूरे बाज़ार वाला पैसा है: इंडेक्स फ़ंड और ईटीएफ़, जिनमें "
        "कई बड़ी कंपनियाँ होती हैं।",
        "about_growth": "अलग शेयर या थीम वाला पैसा ज़्यादा ऊपर नीचे होता है: अलग अलग शेयर, मिड और "
        "स्मॉल कैप फ़ंड, और सेक्टर फ़ंड।",
    },
    "hinglish": {
        "head": "Aapke paas kya hai, {date} ki keemat par: {count} holdings.",
        "row": "{n}. {name} ({bucket}): {units} units, average cost {avg_cost}. Lagaya "
        "{invested}, abhi keemat {value}, {gain} ({ret}). Keemat {price}.",
        "total": "Kul milakar: lagaya {invested}, abhi keemat {value}, {gain} ({ret}).",
        "mix_head": "Abhi ki keemat ke hisaab se aapka mix, aapke save kiye plan ke saath:",
        "mix": "Aapka plan kehta hai {plan}% {bucket}. Aapki holdings {held}% {bucket} hain.",
        "hit": "{held_hit}% raaston mein aapki holdings jaisa mix kabhi na kabhi {fall}% ya "
        "usse zyada gira. Aapka save kiya plan: {plan_hit}%.",
        "fall": "Aam taur par sabse badi giravat: aapki holdings jaise mix ke liye "
        "{held_fall}%, aapke save kiye plan ke liye {plan_fall}%.",
        "median": "Har mahine {amount}, {years} saal baad beech wala haal: aapki holdings "
        "jaise mix ke liye {held_median}, aapke save kiye plan ke liye {plan_median}. Lagaya "
        "gaya kul paisa: {invested}.",
        "method": "Dono mein {start} se {end} tak ke asli purane mahine {paths} baar dohraaye "
        "gaye hain, index ki keemat se, aapke fund ki apni keemat se nahin.",
        "not_rupees": "Aise mix ke baare mein itihaas abhi sirf rupayon mein hai.",
        "no_amount": "Itihaas ke liye aapki monthly rakam aur samay abhi nahin hai; bot mein "
        "/start se yeh jud jaate hain.",
        "no_table": "Itihaas abhi is server par taiyaar nahin hai.",
        "looked_up": "{date} ko dekhi gayi keemat: {count} mein se {looked_up} holdings.",
        "from_source": "Aapke {source} se li gayi keemat: {count} mein se {from_source} holdings.",
        "unpriced": "Abhi ki keemat nahin: {count} mein se {unpriced} holdings, cost par gini "
        "gayi.",
        "label": "Yeh wahi hai jo aapke paas hai, aur itihaas aise mix ke baare mein kya kehta "
        "hai. Yeh advice nahin hai. Aap kya karte hain, yeh aapki pasand hai. Research, advice "
        "nahin.",
        "decline": "Main holdings ko rate nahin karta, na yeh batata hoon ki inka kya karna hai. "
        "Yeh raha aapke paas kya hai aur itihaas aise mix ke baare mein kya kehta hai.",
        "no_report": "Bot mein aapki holdings ka screenshot aane aur aapke confirm karne ke baad "
        "yeh report yahan dikhegi.",
        "xirr": "{pct}% saalana, XIRR",
        "simple": "kul {pct}%, seedha return, kyunki nivesh ki tareekh nahin dikhi",
        "short": "ab tak {pct}%, ek saal se kam samay, isliye saalana dar nahin",
        "price_looked_up": "{date} ko dekhi gayi",
        "price_screenshot": "aapke screenshot se",
        "price_broker": "aapke broker se",
        "price_none": "nahin dikhi, isliye cost par gina gaya",
        "screenshot": "screenshot",
        "snaptrade": "broker",
        "safety": "safe paisa (liquid, gilt, FD)",
        "core": "broad index funds",
        "growth": "alag shares ya theme",
        "about_safety": "Safe paisa sthir rehne ke liye hai: FD, liquid, gilt aur debt fund, aur "
        "sona.",
        "about_core": "Broad index funds poore bazaar wala paisa hai: index fund aur ETF, jinmein "
        "kai badi companies hoti hain.",
        "about_growth": "Alag shares ya theme wala paisa zyada upar neeche hota hai: alag alag "
        "shares, mid aur small cap fund, aur sector fund.",
    },
}
PRICE_KEYS: Final = {
    PriceFrom.LOOKED_UP: "price_looked_up", PriceFrom.SCREENSHOT: "price_screenshot",
    PriceFrom.BROKER: "price_broker", PriceFrom.NONE: "price_none",
}  # fmt: skip


def lang_of(*choices: str | None) -> Lang:
    """The first choice we have sentences for, else English."""
    return next((c for c in choices if c in LINES), "en")  # type: ignore[return-value]


def money(n: int, currency: str) -> str:
    """₹1,50,000 or $12,345, whole units; a minus sign for a loss."""
    body = rupees(abs(n)) if currency == "INR" else f"${western_grouping(abs(n))}"
    return f"{MINUS}{body}" if n < 0 else body


def gain(n: int, currency: str) -> str:
    return f"+{money(n, currency)}" if n > 0 else money(n, currency)


def unit_money(x: float, currency: str) -> str:
    """A per-unit amount to the paisa or cent: ₹1,28,450.50 or $1,234.50."""
    whole, cents = divmod(round(x * 100), 100)
    grouped = indian_grouping(whole) if currency == "INR" else western_grouping(whole)
    symbol = "₹" if currency == "INR" else "$"
    return f"{symbol}{grouped}.{cents:02d}"


def units(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".")


def signed_pct(pct: float) -> str:
    text = f"{abs(pct):.1f}"
    return f"{MINUS}{text}" if pct < 0 else f"+{text}" if pct > 0 else text


def day(d: dt.date, lang: Lang) -> str:
    month = HINDI_MONTHS[d.month - 1] if lang == "hi" else f"{d:%B}"
    return f"{d.day} {month} {d.year}"


def return_text(ret: Return, lang: Lang) -> str:
    return LINES[lang][ret.kind].format(pct=signed_pct(ret.pct))


def price_text(price_from: PriceFrom, as_of: dt.date, lang: Lang) -> str:
    return LINES[lang][PRICE_KEYS[price_from]].format(date=day(as_of, lang))


def _row(r: Row, report: HoldingsReport, lang: Lang) -> str:
    t, c = LINES[lang], report.currency
    return t["row"].format(
        n=r.n, name=r.name, bucket=t[r.bucket.value], units=units(r.units),
        avg_cost=unit_money(r.avg_cost, c), invested=money(r.invested, c),
        value=money(r.value, c), gain=gain(r.gain, c),
        ret=return_text(r.ret, lang), price=price_text(r.price_from, report.as_of, lang),
    )  # fmt: skip


def history_lines(h: History | NoHistory, lang: Lang) -> list[str]:
    t = LINES[lang]
    if isinstance(h, NoHistory):
        return [t[h.value]]
    return [
        t["hit"].format(held_hit=h.held.hit_limit_pct, fall=h.fall_pct,
                        plan_hit=h.plan.hit_limit_pct),
        t["fall"].format(held_fall=h.held.worst_fall_pct, plan_fall=h.plan.worst_fall_pct),
        t["median"].format(years=h.years, amount=rupees(h.monthly_amount),
                           held_median=rupees(h.held.nominal_median),
                           plan_median=rupees(h.plan.nominal_median),
                           invested=rupees(h.invested)),
        t["method"].format(start=h.window_start, end=h.window_end,
                           paths=indian_grouping(h.paths)),
    ]  # fmt: skip


def price_lines(r: HoldingsReport, lang: Lang) -> list[str]:
    t = LINES[lang]
    source = t[r.source.value]
    counts = {"looked_up": r.looked_up, "from_source": r.from_source, "unpriced": r.unpriced}
    return [t[k].format(date=day(r.as_of, lang), count=r.count, source=source, **counts)
            for k, n in counts.items() if n]  # fmt: skip


def mix_lines(report: HoldingsReport, lang: Lang) -> list[str]:
    """The plan and the holdings side by side, as two facts per bucket."""
    t = LINES[lang]
    return [t["mix"].format(plan=p, held=h, bucket=t[b.value])
            for b, p, h in zip(BUCKETS, report.plan_pct, report.held_pct, strict=True)]  # fmt: skip


def holdings_lines(report: HoldingsReport, lang: Lang) -> list[str]:
    t, c = LINES[lang], report.currency
    total = t["total"].format(
        invested=money(report.invested, c), value=money(report.value, c),
        gain=gain(report.gain, c), ret=return_text(report.ret, lang),
    )  # fmt: skip
    return [
        t["head"].format(date=day(report.as_of, lang), count=report.count),
        *(_row(r, report, lang) for r in report.rows),
        total, t["mix_head"], *mix_lines(report, lang), *history_lines(report.history, lang),
        *price_lines(report, lang), t["label"],
    ]  # fmt: skip


def explain_lines(report: HoldingsReport, n: int, lang: Lang) -> list[str] | None:
    """One holding: what its bucket means, then its own line. None for a line not in the list."""
    row = next((r for r in report.rows if r.n == n), None)
    if row is None:
        return None
    t = LINES[lang]
    return [t[f"about_{row.bucket.value}"], _row(row, report, lang), t["label"]]
