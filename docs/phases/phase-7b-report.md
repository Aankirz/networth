# Phase 7B report · Holdings on Telegram

A set-up user sends a screenshot of their holdings. They get back the list we read, in their language, with three buttons: Looks right, Fix a line, Cancel. Once they confirm, they get the Phase 7 report in the 3E message shape. `/holdings` sends it again. `/link_broker` gives US users a read-only broker link. A holdings question in chat gets the facts and never advice.

## Flows

| Flow | What happens | Where |
|---|---|---|
| **Photo in** | A photo (largest `PhotoSize`), or a document whose `mime_type` starts with `image/`, is downloaded inside the queued answer job and passed to `holdings_from_photo`. The bytes stay a local variable. They are never logged or written. The hourly answer cap applies. | `commands.on_media`, `bot/holdings.photo_reply` |
| **Not holdings** | When the reader returns no rows, the image goes to Explain this as before. Any list stored before the photo is put back, because `holdings_from_photo` saves even an empty read. | `photo_reply` |
| **Confirm prompt** | Numbered lines, each with name, units, average cost and bucket. A "Not read" line when rows were skipped. One question per line the bucket table can't place. The fix format. No footer, because it is a question. | `confirm_reply` |
| **Looks right** | Asks again while any line is unplaced. Otherwise `confirm_holdings`, then the report. | `TAP_ACTIONS["hd:ok"]` |
| **Fix a line** | The tap explains the format. A typed "2 units 15", "2 cost 450", "2 growth" or "2 drop" goes to `fix_line` and shows the prompt again. A typed fix is only taken while a list is unconfirmed, so after confirming the same text goes to chat. | `typed_fix`, `commands.on_profile_text` |
| **Cancel** | Deletes the unconfirmed list. | `TAP_ACTIONS["hd:cancel"]` |
| **Report** | `report_for` re-prices with Yahoo, then `holdings_lines`. Title: the head line. Body: rows, total, mix, and the label without its last sentence. Detail (collapsed): history, method and price-source lines. One footer. A url button to `/u/{signed}/holdings` when the server has a public URL and link secret. | `report_reply` |
| **/holdings** | The report, or "Send me a screenshot of your holdings and I'll read it." with no confirmed list. Runs after the update lock, because pricing is network. | `commands.cmd_holdings` |
| **Holdings question in chat** | New `Intent.HOLDINGS`, picked by the model or by phrases (portfolio, my investments, my holdings, investments doing, should i sell). The handler calls `holdings_answer`, which goes through the guard and declines advice. With no models, it sends the fixed decline plus the report. | `chat/__init__.py`, `bot/holdings.chat_answer` |
| **/link_broker** | For a USD user, `snaptrade_link` as a url button. For anyone else, the US-only line. With no SnapTrade keys, the "not available yet" line. A SnapTrade error gives the usual try-again line. | `link_broker_reply` |
| **/stop** | Sends "Stopped", then `forget_snaptrade` (a failure is logged by user id and never blocks the stop), then `new_link_token` so an old `/u` link stops working, then the stopped save, which deletes holdings and the SnapTrade row. | `commands.cmd_stop` |
| **Group chats** | A message or tap from a chat whose `type` is not "private" creates no profile and stores nothing. A message gets one line in English and Hindi asking for a private chat. A tap gets the same line as a toast. | `commands.NotPrivate` |
| **Stale stored brief** (coordinator addition) | Each stored brief's inputs key now includes `FORMAT_KEY`, a hash of the `networth/brief` sources and `message.py`. After a deploy that changes them, the next `/brief` that day writes the brief afresh. The day's claim still stops a second scheduled send. | `bot/briefs.py` |

## Sample messages

From the real code, with the recorded vision answer for `tests/fixtures/holdings/groww_fake.png` and a no-op price source. Plain render. In Telegram the title is bold, the detail is a collapsed quote and the footer is italic.

**Confirm prompt.** Line 3, an active flexi-cap fund, is asked about rather than guessed.

English:

