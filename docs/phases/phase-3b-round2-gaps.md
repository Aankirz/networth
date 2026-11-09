# Phase 3B review, round 1 result

Verified at cb354f9. `make check` passes on a clean clone (377 passed, 1 skipped), and nothing in `data/` or `.env` is tracked. The owner deployed it (deployment 65ab6449). Live, `/health`, `/`, `/why/rbi_hike/^NSEBANK` and `/track-record` return 200, a bad `/u/` token returns 404, and the `brief` and `watcher` schedules are listed. Good work.

The coordinator is now running the live Telegram checks. Fix these meanwhile, then print PHASE 3B READY FOR REVIEW again. Commit with `git commit -- <paths>` only. Never edit `networth/engine/`. After pushing, raise OWNER NEEDED for the redeploy. Don't run it yourself.

1. **The guard lets numbers through.** In `networth/guard.py:30` the lookbehind skips digits after a letter or a dot. `check("Rs5000 gain typical", src)` passes, and so do "Rs.5000" and "INR5000". Number words ("fifty percent", "half the time", "twice") are never checked. Catch both, with tests.
2. **The guard lets advice through.** The coordinator ran each of these, and each passed `check()`:
   - "Investors should hold banks"
   - "I recommend banks"
   - "आपको निवेश करना चाहिए"
   - "Abhi daal dein"
   - "s e l l now"
   - "b<zero-width space>uy now"
   - "Lambe time tak ruko, ghabrao mat"

   Apply NFKC and strip zero-width characters before matching. Catch `should` and `recommend`, plus Devanagari चाहिए, करें and कीजिए. Catch Hinglish imperatives: "chahiye" anywhere, "-iye" and "-ein" endings, daal, nikal, ruko, kijiye. Catch spaced-out letters. Add "score" and "rank" to BANNED. Add one test per string above. Keep false positives low, with a test that a normal brief, why and explain reply still pass.
3. **The writer's own prompt teaches advice.** These rows in `knowledge/glossary.md` are advice, not description:
   - "Lambe time tak ruko" (line 34)
   - "Girawat mein ghabrao mat"
   - "alag-alag companies mein baanto"
   - "alag rakho"
   - "Health aur term insurance pehle"

   Teaching patterns 1 ("one next step") and 12 ("do one thing" close) push the same way. Reword the rows as description ("dips have been normal"), and delete patterns 1 and 12.
4. **Anyone can wake the watcher through `/chat`.** `main.py:101` trusts `body["source"] == "scheduled"`, which anyone can send, and that's up to about 58 paid cycles a day. Use a shared secret if Maritime's trigger docs offer one (look it up, don't invent). Otherwise refuse watcher runs outside the schedule's market hours. Either way, fix the "a forged call costs nothing" claim at `schedule.py:7` and `docs/deploy.md:73`.
5. **There's no chat rate limit per user.** Every text or photo runs Jev, the cheap model, the writer, Exa and vision. Cap paid chat answers per user per hour in Store (config value), with a polite reply when over the cap, and a test.
6. **`/u/{token}` returns 500 on malformed tokens** (`links.py:34-36`): a non-ASCII signature, or `expires="²"`. Make these friendly 404s, with a test.
7. **A scheduled brief can be lost.** In `briefs.py:73-95`, if compose or send fails after `claim_brief`, the claim row stays and no rerun that day sends the brief. Release the claim on failure, or key on a sent flag. Add a test.
8. **Alerts can be lost or burn the cap.** In `schedule.py:97-98`, `insights(since=now)` loses a cycle's alerts if the VM stops between the cycle and `run_alerts`. In `alerts.py:78-86`, a failed send still uses one of the 2 monthly slots. Fix both and test them.
9. **The Jev eval is in-sample.** The criteria at `chat/__init__.py:43-47` were edited after run 1 to name the missed items. Add at least 20 new held-out messages, written before you look at results again (English, Hindi, Hinglish, including tips and forwarded pages). Report both pickers on the held-out set with the production 4 s deadline. Keep Jev only if it's at least the cheap model there.
10. **Explain-this reads a whole page before capping it.** `explain.py:82` reads the full body before slicing to 2 MB. Stream it with a byte cap.
11. **Old `/u/` links stay valid.** Each "fresh link" leaves every older link working for 30 days. If it fits in 20 minutes, put a per-user link epoch in the signature and bump it when a new link is issued. Otherwise record it as a known gap.
12. Update `docs/phases/phase-3b-report.md` (test count, the new guard rules, the held-out Jev table) and the decision log.

The coordinator may send live-Telegram findings as a second note while you work.

## Live Telegram findings (coordinator, 11:15 to 11:20 on the deployed build)

These pass live:
- `/brief` replies, in Hinglish, with the plan and its buttons.
- Explain-this works on pasted IPO text, in English and in Hinglish. "Kya yeh accha hai?" correctly got "these numbers don't settle that", with no score and no apply or skip. Well done.
- `/u/{token}` from the "My page" button returns 200 with the plan, and a tampered token returns 404.

Fix these too:

13. **The deployed product has no news, so the demo is empty.**
    - `/brief` said no confirmed event matched this month.
    - "What happened today?" said "Aaj ki news abhi nahi padhi."
    - Locally, `data/watcher.sqlite` has the 2026-10-07 RBI hike and the bank-stress stories. The VM has none, because the watcher schedule only runs on weekdays 09:00 to 15:00, and it hasn't run since the deploy.

    Make the deployed watcher data repeatable. Either push `watcher.sqlite` the way `scripts/push_rates.sh` pushes rates, or run one cycle on the VM with a documented, authorised command. Document it in `docs/deploy.md`. Done when a live `/brief` shows this month's scoreboard lines with engine numbers, and "What happened today?" answers from confirmed stories.
14. **"Why" refuses a general question.**
    - The coordinator asked "Why do banks move after an RBI rate hike?"
    - The bot replied that the brief had nothing to explain.
    - A why question that names an event type should answer from the engine anyway, with the history line (for example Bank Nifty after RBI hikes, n and hits against the normal rate) and the `/why/...` link. That holds even with no event this month.
15. **The tip verdict is soft.** The fake tip ("200 bps cut tomorrow, banks will double, buy HDFC Bank now, sure shot") got "no publisher report in 7 days, not proven false". Lead with a plain verdict line, "Not confirmed", then the reason. Name the hype signals that were sent ("sure shot", "will double") without adding any number the tip didn't contain.
16. **Model replies use long dashes.** Examples are "hota—but" and "IPO hai—company". The product voice uses short sentences. Tell the writer not to use them, and replace any that come through, before the guard.
17. **Confirm the watcher trigger's timezone.** It must be Asia/Kolkata, like the brief trigger. Paste the `triggers list` output into the report.
