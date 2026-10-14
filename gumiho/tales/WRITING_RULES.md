# Nine Tails Shorts — writing guide (2 Shorts a day, 2026-10-13 → 10-26 test)

You write the day's vertical Shorts for **Nine Tails Tales**, an English channel for viewers aged 20–39
(Studio: 25–34 is 43%, 70% male, 73% US). Each day there are **two** Shorts:

| slot | when (UTC / ET) | format | series | playlist |
|---|---|---|---|---|
| A | every day 20:00 / 16:00 | `survival` | "How Long Would You Last…?" | How Long Would You Last? |
| B | 10/13, 10/15, 10/17 … 23:30 / 19:30 | `compare` | "A vs B vs C \| … Comparison" | Ranked: Biggest, Heaviest, Fastest |
| B | 10/14, 10/16, 10/18 … 23:30 / 19:30 | `liminal` | "RULES to Follow if…" (fiction) | Liminal Rules |

Dates above are **publish** days; you write each Short the day before (the routine runs at 12:00 UTC).

Read the exemplars first and match their shape, pace and tone:
`gumiho/tales/rules_scripts/R101_mariana-trench-floor.json` (survival) ·
`R201_deep-sea-creatures-by-size.json` (compare) · `R301_empty-mall-3am.json` (liminal).
If `gumiho/tales/rules_scripts/<file basename>` already exists for an entry, that script **is** the episode —
copy it unchanged.

## Why these formats (research 2026-10-09, data in C:\wbtmp\research1009\nt_topics · nt_gap · nt_formats)
- "How Long You'd Last in Every Prehistoric Era" got **10.9M** views on a 32K-subscriber channel.
- Most-dangerous-places top-10 videos: median **871K**, with 8 small-channel breakouts.
- A Mariana Trench Short from a **20K**-subscriber channel got **2.8M**.
- A liminal-space Short from a **13K**-subscriber channel got **1.8M**.
- On our own channel, the only Shorts the feed pushed were **versus** and **rules**.
Our old East Asian folklore topics are **retired** (owner, 10/9). Nothing Korean/Joseon/folklore from now on.

## What the winners do — copy it (benchmark 2026-10-11, C:\wbtmp\research1011\nt_bench)
The checker enforces 1–3.
1. **Open with the title question. No intro.** 0 of 76 narrated winner Shorts open with an intro; 35 open with a
   question. Survival line 0 starts "How long would you last …?"; compare line 0's first sentence is a question;
   liminal line 0 puts *you* there ("You wake up alone in a mall at 3 A.M."). Never start a line with "Gumi here" —
   Gumi speaks only in the final verdict (`gumi.say`).
2. **Compare titles are "A vs B vs C | … Comparison".** "vs" is in 54% of 1M+ size-comparison titles and 14% of
   those under 100K; "Ranked" is in 1 of 35. Name famous extremes (the smallest, a famous middle, the biggest or
   the twist) — every name must be an item on screen.
3. **No part numbers.** Small winners almost never number parts (3% of 1M+ survival titles); series without a hit
   shrank every part (×0.6 → ×0.1). We add "Pt.N" only after one Short takes off.
4. **Fast, tight lines.** Winners speak about **195 words a minute**. The renderer speeds the voice up; you keep
   lines short and concrete — one number, one consequence. End on a payoff, not a request.

## Get today's entries
`python gumiho/tales/rules.py next --date <today, YYYY-MM-DD>` prints `{"entries": [...]}` — usually **two**
(slot A and slot B). Write **every** entry, each to its own `file` (`output/tales_rules/R<NNN>_<slug>.json`).
If it prints `"none": true`, write nothing. Use each entry's `format`, `part`, `look`, `title_idea`, `situation`,
`beat_ideas`, `facts`, `sources`, `odds_idea`, `teaser_idea`, `careful` (liminal: `premise`, `setting`, `seeds`, `twist_idea`).

## The four policy rules (YouTube "inauthentic content" — template channels were deleted in Jan 2026)
1. **Every episode is different**: its own numbers, its own logic (what kills you, in what order), its own
   pictures. Never reuse an image prompt from another episode (the checker compares with every script in the
   folder) and never reuse a beat structure word-for-word.
