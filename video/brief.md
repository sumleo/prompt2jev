# Hyperframes Composition Brief: prompt2jev

## Objective
Create a short launch-style brag video for prompt2jev, the agent skill and CLI that turns an LLM prompt into a TypeSafe Jev decision.

## Output
- Composition directory: `video/composition/`
- Rendered video: `video/prompt2jev-walkthrough.mp4`
- Format: landscape — 1920x1080
- Duration: 23.5 seconds

## Source Material
- Project root: the prompt2jev repository
- Primary files read: `README.md`, `README.zh.md`, `skills/prompt2jev/SKILL.md`, `examples/triage/request.json`, `examples/triage/triage.py`, `examples/triage/output.json`, `docs/install.md`, `.claude-plugin/plugin.json`, real output of `prompt2jev validate` and `prompt2jev setup`
- Product name: prompt2jev
- Tagline / strongest claim: "Turn an LLM prompt into a TypeSafe Jev decision your code can branch on." and "Jev judges; your code decides."
- Key UI or visual moment to recreate: the ticket prompt with three phrases highlighted, the three question cards, the terminal with the generated script, and the answer rows with probability bars
- Copy that must appear verbatim:
  - "Classify the support ticket into billing, shipping, or account. Set urgent=true if the customer cannot use the product or has a deadline today. If they ask for a refund, add refund=true. Output JSON only."
  - `team` · choice · "Which team should handle `ticket.text`?" · billing / shipping / account / other
  - `urgent` · noul · "Does `ticket.text` say the customer cannot use the product or has a deadline today?"
  - `refund_requested` · noul · "Does the customer in `ticket.text` explicitly ask for money back or a credit?"
  - `prompt2jev validate request.json --strict`, `prompt2jev code request.json --lang python --output triage.py`, `python3 triage.py`
  - The `triage.py` lines: the `typesafe_sdk` import, `# ----- Constants: every threshold in one place -----`, `CONFIDENCE_FLOOR = 0.5 ...`, `NOUL_YES = 0.8 ...`, `NOUL_NO = 0.2 ...`, `def decide(state) -> dict:` through `refund_requested = read_noul(answers["refund_requested"])`
  - "Nobody on my team can log in since this morning and payroll closes at 5pm."
  - account · 1.0 · confidence 0.99; yes · 0.98; no · 0.01; model jev-1.13.0
  - `--lang python`, `javascript`, `python-stdlib`, `curl`
  - "Jev judges." "Your code decides." · prompt2jev · github.com/sumleo/prompt2jev · Claude Code · Codex · OpenCode · Cursor · Gemini CLI

## Creative Direction
- Tone preset: polished
- Creative direction: a quiet terminal product film; the prompt dissolves into typed questions and a real JSON answer
- Interpretation: restrained type, dark violet-tinted canvas, hard cuts on beats, motion carried by typing, marker sweeps, and bars filling; no jokes, the real output is the confidence
- Angle: one prompt, three judgments. The README's ticket prompt is split on screen, validated, generated into a script, run, and answered with the real recorded probabilities. Everything on screen is lifted from the repo.
- Hook: the prompt card lands, "One prompt." slams in, three phrases light up in violet, teal, orange, "Three judgments." lands, "Output JSON only." is struck through
- Outro / punchline: "Jev judges." "Your code decides." then the wordmark and URL
- Avoid:
  - Generic SaaS language
  - Abstract filler visuals
  - Unrelated visual redesign
  - Any number, command, or sentence that is not in the repo or its recorded output

## Visual Identity
- Background: #0f0b1d; panels #171130; hairlines rgba(167,139,250,0.22)
- Text: #f4f1ff; muted #b3a8d6
- Accent: #7c3aed violet (fills), #a78bfa (violet text); #0d9488 / #2dd4bf teal; #ea580c / #fb923c orange
- Display font: Montserrat 900 (Hyperframes-embedded family)
- Body font: JetBrains Mono 400 / 700 (Hyperframes-embedded family)
- Visual references from the project: the README badge colors, the mono JSON and Python blocks, the CLI `$` lines

## Storyboard
Use the storyboard in `video/plan.md` as the creative contract.

Scene summary:
1. One prompt — 3.82s — prompt card, "One prompt.", three highlights, "Three judgments.", strike-through, split tags
2. Typed questions — 4.92s — three colored question cards one by one, validate command with real info line and exit 0
3. A script that runs — 4.37s — typed code command, generated script lines verbatim, four language chips
4. Probabilities, not prose — 6.55s — typed `python3 triage.py`, the ticket text, three answer rows with bars and count-ups, model line
5. Outro — 3.84s — "Jev judges." "Your code decides.", wordmark, URL, agent list

## Audio
- Audio role: warm bed with sparse professional accents
- Audio arc: bed fades in under the prompt, ticks and slides through the split and typing, three soft hits land the answers, one bell on the wordmark, bed fades out
- Music: `assets/music/happy-beats-business-moves-vol-12-by-ende-dot-app.mp3`
- Music treatment: volume 0.32, fade in over 0.6 s, fade out from 22.0 to 23.5 via a `data-automation` volume lane
- Music cue guidance: preset at `assets/music/cues/happy-beats-business-moves-vol-12-by-ende-dot-app.music-cues.json`; strong cues 8.74 / 13.11 / 19.66 / 22.37 for cuts and the wordmark; beat grid for highlights, cards, and rows as listed in the plan
- Audio-reactive treatment: subtle; per-frame data in `assets/audio-data.js` (extracted with the hyperframes-creative script, 30 fps, 16 bands, trimmed to 24 s); the background glow's scale and opacity follow bass and RMS
- Audio-coupled moments:
  - Scene 1 highlights — soft drop per sweep; muted impact under each headline line
  - Scene 2 cards — card slide per card; bong on `exit 0`
  - Scene 3 and 4 commands — randomized keypress ticks, thinned to every few characters
  - Scene 3 code — one soft impact when the file appears; a click per language chip
  - Scene 4 rows — soft impact, then two drops
  - Scene 5 — soft thud per line, one bell on the wordmark
- SFX selection guidance: low high-frequency-risk files only (`impactSoft_medium_*`, `drop_00*`, `bong_001`, `click2`, `keypress-*`); `card-slide-1` for the cards; `impactBell_heavy_000` once
- SFX analysis guidance: `<brag skill>/assets/sfx/sfx-analysis.md`
- Exact SFX choice: chosen after the animation existed; filenames, timestamps, and volumes are in `composition/index.html`
- Audio files: copied into `video/composition/assets/`

## Hyperframes Instructions
The composition follows `hyperframes-core` (standalone root, `data-*` timing, one paused timeline registered as `window.__timelines["main"]`, `fromTo` entrances, no `.clip` visibility tweens, finite repeats, no clocks or random), `hyperframes-animation` (marker highlight, stat bar fills, typewriter and count-up proxies, spring pops, varied eases), `hyperframes-creative` (audio-reactive per-frame sampling, video-scale type, layered background), `hyperframes-keyframes` (seek-safe GSAP, block-level transformed elements), and `hyperframes-cli` (`check` as the single gate, then `render`).

Requirements:
- Show at least one real UI, copy, or visual element from the source project.
- Keep all text readable in the final render.
- Keep the video within 15-25 seconds.
- Include the planned music/SFX layer.
- Treat cue metadata as timing hints; readability first.
- Use local assets for audio; no network fetch at render time.
- Run `hyperframes check` before render.
