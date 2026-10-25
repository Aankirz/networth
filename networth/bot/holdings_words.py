"""The holdings replies' fixed words in English, Hindi and Hinglish.

Plain words only: a bucket is "single shares or themes", "broad index funds" or "safe money",
never its internal name, and a fix is said in words ("15 shares"), never a syntax to learn.
"""

from __future__ import annotations

from typing import Final

from networth.holdings.model import Bucket

GOT_IT: Final = {
    "en": "Got it. {count} holdings, worth {value} today.",
    "hi": "मिल गया। {count} होल्डिंग्स, आज की कीमत {value}।",
    "hinglish": "Mil gaya. {count} holdings, aaj ki keemat {value}.",
}
GOT_ONE: Final = {
    "en": "Got it. 1 holding, worth {value} today.",
    "hi": "मिल गया। 1 होल्डिंग, आज की कीमत {value}।",
    "hinglish": "Mil gaya. 1 holding, aaj ki keemat {value}.",
}
ADDED: Final = {
    "en": "This screenshot added {added}. Already on the list, so updated: {same}.",
    "hi": "इस स्क्रीनशॉट से {added} जुड़ीं। {same} पहले से लिस्ट में थीं, उन्हें अपडेट कर दिया।",
    "hinglish": "Is screenshot se {added} judi. {same} pehle se list mein thi, unhe update kar "
    "diya.",
}
DOWN: Final = {
    "en": "You put in {invested}, so you're down {gain} ({pct}%).",
    "hi": "आपने {invested} लगाए थे, यानी अभी {gain} ({pct}%) कम है।",
    "hinglish": "Aapne {invested} lagaye the, yaani abhi {gain} ({pct}%) kam hai.",
}
UP: Final = {
    "en": "You put in {invested}, so you're up {gain} ({pct}%).",
    "hi": "आपने {invested} लगाए थे, यानी अभी {gain} ({pct}%) ज़्यादा है।",
    "hinglish": "Aapne {invested} lagaye the, yaani abhi {gain} ({pct}%) zyada hai.",
}
EVEN: Final = {
    "en": "You put in {invested}, about what it's worth today.",
    "hi": "आपने {invested} लगाए थे, आज भी कीमत लगभग उतनी ही है।",
    "hinglish": "Aapne {invested} lagaye the, aaj bhi keemat lagbhag utni hi hai.",
}
PUT_IN: Final = {
    "en": "You put in {invested} across all of them.",
    "hi": "इन सब में आपने कुल {invested} लगाए थे।",
    "hinglish": "In sab mein aapne kul {invested} lagaye the.",
}
NO_PRICE: Final = {
    "en": "The screenshot shows no price for {names}, so today's total leaves them out.",
    "hi": "स्क्रीनशॉट में {names} की कीमत नहीं दिखी, इसलिए आज के कुल में वे शामिल नहीं हैं।",
    "hinglish": "Screenshot mein {names} ki keemat nahin dikhi, isliye aaj ke total mein woh "
    "shaamil nahin hain.",
}
ROW_FIRST: Final = {
    "en": "{name}: {value}, {share} of this",
    "hi": "{name}: {value}, इसका {share}",
    "hinglish": "{name}: {value}, iska {share}",
}
ROW: Final = {"en": "{name}: {value}, {share}", "hi": "{name}: {value}, {share}",
              "hinglish": "{name}: {value}, {share}"}  # fmt: skip
