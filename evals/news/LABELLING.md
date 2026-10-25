# How the news judge set is labelled

Every row in `labels.jsonl` is one news story as the watcher would see it on the day it was published. The label says what really happened. It does not say what the watcher is expected to output. Labels are written and committed before the judge runs on them.

## Row shape

One JSON object per line:

```json
{
  "id": "in-rbi_hike-2022-05-04",
  "region": "in",
  "kind": "confirmed_event",
  "label": "rbi_hike",
  "event_date": "2022-05-04",
  "seen_on": "2022-05-04",
  "headline": "RBI raises repo rate by 40 bps to 4.4% in surprise move",
  "articles": [
    {"url": "https://...", "title": "...", "published": "2022-05-04T08:50:00+00:00",
     "author": "", "text": "The first 300 or so characters of the article body, copied as written."}
  ],
  "note": "One line on why this label is right, with the fact that decides it."
}
```

- `region`: `in`, `us` or `global`.
- `kind`: one of `confirmed_event`, `rumour`, `old_news`, `opinion`, `near_miss`, `preview`.
- `label`: an event type for a `confirmed_event`, else `none`. The types are `oil_supply, fed_hike, fed_cut, rbi_hike, rbi_cut, union_budget, inr_shock, military_conflict, tariff, bank_stress, pandemic, election`.
- `event_date`: the day the event itself happened, or `null` when there is no event.
- `seen_on`: the day the watcher reads the story. Use the earliest article's publish date.
- `headline`: the story title, taken from one of the articles.
- `articles`: real articles only. Every `url` must open and show that title. `published` is the time the page states, in ISO 8601 with an offset. When the page gives only a date, use `T12:00:00` in the publisher's local time and say so in `note`. `text` is copied from the page, never written by you.

## The label rules

1. **confirmed_event.** The event of that type happened on `event_date`, and the story reports it on or within 3 days after that date. The articles are the real coverage: at least 3 different publishers within 24 hours of each other, or at least 1 primary source (rbi.org.in, sebi.gov.in, pib.gov.in, federalreserve.gov, sec.gov, nseindia.com, bseindia.com, opec.org, finmin.nic.in, indiabudget.gov.in, treasury.gov, ustr.gov, whitehouse.gov, who.int). Reuters, PTI, ANI, AP, AFP, Bloomberg and IANS copies count once per agency.
2. **rumour.** A claim that was not true or not confirmed when it was published: "sources say", a single outlet's scoop that was later denied, a viral claim. Label `none`.
3. **old_news.** The article is published more than 7 days after the event it is about: an anniversary, a recap, an explainer. Label `none`, and give the old event's date in `event_date`.
4. **opinion.** An opinion or analysis piece about an event type, with no new event in it. Label `none`.
5. **near_miss.** A real, widely reported decision that is not one of the types: "RBI holds repo rate", "Fed leaves rates unchanged", "tariff threat" with nothing imposed, an OPEC meeting with no change in output. Label `none`. These need real coverage too, because the confirmation rule passes them and only the judge can stop them.
6. **preview.** "Expected to", "likely to", "markets brace for". Label `none`.

What each type means is the engine's own meaning: a rate type is a change in the policy rate (hold is not a type), `union_budget` is India's Union Budget being presented, `inr_shock` is a sharp rupee fall or a record low against the dollar, `bank_stress` is a bank failure, run, moratorium or rescue, `oil_supply` is an OPEC or war-driven change in crude supply, `tariff` is a US tariff imposed or raised, `election` is a national election result, `military_conflict` is a war, strike or invasion starting or escalating, `pandemic` is a WHO pandemic or emergency declaration.

Never invent a URL, a date, a publish time or article text. A row you cannot source fully is dropped.