```text
Here is what I read.

1. UTI Nifty 50 Index Fund Direct Growth: 1250 units, average cost ₹128.40 (core)
2. HDFC Liquid Fund Direct Growth: 20.5 units, average cost ₹4,720.00 (safety)
3. Parag Parikh Flexi Cap Fund Direct Growth: 800 units, average cost ₹68.50
4. Reliance Industries: 40 units, average cost ₹2,450.00 (growth)
5. Tata Motors: 60 units, average cost ₹910.00 (growth)
6. Nippon India ETF Bank BeES: 150 units, average cost ₹470.00 (growth)
7. Infosys: 25 units, average cost ₹1,540.00 (growth)

Is line 3 safety, core or growth? Reply like: 3 growth

To fix a line, type its number and the change: 2 units 15, 2 cost 450, 2 growth or 2 drop.
[Looks right] [Fix a line] [Cancel]
```

Hindi:

```text
मैंने यह पढ़ा।

1. UTI Nifty 50 Index Fund Direct Growth: 1250 यूनिट, औसत लागत ₹128.40 (कोर)
2. HDFC Liquid Fund Direct Growth: 20.5 यूनिट, औसत लागत ₹4,720.00 (सेफ़्टी)
3. Parag Parikh Flexi Cap Fund Direct Growth: 800 यूनिट, औसत लागत ₹68.50
4. Reliance Industries: 40 यूनिट, औसत लागत ₹2,450.00 (ग्रोथ)
5. Tata Motors: 60 यूनिट, औसत लागत ₹910.00 (ग्रोथ)
6. Nippon India ETF Bank BeES: 150 यूनिट, औसत लागत ₹470.00 (ग्रोथ)
7. Infosys: 25 यूनिट, औसत लागत ₹1,540.00 (ग्रोथ)

लाइन 3 सेफ़्टी, कोर या ग्रोथ में है? जवाब ऐसे दे सकते हैं: 3 growth

कोई लाइन ठीक करने के लिए उसका नंबर और बदलाव लिख सकते हैं: 2 units 15, 2 cost 450, 2 growth या 2 drop।
[सही है] [एक लाइन ठीक करनी है] [रद्द]
```

Hinglish:

```text
Maine yeh padha.

1. UTI Nifty 50 Index Fund Direct Growth: 1250 units, average cost ₹128.40 (core)
…rows 2 to 7 as in English…

Line 3 safety, core ya growth mein hai? Jawab aise de sakte hain: 3 growth

Koi line theek karne ke liye uska number aur badlav likh sakte hain: 2 units 15, 2 cost 450, 2 growth ya 2 drop.
[Sahi hai] [Ek line theek karni hai] [Cancel]
```

**Report**, after "3 growth" and Looks right. The rows are the Phase 7 sample lines word for word (see `docs/phases/phase-7-report.md`). The test table gave the history numbers below, so production numbers will differ.

```text
What you hold, valued on 25 October 2026: 7 holdings.

1. UTI Nifty 50 Index Fund Direct Growth (core): 1250 units at an average cost of ₹128.40. Put in ₹1,60,500, worth ₹2,02,625 now, +₹42,125 (+5.2% a year, XIRR). Price from your screenshot.
…rows 2 to 7…

In total: put in ₹5,73,660, worth ₹6,51,285 now, +₹77,625 (+13.5% in total, a simple return as no start date was shown).

Your mix by value now, next to the plan you saved:
Your plan says 20% safety. Your holdings are 16% safety.
Your plan says 70% core. Your holdings are 31% core.
Your plan says 10% growth. Your holdings are 53% growth.

This is what you hold and what history says about a mix like it. It is not advice. What you do is your choice.

[collapsed] In N% of paths a mix like your holdings fell 20% or more at some point. … Prices from your screenshot: 7 of 7 holdings.

Research, not advice.
[My holdings page]
```

