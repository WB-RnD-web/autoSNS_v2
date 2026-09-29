# Nine Tails Tales — how to write one episode

You are writing **one** episode script for the English YouTube channel **Nine Tails Tales**
(Korean and East Asian myths, monsters and ghost stories for viewers aged 13–30 worldwide).
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
3. `{"card": "TALE 00N", "sub": "<short tale name>"}`
4. **3–4 chapters**, each opened by `{"card": "I", "sub": "…"}` (II, III…). Background/lore first,
   then the tale proper with rising tension, then what it means / how Korea (or Japan/China) tells it today.
5. **Ending**: Gumi's personal answer or reflection → teaser for **next week's catalog entry**
   (use its `angle`) → sign-off in one line (vary it; a callback to the cold open is best).

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
- Tell the setup and the turn; **do not reveal the ending** — the last line is Gumi
  (`"gumi": "wink"`) sending viewers to the full tale.
- Reuse pictures by `scene` key; `title` ≤100 chars ending with `#shorts`.

## Done
Save as `output/tales/<NNN>_<slug>.json` (the `file` value from `next`), run the checker until ✅,
commit **only that file**, push to `routine/tales`.
