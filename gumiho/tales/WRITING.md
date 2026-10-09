# Nine Tails Tales — how to write one episode (explainer long-form, from Episode 027)

**Nine Tails Tales** is now an English **science & extreme-places explainer** channel. One long-form a week,
published **Sunday 14:00 UTC (10:00 ET)**, 10–12 minutes. The daily Shorts (a separate pipeline) cut single
items out of that week's episode and send viewers to it, so **the long-form is the destination**.

Audience: overseas English speakers aged 20–39 (25–34 is 43%), 70% male, 73% US.

**Why this format (research, 2026-10-09 — `C:\wbtmp\research1009\nt_topics`, `nt_gap`, `nt_formats`):**
- "Most dangerous places" top-10 videos: median **871K** views, with **8 breakouts from small channels**.
- Mariana Trench: a **20K-subscriber** channel got **2.8M** views.
- The "Explained in 9 Minutes" series got **637K**.
- MrUnnerving's "…You CANNOT Survive" got **666K**.
- Our own Korean-folklore long-forms got **0–15 views**. The owner banned those topics on 2026-10-09.

The exemplar is `gumiho/tales/scripts/027_places-you-cant-survive.json`. Read it first and match its
voice, pacing and JSON shape. The code enforces the hard rules: `python gumiho/tales/tales.py check <file>`
must print ✅. This page is about making the episode *good* and *honest*.

## Which episode
`python gumiho/tales/tales.py next --date <today, YYYY-MM-DD>` prints this week's catalog entry, or
`{"none": true}`. If it prints `none`, write nothing. Write only the entry it gives.
- `exemplar_ready: true` means a human already wrote this episode in `gumiho/tales/scripts/<file>`.
  Copy that file unchanged.
- `publish_at` is the Sunday slot. The upload code schedules it; you don't.
- `teaser` is next week's episode. Use its `line` for the closing teaser and never invent a different one.
  When next week isn't scheduled yet, `line` is just "A new one next Sunday." Say that and don't name a topic.

## Facts and sources (hard rule — YouTube "inauthentic content" policy)
Every episode stands on **its own researched facts**. That is what separates it from mass-produced filler.
- Use **only** the entry's `facts` for numbers, dates, depths, temperatures and percentages. The checker
  compares every number above 12 with the entry's facts and rejects any it doesn't find there. That covers narration,
  `odds`, `note`, the title, the thumbnail text, the hook and every Short's title, hook and lines.
  If you need a number that isn't there, leave it out or describe it without a number ("colder than any freezer you own").
- **Times are checked strictly** (checked): any number followed by a time unit ("3 minutes", "9 to 12 seconds",
  "1,000 years") must appear in the facts with the same unit, even small numbers. Write times in digits. A spelled-out
  time ("ninety seconds", "two weeks") is rejected unless that exact phrase is in the facts. Don't convert units
  or compute new numbers. Say "moments" or "a while" instead.
- Respect every `careful` note. Write "about" or "roughly" when the facts give a range.
- Copy the entry's `sources` into the script's `sources` field: at least 3, each with publisher, title and URL
  (checked). Every link must come from the entry's `sources` (checked). They go into the description word for word.
- Every numbered segment card lists the sources for **that segment's** numbers in `src` (1–5 items copied from
  `sources`, checked): `{"card": "#5", "sub": "Lut Desert, Iran", "src": ["NASA Earth Observatory — Iran's Lut Desert: https://…"]}`.
  A Short cut from that segment shows those sources in its description.
