# Nine Tails Tales — how to write one episode

You are writing **one** episode script for the English YouTube channel **Nine Tails Tales**
(Korean urban legends, real places and mysteries, ghost stories and myths for viewers aged 13–34 worldwide —
most of them Korean-culture fans; old myths are at most one episode in four).
The narrator is **Gumi**, a 1,000-year-old Korean gumiho (nine-tailed fox). The exemplar is
`gumiho/tales/scripts/001_gumiho.json` — read it first and match its voice, pacing and JSON shape.

The code enforces the hard rules (`python gumiho/tales/tales.py check <file>` must print ✅).
This page is about making the episode *good*.

## Which tale
`python gumiho/tales/tales.py next --date <today, YYYY-MM-DD>` prints the one catalog entry for this
week. Write that one — not another. Use its `facts` as the skeleton, respect its `careful` notes,
and cite its `sources` in the `sources` field. If a detail differs between versions, say
"in one version…" instead of inventing certainty. Never invent fake quotes, dates or statistics.

## Gumi's voice
- First person, warm, sly, a little dangerous, dryly funny. She is *on the monsters' side*
  and says so with a wink ("I suppose we finally got better publicity").
- Speaks to the viewer as "dear human" occasionally (not every line).
- Plain spoken English. Short sentences for suspense. No purple prose, no modern slang, no emojis.
- She can have opinions and little asides, but the **tale** is the star — at least 60% of the
  runtime is the story itself, told scene by scene with sensory detail.
- PG-13: dread, not gore. Imply violence; never describe wounds, blood pooling, torture in detail.

## Structure (match 001)
1. **Cold open** (scene 0–2): an image + one eerie, specific line that makes the viewer need the
   answer. ≤45 words in scene 0. No greeting before the hook.
2. **Gumi intro** (2–3 `gumi` scenes): "…This is Tale Number N." Keep under 30 seconds.
3. `{"card": "TALE 00N", "sub": "<short tale name>"}` — this card also opens the first chapter.
   **Never put two cards back to back** (the checker rejects it): 5 seconds of text-only screen is where viewers leave.
4. **3–4 chapters**: the first starts right after the TALE card; the next ones open with `{"card": "I", "sub": "…"}` (then II, III…). Background/lore first,
   then the tale proper with rising tension, then what it means / how Korea (or Japan/China) tells it today.
5. **Ending**: Gumi's personal answer or reflection → **one question for the comments**
   ("If you were that boy, would you have swallowed the bead? Tell me in the comments.") → teaser for **next week's catalog entry**
   (use its `angle`) → sign-off in one line (vary it; a callback to the cold open is best).

## Evergreen — it must still work a year from now
This channel lives on search and recommendations, not on today's feed. An episode should be able to
pick up views months later.
- No time-bound phrases: "this Halloween", "recently", "this year", "trending", "right now" (the checker rejects them).
  Years stated as facts are fine ("the 1994 film", "in March 2022").
- The title carries the searchable name people actually type (gumiho, dokkaebi, jangsanbeom, kitsune…) —
  one of the first three `tags` must appear in the title (checked).
- Mention dramas/films only as background, never as the hook — **except `behind` episodes** (below),
  where a famous film or drama is the doorway. Even there, the folklore is the story.
- Tie episodes together: a callback to an earlier tale where it fits, and the teaser for the next one.

## Format (the entry's `format` field)
Same narrator every week, **different shape** — so the channel never feels like the same video twice.
- `tale` — one story told start to finish (the structure above).
- `list` — a countdown ("7 Korean Superstitions…"). Cold open teases #1. Each item opens with a
  card `{"card": "#7", "sub": "<item name>"}` followed by 4–8 scenes: a mini scene that *shows* it,
  the real belief/fact, Gumi's comment. Get stranger as you count down; #1 is the scariest or most surprising.
  Only the first 3 cards need `sub`s for chapters; give every item a `sub` anyway.
- `urban` — a modern legend (school panics, internet creatures). Open on a "witness" moment,
  framed as a rumor ("people swear…"), then: where it started, the older folklore underneath it,
  how the panic spread, what's real vs. rumor, Gumi's verdict. Never present sightings as fact,
  never name private people or private addresses.
- `versus` — three contenders, 3–4 rounds as chapters (origins, powers, weaknesses, most famous case),
  a comically biased verdict from Gumi, and a question for the comments ("who would YOU pick?").