The Hindi and Hinglish reports have the same layout. Their last body lines are "यह वह है जो आपके पास है, और इतिहास ऐसे मिश्रण के बारे में क्या कहता है। यह सलाह नहीं है। आप क्या करते हैं, यह आपकी पसंद है।" and "Yeh wahi hai jo aapke paas hai, aur itihaas aise mix ke baare mein kya kehta hai. Yeh advice nahin hai. Aap kya karte hain, yeh aapki pasand hai.". The footers are "रिसर्च, सलाह नहीं।" and "Research hai, advice nahin.".

**"What should I sell?"** gets the Phase 7 decline as its first line, then the report, with one footer:

- "I don't rate holdings or say what to do with them. Here is what you hold and what history says about a mix like it."
- "मैं होल्डिंग्स को रेट नहीं करता, न यह बताता हूँ कि इनका क्या करना है। …"
- "Main holdings ko rate nahin karta, na yeh batata hoon ki inka kya karna hai. …"

**/link_broker:**

| Case | English | Hindi | Hinglish |
|---|---|---|---|
| INR user | Linking a broker works for US accounts only for now. A screenshot of your holdings works here. | ब्रोकर लिंक करना अभी सिर्फ़ US खातों के लिए है। यहाँ आपकी होल्डिंग्स का स्क्रीनशॉट काम करता है। | Broker link karna abhi sirf US accounts ke liye hai. Yahan aapki holdings ka screenshot kaam karta hai. |
| No keys | Broker linking isn't available yet. A screenshot of your holdings works for now. | ब्रोकर लिंक करना अभी उपलब्ध नहीं है। … | Broker linking abhi available nahin hai. … |
| USD user | This opens SnapTrade with read-only access, so it can read your holdings and never place a trade. [Link my broker (read-only)] | … [मेरा ब्रोकर लिंक करना (सिर्फ़ पढ़ने के लिए)] | … [Mera broker link karna (read-only)] |

**Group chat:** "I only answer in a private chat. Message me directly and we'll start there." followed by "मैं सिर्फ़ प्राइवेट चैट में जवाब देता हूँ। मुझे सीधे मैसेज करने पर वहीं से बात शुरू होगी।"

The script that prints these samples is outside the repo. Every string above is a module-level table in `networth/bot/holdings.py` or `networth/holdings/lines.py`, and `tests/test_voice.py` walks both modules.

## BotFather command list

Paste into BotFather with /setcommands:

```text
brief - this month's brief
plan - see or change your plan
range - what your plan could become, replayed over past months
holdings - what you hold, read from a screenshot you send
link_broker - link a US broker, read-only
watch - hear once when a confirmed story about something appears
watches - see or stop your watches
unwatch - stop a watch by its number
pause - pause briefs and alerts
resume - turn them back on
link - a code to use me by email too
sendto - where briefs and alerts go, email or telegram
start - set up again or see your answers
help - everything I can do
stop - stop all messages
```

`/help` lists `/holdings` and `/link_broker` in all three languages.

## Tests

`make check`: 992 passed after rebasing onto Phase 3F. That is 918 before this phase, 68 added here, and 6 from 3F. No test touches the network.

- **`tests/test_bot_holdings.py`:**
  - a photo becomes a confirm prompt listing all 7 in each language;
  - a non-holdings picture goes to Explain this and keeps the earlier list;
  - an unplaced line is asked again;
  - Looks right gives a report carrying every `holdings_lines` line, in each language;
  - fix then confirm;
  - Fix a line explains the format;
  - cancel stores nothing;
  - an unconfirmed list gives no report;
  - `/holdings` with and without a list, with and without the page button;
  - "What should I sell?" gets the decline and the report, in each language;
  - a writer's advice draft falls back to the decline;
  - a USD list keeps every line in its place.
- **`tests/test_bot_holdings_edges.py`:**
  - `/link_broker` for USD, INR and no keys;
  - `/stop` calls `forget_snaptrade`, deletes holdings and rotates the link token, so the old token no longer resolves;
  - `/stop` still stops when SnapTrade fails;
  - group messages and taps;
  - an image sent as a document;
  - the image is never written: every file under the data dir and the working dir is snapshotted, and no file holds the bytes;
  - the image is never logged (caplog);
  - voice samples, with the footer once on the report and answer and none on prompts or acks.