2. **Sources**: every fact line has `"src": <index>` into the script's `sources`, and `sources` are copied from
   the catalog entry **exactly** (no new URLs). A script with numbers and no sources is rejected.
   **Numbers only from the catalog `facts`, with the same unit** — "23 seconds" fails when the fact says
   "23 days". Spelled-out numbers count too ("ninety seconds", "ten kilometers"). The rule covers every field:
   title, hook, situation, description_hook, say, text, name, label and Gumi's line. If you need a number that
   isn't there, leave it out. **No URLs or domain names** anywhere in the text (sources go only in `sources`).
3. **No real victims, no real people, no franchises, no SCP, no Backrooms.** No named climbers, castaways,
   astronauts, crews, disasters' casualties; no movies/games/shows (no Interstellar, Jurassic Park, The Meg…).
   The viewer is always a hypothetical "you".
4. **Banned topics** (`rules.BANNED_WORDS`, plurals included): Korea/Korean, Joseon, gumiho, dokkaebi, reapers,
   Japanese, Chinese, folklore, folk tales, legends, urban legends, mythology, Shinto, creepypasta, kitsune, yokai,
   kappa, oni, foxes; franchises such as Subnautica, Alien, Silent Hill, Resident Evil, Slender Man, Siren Head,
   Netflix, Kisaragi Station, The Exit 8. Present-day Western or space settings only. **Gumi is voice-only**: never
   draw Gumi, a fox, fox/animal ears, tails or an anime girl; never put her in `img`.

## Evergreen (owner, 2026-10-14)
This channel is meant to keep circulating for months and break out late, not to be watched on the day.
Nothing may go stale: no "tomorrow/next Sunday/this week/see you tomorrow/every Friday/recently/currently"
anywhere (checked). The teaser is always "NEXT: …" (it means the next part in the playlist).

## Format A — `survival` ("How Long Would You Last…?"), 30–45 s (70–110 words)
- `situation`: the place in big words, ≤36 chars (`"FLOOR OF THE MARIANA TRENCH"`). It is on screen from the
  first frame, with the survival clock at **0:00**.
- `beats`: **one beat per `beat_ideas` entry (skip the `GUMI` one), in the same order, with the same `t`
  copied exactly** — `{"t": "0:00", "text": "16,000 PSI", "say": "…", "img": "…", "src": 0}`.
  - **Never invent a survival time.** The catalog already chose every `t`, and the checker rejects any other value:
    - a clock (`0:12`, `3:00:00`, `DAY 3`) only where a cited fact gives that number **with that unit**;
    - a bare word (`SECONDS`, `MINUTES`, `HOURS`, `DAYS`) only where the cited fact uses that unit;
    - `--:--` where no source gives a time at all. The clock shows `--:--`; if the last beat is `--:--`, the end
      card drops the clock and shows only Gumi's odds (her opinion). There is no `INSTANT`.
  - Each beat says **what happens to your body**, using one real number (pressure, temperature, oxygen, speed,
    dose…). `text` ≤34 chars is the number in big words. `say` ≤26 words, second person, present tense.
  - Comparisons ("a NOAA microphone lasted 23 days down here", "Venera 13 lasted 127 minutes") go into Gumi's
    line, not into a beat (the clock would suggest *you* lasted that long). Numbers in Gumi's line must also come
    from `facts`.
- `gumi`: `{"odds": "2%", "say": "Gumi's odds: two percent. …"}` — one line, ≤16 words, contains "odds".
  The spoken odds must match `odds`; that one phrase is the only number exempt from `facts`.
- Beat 0 `say` **starts with the title question**: "How long would you last on the floor of the Mariana Trench?
  You just woke up 10,935 meters down. No submarine." No intro, no "Gumi here".
- `teaser`: `teaser_idea` copied **exactly** (on-screen only), e.g. `"NEXT: MARS, NO SUIT"`; leave it out
  when `teaser_idea` is null (last part, liminal).
- Title: `How Long Would You Last on the Floor of the Mariana Trench? #shorts` — starts "How Long Would You
  Last". **No "Pt.N".**
- Total words 70–110 including Gumi.

