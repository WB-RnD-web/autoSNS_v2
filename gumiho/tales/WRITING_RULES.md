# Nine Tails RULES — writing guide (daily Shorts)

You write **one** 20–35 second vertical Short a day for Nine Tails Tales, an English horror channel for
viewers aged 13–30 around the world. The series is East Asian **rule horror**: Korean, Japanese and Chinese
legends and superstitions turned into rules the viewer must follow. Read the exemplar first:
`gumiho/tales/rules_scripts/R001_name-called-at-night.json` — match its shape, pace and tone.

## Get today's entry
`python gumiho/tales/rules.py next --date <today, YYYY-MM-DD>` prints one catalog entry and the file path
(`output/tales_rules/R<NNN>_<slug>.json`). If it prints `"none": true`, write nothing and stop.
Use the entry's `format`, `region`, `look`, `title_idea`, `premise`, `facts`, `careful`.

## The one rule about rules
**Every rule must come from the entry's `facts` (or the legend's well-known versions).** Never invent a
rule, a ritual step, a death, or a "true story". You may phrase, order and dramatize — not fabricate.
If a fact says versions differ, say "they say" / "in some towns".

## Why this shape (what is working on YouTube right now)
New faceless AI Shorts channels in 2026 hit their first million views on video 16–49, posting about one a
day. The ones that last share: a **second-person warning in the first second** ("If you see…"), **20–30
seconds**, an **ending that loops back to the start**, and a **recurring character**. Channels that only
swapped names on a template were deleted in January 2026 — so every Short is a different legend, different
rules, different pictures.

## Formats
- `rules` — 4–5 numbered rules (`"rule": 1, 2, 3…`), each line one rule, getting stranger. The **last rule
  bends or contradicts an earlier one** (the voice is your mother's — but your mother is asleep next door),
  so the viewer is pushed back to rule one. Write how it loops in `loop_back`.
  Title starts with **Never / Don't / If You / Always**.
- `versus` — two creatures, 3–4 rounds (speed, trick, weakness, what scares it), each grounded in the legends.
  Gumi gives a biased verdict; `vote` asks the comments ("Team Kappa or Team Dokkaebi?"). Title has "vs".
- `pov` — second person, present tense: "You're visiting your grandmother's village. Across the rice field,
  something white is wiggling." Each line is a choice the legend punishes or rewards. Title starts "POV:".

## Lines (5–9)
- `say`: what the narrator says, ≤22 words, short punchy sentences. Total 45–95 words incl. Gumi's line.
- `text`: the BIG on-screen words for that line (≤48 chars, CAPS look good): the rule itself ("DON'T ANSWER
  YOUR NAME"). Line 0 must have `text` — viewers decide in the first second, often with the sound off.
- `img`: one English sentence: subject, setting, time, light, mood. **Present-day settings** for anything
  people still believe today (apartments, school corridors, convenience stores, subways, rice fields, hiking
  trails); the renderer adds the art style. Vertical framing: one clear subject, center. No words/letters in
  pictures, no logos, no real people, no gore, no nudity, nothing that looks like a real crime photo.
  **Never draw Gumi** — she appears only at the end as a sticker.
- Optional `look` per line for a flashback (`joseon`, `japan`, `china`, `myth`); top-level `look` from the
  entry (`modern` unless the entry says otherwise).

## Gumi (end sticker, 1 line)
`"gumi": {"react": "shock" | "smug" | "scared" | "laugh", "say": "…"}` — her verdict or a dare, ≤16 words,
ends with a question for the comments ("So. Would you answer?"). She is a 1,000-year-old nine-tailed fox in
a black hoodie: playful, a little smug, never preachy.

## Title, hook, source, tags
- `title` ≤100 chars, ends with ` #shorts`. Use or sharpen the catalog `title_idea`.
- `hook`: 2–7 words, ≤38 chars, stays on screen the whole Short ("DON'T ANSWER", "NEVER SAY YES").
- `description_hook`: one sentence for the description's first line.
- `source`: where the rules come from, in plain words (goes into the description).
- `tags`: 6–15, include the legend's name (romanized) and English words people search.
- Audience is 13+: scary, not graphic. No self-harm, no instructions someone could hurt themselves with —
  for rituals (one-man hide and seek, bunshinsaba), end with "don't try this".

## Done
Run `python gumiho/tales/rules.py check <file>` until ✅. Commit **only that file** and push it to the
`routine/tales_rules` branch (create the local branch with the same name from origin/main first, then
`git push -f origin routine/tales_rules`). The push renders and uploads it.