- Never invent quotes, studies, records, death tolls or **survival times**. No source tells you how long a person
  "would last" somewhere, so never write one. A survival-odds line is a judgment built on the facts ("without a
  pressure suit: none worth mentioning"), or it quotes a time the facts really give (for example "1 to 5 minutes of
  useful consciousness", which is not the same as being alive).
- **No real victims and no real people dramatized.** You may state a historical fact in one line
  ("In 1960 a two-man submersible reached the bottom"). Never re-enact a real death or accident, never name
  or depict casualties, never show a real person's face.
- **No franchises and no borrowed universes:** no SCP, Backrooms, creepypasta, games or films as the subject
  (checked).

## Banned topics (checked)
No folklore of any kind, and no Korean, Japanese, Chinese or East Asian legends, myths, ghosts or monsters. No
Joseon-era settings, gumiho, kitsune, foxes, hanbok, hanok, shamans, dokkaebi, kappa, oni, yokai or reapers, and no
urban legends, in narration, pictures, titles or tags. The channel name stays; the old identity doesn't.

## Gumi — the voice (voice only, never on screen)
- Gumi is the host you **hear**: a dry, witty, very old narrator who has seen everything and is impressed by
  almost nothing. Deadpan understatement, short sentences and one sharp joke per segment at most. The facts are the star.
- Give a **brief intro line** in the first 5 scenes ("I'm Gumi. Today we're visiting ten places that would
  very much like you dead."). The checker needs the name "Gumi" in the first 5 scenes. Keep the intro under 15 seconds.
- She never talks about being a fox or about folklore. She is simply the narrator.
- Address the viewer as "you". "Dear human" is allowed once per episode at most.
- Plain spoken English, no slang that dates, no emojis. PG-13: describe what extreme conditions do to a body
  in clinical, calm terms (pressure, cold, lack of oxygen). Never gore and never real victims.

## Structure
1. **Cold open (scene 0, the first 10 seconds):** the most extreme fact of the episode, with its number
   (checked: scene 0 must contain a number, ≤45 words). No greeting before it.
   Example: "Almost 11 kilometers down, the ocean presses on you with about 1,100 times the pressure at the surface."
2. **Intro (1–2 scenes):** Gumi's one-line intro + the promise ("ten places, ranked from 'bad idea' to 'instant'").
3. **Numbered segments:** at least 4 (checked). Each opens with a card that has a `sub`, which becomes a YouTube chapter:
   - `places` / `ranked`: `{"card": "#10", "sub": "Lut Desert, Iran"}` … `#1`
   - `zones`: `{"card": "ZONE 1", "sub": "The Sunlight Zone"}`
   - `whatif`: `{"card": "8 MIN 20 S", "sub": "Earth Lets Go"}`
   - `abandoned`: `{"card": "I", "sub": "The Fire Underground"}`
   Inside a segment (4–8 scenes): where/what it is → the numbers → what it would do to *you* →
   **the survival-odds line**. One scene per segment carries `"odds"` (checked: exactly one per segment, ≤34
   characters, shown on screen as a red badge), and its `say` delivers the verdict out loud:
   `{"say": "Survival odds: excellent, on the boardwalk.", "odds": "SURVIVAL ODDS: BOARDWALK ONLY", ...}`.
   The badge must start with `SURVIVAL ODDS:`, `AWAKE FOR:` or `RISK:` (checked). Use `AWAKE FOR:` only with a time
   the facts give ("AWAKE FOR: 1–5 MINUTES"). Every digit on a badge must be in the facts, and spelled-out numbers
   are not allowed on badges (checked). Keep the spoken line recurring ("Survival odds: …") but fresh each time.
4. **Mid-episode shock beat:** one short line (≤8 words) with `"hold": 1.0`, `"fx": "none"`, `"move": "in"`.
5. **Closing (checked):** `{"card": "VERDICT", "sub": "Gumi's Verdict"}` in the last quarter → a scene whose
   `say` contains "verdict" ("My verdict: …" — rank, compare, or a dry final judgment) → one real question
   for the comments ("Which one would you last longest in?") → **next week's teaser** from `teaser`
   in the last 3 scenes ("Next Sunday: …" — the word "next" is checked) → a one-line sign-off. A callback to the cold open works best.
- Never put two cards back to back (checked). A text-only screen that lasts too long makes viewers leave.

## Formats (the entry's `format`)
- `places`: a countdown of N real places ("10 Places on Earth You Can't Survive"). Rank by how fast they
  would end you: #10 is survivable for a while with gear, #1 is instant. Use real locations only.
- `zones`: go down (or up) layer by layer: ocean zones, atmosphere layers, Earth's interior. Each zone covers its
  depth or height range, light, temperature and pressure, then what lives there, then what it does to a human.
- `whatif`: an impossible scenario played out on a clock ("What If the Sun Disappeared? Minute by Minute").
  Segments are timestamps. Say once, plainly, that it can't really happen and why. Every timestamp
  must rest on a cited fact. No made-up chain of events.
- `ranked`: N things ranked by a single axis ("Every Way the Universe Could End, Ranked by How Bad It Feels").
- `abandoned`: one real abandoned or uninhabitable place in depth ("This Town Has Been Burning Since 1962").
  Cover what happened physically, why nobody lives there, what's left and what's still dangerous. Use public
  records only, no residents' names and no private property shown as accessible. Never dare viewers to trespass.

## Length and scenes
- **1,450–1,750 words** of narration (≈10–12 minutes). The checker allows 1,400–1,900 and needs 8+ minutes for mid-roll ads.
- **45–70 scenes** (checker 40–80). One scene = one picture for 6–20 seconds = **12–45 words** (hard max 70).
- `hold` (0–3 s): a pause after a reveal (0.6–1.2).
- `note`: a small caption for one key number or unit, e.g. `"10,935 m · 35,876 ft"` (at most ~6 per episode).

## Evergreen
It must still work a year from now. Don't write "this year", "recently", "right now" or "trending" (checked).
Years stated as facts are fine ("in 1983"). The title carries the words people search for, and one of the first
3 `tags` must appear in the title (checked).

## Pictures (`img`)
- Set `"look": "real"` at the top (checked). The renderer adds a photorealistic documentary-film style plus
  "no text, no logos, no watermark". Your prompt gives **subject, setting, time of day, light, scale and mood**
  in one English sentence.
- **Realistic and scientifically accurate:** a real salt flat looks like a real salt flat, and a deep-sea animal
  looks like the real species. Show scale with gear, vehicles or an anonymous figure seen from behind or in a suit.
- **Every scene gets its own new picture.** Never reuse the same prompt twice in an episode (checked: no reused
  stills). Don't copy famous photographs.
- **Never draw Gumi, any fox, or anything fox-like** (checked). No Korean, Japanese or Chinese folklore motifs
  (no hanbok, hanok, temples, shrines, lanterns as decoration). No words, letters or signs. No real people,
  celebrities or victims, no logos, no flags of real organizations, no gore.
- Vary shot size: wide establishing → medium → close-up (a gauge, frost on a visor, a cracked sensor) → wide.
- `fx`: none (default for most realistic shots), dust (deserts, interiors), snow (polar), fog (mist, steam,
  gas), embers (heat, fire, volcanoes), rain. Skip fireflies (fantasy).
- `move`: in (tension), out (scale reveals), left/right (landscapes), up (height, sky), down (depth, falling).
  Don't repeat the same move 3× in a row.
- Give every segment's strongest 2–3 scenes a `key` ("trench-floor", "lut-heat"…) so its Short can reuse them.

## Title, thumbnail, tags
- `title` (≤70 characters): the search phrase people really type, plus the payoff. Patterns that work:
  "10 Places on Earth You Can't Survive — Explained", "The Deep Sea, Explained: Every Zone and What Lives There",
  "What If the Sun Disappeared? Minute by Minute". Use the catalog `title_idea` unless you can clearly improve it.
- `thumb.text`: 2–4 words ("YOU WON'T LAST", "8 MINUTES LEFT"). `thumb.img`: the most extreme image
  of the episode, one clear subject, high contrast.
- `hook`: one sentence for the first line of the description.
- `tags`: 10–15 search phrases ("places you can't survive", "mariana trench", "deep sea explained"…).
- Optional `badge`: the label on the thumbnail and Shorts (default `EXPLAINED`, `WHAT IF` for whatif).

## Shorts attached to the episode (`short` + `shorts_extra`)
1 main Short + 1–2 extra Shorts. **Each one is a single-item cut from ONE segment** of the episode
(checked: all its `scene` keys come from one segment and it uses at least 2 of them). Examples:
"How Long Would You Last at the Floor of the Mariana Trench? #shorts" (from the deep-sea episode),
"How Long Would You Last in Everest's Death Zone? #shorts".
- `title` must be a single-item question (checked): **How Long Would You Last/Survive…**, **Could You Survive…**,
  **What Happens If/When…**, **What If…**, **Why Nobody/You Can't…**, **How Deep/Hot/Cold… Is…**, or a size/danger
  comparison **A vs B**. End with `#shorts`.
- `hook`: 2–7 words (≤38 characters), shown big at the top for the whole Short ("1–5 MINUTES AWAKE",
  "WATER BOILS AT 37°C"). It is checked like narration: only fact numbers, and times only as the facts give them.
- 5–8 lines, 70–130 words (35–55 s). Line 1 is the situation, not a greeting. Line 1 of the main Short is drawn
  over the thumbnail picture. Extra Shorts open on their own scene, never the main Short's first scene (checked).
- No `gumi` lines (checked). Every number comes from the facts, as in the episode.
- Don't end with the answer to everything: give the item's verdict, then a last line that points to the full
  episode ("Nine more places like this in the full video.").
- The renderer adds a 3–5 s end card by itself. Gumi says "The full video is right below. Tap the link."
  over **"FULL VIDEO ↓ / tap the link below"**, with an arrow down to the related-video link. Don't write that line yourself.
- These Shorts are published **after** the episode (Mon / Wed / Fri 14:00 UTC), so the link works.

## Done
Save as `output/tales/<NNN>_<slug>.json` (the `file` value from `next`), run the checker until ✅,
commit **only that file**, push to `routine/tales`.