- **`tests/test_bot_briefs_format.py`:** a legacy stored brief is rewritten on the next `/brief` the same day, and the claim still stops a scheduled second send.
- **Mutation check.** The implementer broke five behaviours one at a time. The tests caught each one: the list restore, the SnapTrade forget, the confirmed-list fix guard, the token rotation and the group filter.

## Deviations

1. **Prompts are written in the bot, not in `networth/holdings/`.** `ConfirmPrompt.text`, `confirm_holdings` and `fix_line` reply in English only, and holdings code was off limits. The bot builds its prompts from the stored `Holdings` in three languages and uses the entry points only for state.
2. **The report's "Research, advice nahin." is dropped at render time.** The Phase 7 label ends with its own disclaimer, which in Hinglish differs from the 3E footer. The bot removes the label's last sentence, read at runtime from `LINES[lang]["label"]`, so the footer appears once.
3. **The chat change is outside `networth/bot/`.** `Intent.HOLDINGS` lives in `networth/chat/__init__.py`, because that is where intents are picked. Its CRITERIA line says "what to do with them", because the voice walker rejects "sell" and "should" in our own tables. `PHRASES` was added to `NOT_WORDS` in `tests/test_voice.py`, because it holds what users type, not what we send.
4. **`Services` gains `prices` and `snaptrade`.** Production sets `YahooPrices()` and builds SnapTrade from its keys. Tests inject fakes.
5. **The stale-brief fix stores the format inside the inputs key, not in a new column.** Any edit to the brief code changes the key, so nobody has to remember a version bump, and `store.py` has no schema change. The cost is one extra rewrite, with no model call, after any edit to those files, a refactor included.
6. **"Looks right" with an unplaced line asks again.** On the Groww fixture, line 3 (Parag Parikh Flexi Cap) must be placed first. Live, the coordinator sends "3 growth", then taps Looks right.

## Known gaps

- **A new screenshot replaces the previous list once read,** and Cancel doesn't bring a previous confirmed list back. The entry point overwrites it before the user taps. Only an empty read restores it.
- **A non-holdings image costs two vision calls,** the holdings read and then Explain this.
- **Very long lists can exceed Telegram's 4,096-character limit.** About 25 or more holdings would. The send then fails and the user gets the try-again line.
- **Documents over 20 MB fail at `getFile`,** Telegram's bot download limit, and get the try-again line.
- **Intent picking for HOLDINGS by the live model is not measured.** `evals/intent_accuracy.py` has no holdings cases yet. The phrase fallback is tested.
- **Bank BeES is placed as growth.** That comes from the Phase 7 bucket table, where sector comes before index.
- **Email (Keiki) users can't tap buttons.** The holdings flow is Telegram-only.

## OWNER NEEDED

- `OWNER NEEDED: push access - git push to https://github.com/Aankirz/networth returns 403 for ankit-kiran-7. Grant that account write access, or push from an account that has it: cd ~/Desktop/networth-7b && git pull --rebase && git push origin main`
- `OWNER NEEDED: deploy Phase 7B - npx maritime deploy networth --source github --repo https://github.com/Aankirz/networth --branch main --wait --json, then wake it with curl https://api.maritime.sh/a/eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea/health`
- `OWNER NEEDED: BotFather - send /setcommands to @BotFather, pick the bot, paste the command list above`
- `OWNER NEEDED: decide whether a sector index ETF (Bank BeES) is growth or core - networth/holdings/model.py BUCKET_RULES, owned by holdings`
- `OWNER NEEDED: SnapTrade keys for /link_broker live - the Phase 7 report's steps, then add SNAPTRADE_CLIENT_ID and SNAPTRADE_CONSUMER_KEY to the server env`

Live check for the coordinator after the deploy:

1. Send `groww_fake.png` and check that all 7 lines are listed.
2. Send `3 growth`, tap Looks right, and compare the numbers with `holdings_lines`.
3. Send `/holdings` and open the page button.
4. Ask "What should I sell?".
5. Send `/link_broker` on the INR profile.