UNDER_ONE: Final = {"en": "under 1%", "hi": "1% से कम", "hinglish": "1% se kam"}
ROW_NO_PRICE: Final = {
    "en": "{name}: price not shown",
    "hi": "{name}: कीमत नहीं दिखी",
    "hinglish": "{name}: keemat nahin dikhi",
}
ALL_SHARES: Final = {
    "en": "All {count} are single company shares.",
    "hi": "सभी {count} अलग अलग कंपनियों के शेयर हैं।",
    "hinglish": "Sabhi {count} alag alag companies ke shares hain.",
}
ONE_SHARE: Final = {
    "en": "It's a single company's shares.",
    "hi": "यह एक कंपनी के शेयर हैं।",
    "hinglish": "Yeh ek company ke shares hain.",
}
SOME_SHARES: Final = {
    "en": "{shares} of the {count} are single company shares.",
    "hi": "{count} में से {shares} अलग अलग कंपनियों के शेयर हैं।",
    "hinglish": "{count} mein se {shares} alag alag companies ke shares hain.",
}
TOP: Final = {
    "en": "{name} alone is {share}% of this money.",
    "hi": "अकेले {name} इस पैसे का {share}% है।",
    "hinglish": "Akele {name} is paise ka {share}% hai.",
}
EVERYTHING: Final = {
    "en": "Is this everything? If your app shows more, send the next screenshot and I'll add it.",
    "hi": "क्या यही सब है? अगर आपके ऐप में और हैं, तो अगला स्क्रीनशॉट भेजने पर मैं उसे जोड़ दूँगा।",
    "hinglish": "Kya yahi sab hai? Agar aapke app mein aur hain, toh agla screenshot bhejne par "
    "main use jod doonga.",
}
SEE_OF: Final = {
    "en": "I can see {count} of your {listed}. Scroll in your app and send the rest.",
    "hi": "मुझे आपकी {listed} में से {count} दिख रही हैं। ऐप में नीचे स्क्रोल करके बाकी भेजी जा सकती हैं।",
    "hinglish": "Mujhe aapki {listed} mein se {count} dikh rahi hain. App mein neeche scroll "
    "karke baaki bheji ja sakti hain.",
}
SEE_CUT: Final = {
    "en": "I can see {count} here, and the list goes on. Scroll in your app and send the rest.",
    "hi": "मुझे यहाँ {count} दिख रही हैं, और लिस्ट आगे भी है। ऐप में नीचे स्क्रोल करके बाकी भेजी जा सकती हैं।",
    "hinglish": "Mujhe yahan {count} dikh rahi hain, aur list aage bhi hai. App mein neeche "
    "scroll karke baaki bheji ja sakti hain.",
}
THATS_ALL: Final = {"en": "That's everything", "hi": "बस इतना ही", "hinglish": "Bas itna hi"}
SEND_MORE: Final = {"en": "Send more", "hi": "और भेजूँगा", "hinglish": "Aur bhejunga"}
WRONG: Final = {"en": "Something's wrong", "hi": "कुछ गलत है", "hinglish": "Kuch galat hai"}
SEND_NEXT: Final = {
    "en": "Send the next screenshot and I'll add it to these {count}.",
    "hi": "अगला स्क्रीनशॉट आने पर मैं उसे इन {count} में जोड़ दूँगा।",
    "hinglish": "Agla screenshot aane par main use in {count} mein jod doonga.",
}
WHICH: Final = {"en": "Which one is off?", "hi": "कौन सी गलत है?", "hinglish": "Kaun si galat hai?"}
START_OVER: Final = {"en": "Start over", "hi": "फिर से शुरू", "hinglish": "Phir se shuru"}
STARTED_OVER: Final = {
    "en": "Cleared. Send a screenshot of your holdings when you're ready.",
    "hi": "मिटा दिया। जब मन हो, होल्डिंग्स का नया स्क्रीनशॉट भेजा जा सकता है।",
    "hinglish": "Mita diya. Jab mann ho, holdings ka naya screenshot bheja ja sakta hai.",
}
WHAT_SHOULD: Final = {
    "en": 'What\'s the right number for {name}? Write it in plain words, like "15 shares", '
    '"average 450" or "remove it". If it\'s the wrong kind of holding, tap the right kind.',
    "hi": '{name} के लिए सही गिनती क्या है? सीधे शब्दों में लिखें, जैसे "15 शेयर", "औसत 450" या '
    '"हटा दो"। अगर इसका प्रकार गलत है, तो सही प्रकार वाला बटन दबाया जा सकता है।',
    "hinglish": "{name} ke liye sahi ginti kya hai? Seedhe shabdon mein likh sakte hain, jaise "
    '"15 shares", "average 450" ya "hata do". Agar iska type galat hai, toh sahi type '
    "par tap kar sakte hain.",
}
NOT_CAUGHT: Final = {
    "en": 'I didn\'t catch that. Write the number of shares, like "15 shares", the average '
    'price, like "average 450", or "remove it".',
    "hi": 'यह समझ नहीं आया। शेयरों की गिनती लिखें, जैसे "15 शेयर", औसत कीमत, जैसे "औसत 450", या "हटा दो"।',
    "hinglish": 'Yeh samajh nahin aaya. Shares ki ginti likh sakte hain, jaise "15 shares", '
    'average keemat, jaise "average 450", ya "hata do".',
}
CHANGED: Final = {"en": "Updated {name}.", "hi": "{name} अपडेट कर दिया।",
                  "hinglish": "{name} update kar diya."}  # fmt: skip
REMOVED: Final = {"en": "Removed {name}.", "hi": "{name} हटा दिया।",
                  "hinglish": "{name} hata diya."}  # fmt: skip
