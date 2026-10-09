# Nine Tails Shorts — writing guide (2 Shorts a day, 2026-10-13 → 10-26 test)

You write the day's vertical Shorts for **Nine Tails Tales**, an English channel for viewers aged 20–39
(Studio: 25–34 is 43%, 70% male, 73% US). Each day there are **two** Shorts:

| slot | when (UTC / ET) | format | series | playlist |
|---|---|---|---|---|
| A | every day 20:00 / 16:00 | `survival` | "How Long Would You Last…? Pt.N" | How Long Would You Last? |
| B | 10/13, 10/15, 10/17 … 23:30 / 19:30 | `compare` | "… Ranked by Size Pt.N" | Ranked by Size |
| B | 10/14, 10/16, 10/18 … 23:30 / 19:30 | `liminal` | "RULES to Follow if…" (fiction) | Liminal Rules |

Dates above are **publish** days; you write each Short the day before (the routine runs at 12:00 UTC).

Read the exemplars first and match their shape, pace and tone:
`gumiho/tales/rules_scripts/R101_mariana-trench-floor.json` (survival) ·
`R201_deep-sea-creatures-by-size.json` (compare) · `R301_empty-mall-3am.json` (liminal).

## Why these formats (research 2026-10-09, data in C:\wbtmp\research1009\nt_topics · nt_gap · nt_formats)
- "How Long You'd Last in Every Prehistoric Era" got **10.9M** views on a 32K-subscriber channel.
- Most-dangerous-places top-10 videos: median **871K**, with 8 small-channel breakouts.
- A Mariana Trench Short from a **20K**-subscriber channel got **2.8M**.
- A liminal-space Short from a **13K**-subscriber channel got **1.8M**.
- A size-comparison series went Pt.1 → Pt.3 **3.3M → 4.73M** (parts build an audience).
- On our own channel, the only Shorts the feed pushed were **versus** and **rules**.
Our old East Asian folklore topics are **retired** (owner, 10/9). Nothing Korean/Joseon/folklore from now on.

## Get today's entries
`python gumiho/tales/rules.py next --date <today, YYYY-MM-DD>` prints `{"entries": [...]}` — usually **two**
(slot A and slot B). Write **every** entry, each to its own `file` (`output/tales_rules/R<NNN>_<slug>.json`).
If it prints `"none": true`, write nothing. Use each entry's `format`, `part`, `look`, `title_idea`, `situation`,
`facts`, `sources`, `odds_idea`, `teaser_idea`, `careful` (liminal: `premise`, `setting`, `seeds`, `twist_idea`).

## The four policy rules (YouTube "inauthentic content" — template channels were deleted in Jan 2026)
1. **Every episode is different**: its own numbers, its own logic (what kills you, in what order), its own
   pictures. Never reuse an image prompt from another episode (the checker compares with every script in the
   folder) and never reuse a beat structure word-for-word.
2. **Sources**: every fact line has `"src": <index>` into the script's `sources`, and `sources` are copied from
   the catalog entry **exactly** (no new URLs). A script with numbers and no sources is rejected.
   **Numbers only from the catalog `facts`** — the checker rejects any digit that isn't in them. If you need a
   number that isn't there, leave it out (say "about a thousand times" in words, or skip the beat).
3. **No real victims, no real people, no franchises, no SCP, no Backrooms.** No named climbers, castaways,
   astronauts, crews, disasters' casualties; no movies/games/shows (no Interstellar, Jurassic Park, The Meg…).
   The viewer is always a hypothetical "you".
4. **Banned topics**: Korea/Korean, Joseon, gumiho, dokkaebi, reapers, folklore, legends, kitsune, yokai, foxes.
   Present-day or space settings only. **Gumi is voice-only**: never draw Gumi or any fox; never put her in `img`.

## Format A — `survival` ("How Long Would You Last…? Pt.N"), 30–45 s (70–110 words)
- `situation`: the place in big words, ≤36 chars (`"FLOOR OF THE MARIANA TRENCH"`). It is on screen from the
  first frame, with the survival clock at **0:00**. Use the entry's `beat_ideas` — their clock labels already pass.
- `beats` (4–6): `{"t": "0:00", "text": "16,000 PSI", "say": "…", "img": "…", "src": 0}`.
  - **Never invent a survival time.** `t` is either
    - a clock label (`M:SS`, `H:MM:SS`, `DAY N`) **only when a catalog fact gives that number with its unit**
      (`0:12` needs a fact like "about 9-12 seconds"; `3:00:00` needs "about 3 hours"; `DAY 3` needs "3 days"), or
    - a word when no source gives a time: `INSTANT`, `SECONDS`, `MINUTES`, `HOURS`, `DAYS` (optionally a short
      caps qualifier, e.g. `MINUTES WITH WATER`). The clock then shows the word instead of a fake mm:ss.
    The first beat is `0:00`. Labels never go backwards (several beats may share `0:00` or `INSTANT` — order them
    "what hits you first → next"). The checker rejects any clock value that isn't in the entry's facts.
  - Each beat says **what happens to your body**, using one real number (pressure, temperature, oxygen, speed,
    dose…). `text` ≤34 chars is the number in big words. `say` ≤26 words, second person, present tense.
  - The **last beat is the moment you're done** — the clock stops there. Comparisons ("a NOAA microphone lasted
    23 days down here", "Venera 13 lasted 127 minutes") go into Gumi's line, not into a beat (the clock would
    suggest *you* lasted that long). Numbers in Gumi's line must also come from `facts`.
- `gumi`: `{"odds": "2%", "say": "Gumi's odds: two percent. …"}` — one line, ≤16 words, contains "odds".
  The odds are her playful verdict; any other number in her line must come from `facts`. Optional: Gumi may open beat 0 ("Gumi here. You just woke up…").
- `teaser`: copy `teaser_idea` (on-screen only, not spoken), e.g. `"PT.2 TOMORROW: MARS, NO SUIT"`. Omit on the last part.
- Title: `How Long Would You Last on the Floor of the Mariana Trench? Pt.1 #shorts` — starts "How Long Would You
  Last", contains `Pt.N`.
- Total words 70–110 including Gumi.

## Format B1 — `compare` ("… Ranked by Size Pt.N"), 25–40 s (60–105 words)
- `hook`: the topic in big words (`"DEEP SEA CREATURES BY SIZE"`), on screen the whole time.
- `unit`, `scale` (`log` when values span more than ~2 orders of magnitude, else `linear`).
- `items`: 4–6 ranked items **smallest → largest**, then **one last item with `"twist": true`**:
  `{"name": "GIANT SQUID", "value": 13, "label": "13 M", "say": "…", "img": "…", "src": 3}`.
  Bars are drawn by code from `value`; `label` is the number people read. The twist either breaks the chart
  (value bigger than everything → the bar shoots off-screen) or has no value and a big `text`.
- `gumi.say` ≤16 words: a verdict or a question for the comments. `teaser` from `teaser_idea`.
- Title contains "Ranked" or "by Size" and `Pt.N`. Total words 60–105.

## Format B2 — `liminal` ("RULES to Follow if You Wake Up in an Empty Mall at 3 A.M."), 20–40 s (50–92 words)
- **Clearly fiction** (`"fiction": true`; the screen shows FICTION and the description says so). Original
  rules for an empty, too-quiet, present-day place — fluorescent hum, wet floor signs, one door that wasn't there.
- `lines` (5–8), numbered rules `"rule": 1, 2, 3…` (≥4), getting stranger. The **last rule bends an earlier one**
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