- `behind` — the real Korean folklore behind a famous film or drama (KPop Demon Hunters, Exhuma…).
  Viewers aged 13–34 search for the culture behind what they just watched; the work is the doorway.
  The title names the work and the folklore ("The Real Korean Legends Hidden in KPop Demon Hunters").
  Cold open on the folklore, not the film: the oldest, strangest version of the thing the viewer
  thinks they know. Then **3 chapters, one per element** (e.g. the reapers, the tiger and magpie,
  the shamans): what the film shows in one line → the real tradition, told with a mini scene →
  what the film changed or kept. End with Gumi's verdict and a comments question
  ("Which one did you recognize?").
  Rules: premise only — no plot spoilers past the first act; never quote the film; never depict its
  characters, costumes or scenes in pictures (draw the folklore itself: Joseon reapers, a minhwa-style
  tiger, a shaman's ritual); say the film "echoes" or "draws on" a tradition unless a source says the
  creators stated it; never imply the channel is affiliated with the studio.
- `mystery` — a real record or a real place that nobody has fully explained (a royal chronicle's
  sky sighting, an abandoned building with a legend). Cold open on the record or the place itself.
  Chapters: what was actually recorded or reported → the world it happened in → the explanations
  (science first, then folklore and rumor) → what is still unexplained. Gumi gives her verdict and asks
  the comments. Rules: never present the supernatural as fact; paraphrase records, never invent quotes,
  names or numbers; no real victims, patients or private people named or depicted; no trespassing dares.

## Make it hit (every format)
- **Scene 0 is the scariest or strangest image of the episode**, not the calm beginning.
- Plant **one shock beat around the middle**: a short line (≤8 words) that turns the story,
  with `"hold": 1.0`–`1.5`, `"fx": "none"`, `"move": "in"` (001: "Your liver.").
- End every chapter on an open question or a threat, so the next card feels like a cliffhanger.
- Dread and suspense, never gore: the scariest thing is what the viewer imagines.

## Length and scenes
- **1,700–2,300 words** of narration (≈11–15 minutes). The checker allows 1,200–2,600.
- **45–75 scenes.** One scene = one picture on screen for 6–20 seconds = **12–45 words**
  (hard max 70). Split long passages into several scenes with different pictures.
- `hold` (0–3 s) adds a pause after a line — use it after reveals (0.6–1.2).
- `note` puts a small caption on screen: use it for Korean/Chinese/Japanese terms,
  e.g. `"여우구슬  yeowoo guseul  =  the fox bead"`. At most ~5 per episode.

## Pictures (`img`)
- The renderer prepends a house style (anime film still, painterly, cinematic). Your prompt
  describes **subject, setting, time of day, light, mood** in one sentence. English only.
- **Recurring characters**: write one fixed description and reuse it *verbatim* every time
  (001 uses "a beautiful young woman in a pale jade hanbok with a red ribbon in her long black hair").
- Korean tales: hanbok, hanok, gat hats, Joseon villages, pine mountains. Never torii gates,
  kimono or pagodas in a Korean tale (and vice versa for Japan/China episodes).
- No words/letters/signs in pictures. No nudity, no gore, no real celebrities, no logos, no scenes
  copied from films or dramas (mention a drama in narration; don't depict its actors).
- Vary shot size: wide establishing → medium → close-up (eyes, hands, an object) → wide.
- `gumi`: `front` | `bead` | `wink` — Gumi's own portraits. Use for her intro, asides and ending
  (about 6–10 scenes). Never describe Gumi in an `img` prompt except as a silhouette.
- `fx`: fog (mountains, night), embers (fire, danger, Gumi), snow, rain, fireflies (magic, night),
  dust (interiors, calm), none (pure black close-ups).
- `move`: in (tension, faces), out (reveals, endings), left/right (travel, landscapes), up (sky,
  tall things, awe), down (falling, the ground, the underworld). Don't repeat the same move 3× in a row.
- Give 5–7 story scenes a `key` ("girl", "scream"…) so the Short can reuse them.

## Title, thumbnail, tags
- `title` (≤100 chars): a curiosity hook first, the searchable name second.
  Patterns that work: "Korea's X Is Darker Than Japan's Y | The X Legend",
  "Every Magistrate Who Slept Here Died by Morning | The Legend of Arang".
  Use the catalog `title_idea` or improve it.
- `thumb.text`: 2–4 punchy words in caps-friendly English ("NEVER KISS HER", "DON'T ANSWER").
  `thumb.img`: the single most arresting image of the tale, a face or figure large in frame.
- `hook`: one sentence for the description's first line.
- `tags`: 10–15, include the creature/tale name in romanized Korean and English.

## The Short (`short`)
- 5–8 lines, 70–130 words (35–55 s). Line 1 is the hook (a situation, not a greeting).
- `hook`: 2–7 words (≤38 characters) shown in big letters at the top for the whole Short —
  the question the viewer needs answered ("SHE ATE THEM ALL", "NEVER KISS HER ON THIS ROAD").
  Viewers decide in the first second, often with sound off. The renderer uses the thumbnail
  picture for line 1, so write line 1 to fit `thumb.img` (the scariest image of the tale).
- Tell the setup and the turn; **do not reveal the ending** — the last line is Gumi
  (`"gumi": "wink"`) sending viewers to the full tale.
- Reuse pictures by `scene` key; `title` ≤100 chars ending with `#shorts`.

## Extra Shorts (`shorts_extra`, required from tale 3)
1–2 more Shorts from the same episode, same shape as `short` (lines, `hook`, `title`). Each one is a
**different way in** — so we learn which angle and which first second works:
- a different **angle**: the creepiest rule or fact, a 'did you know' twist, the scariest single moment,
  or a question that splits the comments — not the same setup told again;
- a different **first picture**: line 1 must be a `scene` (or `img`), never `gumi`, and not the scene
  the main Short opens on (the checker compares them);
- its own `hook` (required, 2–7 words) and its own `title`.
Still never reveal the ending; the last line is Gumi sending viewers to the full tale.
They are released after the episode is public (Tue and Thu), so they can link to it.

## Done
Save as `output/tales/<NNN>_<slug>.json` (the `file` value from `next`), run the checker until ✅,
commit **only that file**, push to `routine/tales`.