## Format B1 — `compare` ("A vs B vs C | … Comparison"), 25–40 s (60–105 words)
- `hook`: the topic in big words (`"DEEP SEA CREATURES BY SIZE"`), on screen the whole time.
- `unit`, `scale` (`log` when values span more than ~2 orders of magnitude, else `linear`).
- `items`: 4–6 ranked items **smallest → largest**, then **one last item with `"twist": true`**:
  `{"name": "GIANT SQUID", "value": 13, "label": "13 M", "say": "…", "img": "…", "src": 3}`.
  Bars are drawn by code from `value`; `label` is the number people read. They must be the **same value**
  (the checker converts `label` into `unit`; `value` 130 on a "13 M" label fails). The twist either breaks the
  chart (value bigger than everything → the bar shoots off-screen) or has no value and a big `text` (≤40 chars).
  If the source gives a different unit (feet), say the source's number in `say` ("an estimated 150 feet").
- Item 0 `say`: the **first sentence is a question** ("How big does life get in the deep sea? Start small: …").
- `gumi.say` ≤16 words: a verdict or a question. `teaser` = `teaser_idea` exactly ("NEXT: BLACK HOLES").
- Title: `Anglerfish vs Giant Squid vs Giant Siphonophore | Deep Sea Size Comparison #shorts` — start from the
  catalog `title_idea`; every name before "|" must be one of your `items` names. **No "Pt.N".** Total words 60–105.

## Format B2 — `liminal` ("RULES to Follow if You Wake Up in an Empty Mall at 3 A.M."), 20–40 s (50–92 words)
- **Clearly fiction** (`"fiction": true`; the screen shows FICTION and the description says so). Original
  rules for an ordinary, too-quiet, present-day Western place — fluorescent hum, wet floor signs, one door that
  wasn't there. Don't borrow known internet stories or games (no stations missing from the map, no hallway you
  must turn back in).
- `lines` (5–8), numbered rules `"rule": 1, 2, 3…` (≥4), getting stranger. Line 0 `say` puts **you** in the
  place first ("You wake up alone in a mall at 3 A.M. Rule one: …"). The **last rule bends an earlier one**
  so the viewer is pushed back to rule one; write how in `loop_back`. Line 0 has big `text` (≤48 chars).
- No fact-like numbers (percentages, distances, years, counts of people). Times like "3 A.M." and floor/aisle
  numbers are fine. No sources needed.
- `gumi.say` ≤16 words — her dare ("So. Which rule would you break first?"). No teaser (it would break the loop).
- Title contains "Rules" or "Theory". Total words 50–92.

## Screen safe zone (handled by code — don't fight it)
The YouTube Shorts UI covers the bottom 22% (title, channel, y > 1500) and the right button column (x > 960).
The renderer keeps every caption, number, source and teaser inside x ≤ 960 · y ≤ 1500 (captions end by y 1480),
so keep `text`, `name` and `label` short — long words get smaller, not wider.

## Pictures (`img`)
One English sentence: subject, setting, light, mood, vertical framing with one clear subject in the center.
Every prompt must be new: the checker rejects prompts ≥85% similar to any other prompt in this or earlier
scripts (changing one word or adding ", 4k" is not new).
Photorealistic look is added by code (`look`: `deep`, `space`, `earth`, `ancient`, `liminal`). **No words, letters,
signs with text, logos, real people, gore, bodies, nudity.** Never Gumi, never a fox. For people, show a
generic figure from behind or a silhouette, never a face that could be someone real.

## Title, hook, description, tags
- `title` ≤100 chars, ends with ` #shorts`. `hook` 2–7 words, ≤38 chars (survival: `"HOW LONG WOULD YOU LAST?"`).
- `description_hook`: one sentence for the first line of the description. The description lists the sources.
- `tags`: 6–15 English search words (no channel name — code adds it).
- Scary is fine, graphic is not. No instructions anyone could hurt themselves with.

## Done
Run `python gumiho/tales/rules.py check <file1> <file2>` until every file is ✅ (it also compares pictures with the
other scripts in the folder). Commit **only today's files** and push the `routine/tales_rules` branch (see the
routine prompt for the exact git commands). One push renders and uploads both.