WHAT_KIND: Final = {
    "en": "What kind of holding is {name}?",
    "hi": "{name} किस तरह की होल्डिंग है?",
    "hinglish": "{name} kis tarah ki holding hai?",
}
KIND_BUTTONS: Final = {
    Bucket.GROWTH: {"en": "Single shares or themes", "hi": "अलग शेयर या थीम",
                    "hinglish": "Alag shares ya theme"},
    Bucket.CORE: {"en": "Broad index fund", "hi": "ब्रॉड इंडेक्स फ़ंड",
                  "hinglish": "Broad index fund"},
    Bucket.SAFETY: {"en": "Safe money (liquid, gilt, FD)", "hi": "सुरक्षित पैसा (लिक्विड, गिल्ट, FD)",
                    "hinglish": "Safe paisa (liquid, gilt, FD)"},
}  # fmt: skip
SAVED: Final = {"en": "Saved.", "hi": "सेव हो गया।", "hinglish": "Save ho gaya."}
PLAN_IS: Final = {
    "en": "Your plan is {name}: about {parts}.",
    "hi": "आपका प्लान {name} है: लगभग {parts}।",
    "hinglish": "Aapka plan {name} hai: lagbhag {parts}.",
}
PLAN_PART: Final = {"en": "{pct}% in {words}", "hi": "{pct}% {words} में",
                    "hinglish": "{pct}% {words} mein"}  # fmt: skip
AND: Final = {"en": " and ", "hi": " और ", "hinglish": " aur "}
NOW_IS: Final = {
    "en": "Right now {parts}.",
    "hi": "अभी {parts}।",
    "hinglish": "Abhi {parts}.",
}
NOW_PART: Final = {"en": "{pct}% is in {words}", "hi": "{pct}% {words} में है",
                   "hinglish": "{pct}% {words} mein hai"}  # fmt: skip
FURTHEST: Final = {
    "en": "The part furthest from your plan is {words}: at your plan's {plan_pct}% that would "
    "be about {plan_value}, and right now it is {held_value}. That's the part worth reading "
    "about first.",
    "hi": "आपके प्लान से सबसे ज़्यादा दूर {words} हैं: प्लान के {plan_pct}% पर यह लगभग "
    "{plan_value} होता, और अभी {held_value} है। पढ़ने की शुरुआत इसी हिस्से से की जा सकती है।",
    "hinglish": "Aapke plan se sabse zyada door {words} hain: plan ke {plan_pct}% par yeh "
    "lagbhag {plan_value} hota, aur abhi {held_value} hai. Padhne ki shuruaat isi hisse se ki ja "
    "sakti hai.",
}
MATCHES: Final = {
    "en": "Your holdings are split the way your plan is.",
    "hi": "आपकी होल्डिंग्स उसी तरह बँटी हैं जैसे आपका प्लान।",
    "hinglish": "Aapki holdings usi tarah bati hain jaise aapka plan.",
}
SHOW_PLAN: Final = {"en": "Show my plan", "hi": "मेरा प्लान दिखाएँ", "hinglish": "Mera plan dikhao"}
HISTORY: Final = {
    "en": "What would history say?",
    "hi": "इतिहास क्या कहता है?",
    "hinglish": "Itihaas kya kehta hai?",
}
BUCKET_WORDS: Final = {
    Bucket.GROWTH: {"en": "single shares or themes", "hi": "अलग शेयर या थीम",
                    "hinglish": "alag shares ya theme"},
    Bucket.CORE: {"en": "broad index funds", "hi": "ब्रॉड इंडेक्स फ़ंड",
                  "hinglish": "broad index funds"},
    Bucket.SAFETY: {"en": "safe money (liquid, gilt, FD)", "hi": "सुरक्षित पैसा (लिक्विड, गिल्ट, FD)",
                    "hinglish": "safe paisa (liquid, gilt, FD)"},
}  # fmt: skip
NOT_A_PICK: Final = {
    "en": "I don't pick holdings or say what to do with them. That choice stays yours. Here is "
    "how your holdings sit next to your plan, and what history says about a mix like this.",
    "hi": "मैं होल्डिंग्स नहीं चुनता, न यह बताता हूँ कि इनका क्या करना है। यह फ़ैसला आपका है। यह रहा कि "
    "आपकी होल्डिंग्स आपके प्लान के मुकाबले कैसी हैं, और इतिहास ऐसे मिश्रण के बारे में क्या कहता है।",
    "hinglish": "Main holdings nahin chunta, na yeh batata hoon ki inka kya karna hai. Yeh faisla "
    "aapka hai. Yeh raha ki aapki holdings aapke plan ke muqable kaisi hain, aur itihaas aise "
    "mix ke baare mein kya kehta hai.",
}
REMOVE_BUTTON: Final = {"en": "Remove it", "hi": "इसे हटा दो", "hinglish": "Ise hata do"}
