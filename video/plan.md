# Brag Plan: prompt2jev

## What is this app?
prompt2jev is an agent skill plus a dependency-free CLI that turns an LLM prompt (a classifier, router, grader, or extractor that returns labels, booleans, or JSON fields) into a TypeSafe Jev decision: a `state`, atomic `choice` / `score` / `noul` questions, a validated request, and a generated script whose answers are probabilities the code can branch on.

## The angle
"One prompt. Three judgments." The video takes the README's own support-ticket prompt and shows it being split: three phrases in the prompt light up, become three typed questions, get validated, become a real Python script, and come back as real probabilities. Every word on screen is lifted from the repo: the prompt, the question texts from `examples/triage/request.json`, the constants and `decide()` lines from `examples/triage/triage.py`, the values from `examples/triage/output.json`, and the CLI commands from the README. Nothing is invented.

## Hook (first 2-3 seconds)
The 34-word ticket prompt lands in a mono card. "One prompt." slams in above it. Then three phrases inside the prompt get marker-highlighted one by one in violet, teal, and orange (the README badge colors): "billing, shipping, or account", "urgent=true", "refund=true". "Three judgments." lands with the third highlight. "Output JSON only." gets struck through: it is dropped because the answers are already typed.

## Key moments (the middle)
- Three question cards arrive one by one, colored to match the highlights: `team` (choice, options billing / shipping / account / other), `urgent` (noul), `refund_requested` (noul). The real `prompt2jev validate request.json --strict` line prints its real info message and `exit 0`.
- `prompt2jev code request.json --lang python --output triage.py` types itself, and the generated script's constants block and `decide()` reveal line by line, exactly as in `triage.py`. Four language chips: `--lang python`, `javascript`, `python-stdlib`, `curl`.
- `python3 triage.py` types itself against the ticket "Nobody on my team can log in since this morning and payroll closes at 5pm." Three answer rows fill in with bars and count-ups: team → account 1.00 (confidence 0.99), urgent → yes 0.98, refund_requested → no 0.01, model jev-1.13.0.

## Outro / punchline
"Jev judges." / "Your code decides." (the README's opening line). Then the wordmark ⚡ prompt2jev, `github.com/sumleo/prompt2jev`, and the agents it works with: Claude Code · Codex · OpenCode · Cursor · Gemini CLI.

## User flow worth showing
Entry: paste a prompt → key action: the skill writes and validates a request, then generates a script → result: run the script and read typed probabilities. Scenes 2 to 4 are that flow, shown as the CLI actually behaves.

## Tone
- Preset: polished
- Creative direction: a quiet terminal product film; the prompt dissolves into typed questions and a real JSON answer
- Interpretation: restrained type, dark violet-tinted canvas, hard cuts on beats, motion carried by typing, marker sweeps, and bars filling; humor is absent, confidence comes from real output.

## Format: landscape — 1920x1080
## Duration: 23.5 seconds

## Visual identity (from the project)
- Background: #0f0b1d (near-black tinted toward the badge violet); panels #171130
- Accent: #7c3aed violet (README skill badge); secondary #0d9488 teal (archetypes badge) and #ea580c orange (MIT badge); brighter text variants #a78bfa / #2dd4bf / #fb923c for contrast on dark
- Text: #f4f1ff; muted #b3a8d6
- Display font: Montserrat 900 (embedded by Hyperframes; the repo has no web font)
- Body font: JetBrains Mono 400 / 700 for everything the product itself says (prompt, questions, commands, code, output)
- Strongest visual element: the ticket prompt turning into three colored questions, and the answer rows with probability bars

## Share copy (draft)
Introducing prompt2jev: turn an LLM prompt into a TypeSafe Jev decision your code can branch on. One prompt becomes three typed questions, a validated request, a script that runs, and probabilities instead of prose.

## Audio direction
- Role: warm bed with sparse professional accents
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3` (steady and clean, 109.96 BPM)
- Music treatment: starts at 0 with a 0.6 s fade-in at 0.32 volume, holds, fades out over the last 1.5 s under the wordmark
- Music cue guidance: preset read from `assets/music/cues/happy-beats-business-moves-vol-12-by-ende-dot-app.music-cues.md`. Strong cues to target: 8.74 s (cards collapse, cut to the code scene), 13.11 s (cut to the run scene), 19.66 s (cut to the outro), 22.37 s (wordmark). Beat-grid windows: highlights at 1.09 / 1.64 / 2.19; question cards at 4.91 / 6.00 / 7.09 (every other beat, each holds over a second); answer rows at 14.73 / 15.84 / 16.93 (every other beat).
- Audio-reactive treatment: subtle; the background radial glow breathes with bass and RMS (scale 1 to 1.1, opacity 0.2 to 0.36). No waveform or equalizer visuals.
- SFX posture: sparse, motion-matched, low high-frequency risk
- Audio-coupled moments: marker sweeps (soft drops), typed commands (randomized key ticks, thinned to every few characters), card arrivals (card slide), answer rows (soft impacts), wordmark (one bell)
- Restraint rule: no sound on every code line; no stacked hits; SFX never above 0.6 volume; the bell rings once

## Storyboard

### Scene 1 — One prompt — 3.82s (0.00 to 3.82)
Dark canvas, violet glow breathing top-right. Kicker "prompt.txt · 34 words". The prompt card enters at 0.2 s with the full ticket prompt in mono. "One prompt." slams in at 0.56. Marker highlights sweep at 1.09 (violet, "billing, shipping, or account"), 1.64 (teal, "urgent=true"), 2.19 (orange, "refund=true"); "Three judgments." lands at 2.19. At 2.73 "Output JSON only." is struck through. A split row at the bottom pops a tag per instruction: choice, noul, noul, drop (the split-table categories from SKILL.md).
Sequential/interaction: yes — three highlights then one strike, each with a matching bottom tag
Audio intent: quiet arrival, three soft ticks that feel like decisions being made
Audio-coupled idea: soft drop per highlight, a muted thud under each headline line
Music: bed fades in
Transition mood: hard cut on the beat → Scene 2

### Scene 2 — Typed questions — 4.92s (3.82 to 8.74)
Headline "prompt2jev splits it into typed questions." Three cards arrive one by one at 4.91, 6.00, 7.09 with their color from Scene 1: `choice` / `team` / "Which team should handle `ticket.text`?" with chips billing, shipping, account, other; `noul` / `urgent` / "Does `ticket.text` say the customer cannot use the product or has a deadline today?"; `noul` / `refund_requested` / "Does the customer in `ticket.text` explicitly ask for money back or a credit?". At 7.64 the bottom line types `$ prompt2jev validate request.json --strict`, then prints the real info line and `exit 0` at 8.19.
Sequential/interaction: yes — cards one by one, then a typed command with a result
Audio intent: three card slides, one warm confirmation
Audio-coupled idea: card slide per card, key ticks under the command, a bong on exit 0
Transition mood: hard cut on the 8.74 strong cue → Scene 3

### Scene 3 — A script that runs — 4.37s (8.74 to 13.11)
Headline "Then a script that runs." A terminal card. `$ prompt2jev code request.json --lang python --output triage.py` types from 9.0 to 9.8. At 9.83 the generated file reveals line by line: the import, the constants block (CONFIDENCE_FLOOR, NOUL_YES, NOUL_NO with their real comments), and `decide()` down to the three `read_*` lines, verbatim from `examples/triage/triage.py`. At 11.46 four chips pop: `--lang python`, `javascript`, `python-stdlib`, `curl`. A caret blinks throughout.
Sequential/interaction: yes — typed command, staggered code lines, four chips
Audio intent: keyboard texture, one soft landing when the code appears, four tiny clicks
Audio-coupled idea: key ticks every few characters, soft impact at 9.83, clicks on chips
Transition mood: hard cut on the 13.11 strong cue → Scene 4

### Scene 4 — Probabilities, not prose — 6.55s (13.11 to 19.66)
Headline "Probabilities, not prose." Left: a terminal types `$ python3 triage.py` (13.3 to 13.85), then shows the state it judges: kicker `EXAMPLE_STATE · ticket.text` and the sentence "Nobody on my team can log in since this morning and payroll closes at 5pm." at 14.20. Right: three answer rows arrive at 14.73, 15.84, 16.93. Each has the question id, the answer word in its color, a bar that fills, and a count-up: team → account, bar to 1.00, "P(account) 1.00 · confidence 0.99"; urgent → yes, bar to 0.98, "P(yes) 0.98 · band yes"; refund_requested → no, bar to 0.01, "P(yes) 0.01 · band no". Footer at 18.02: `model jev-1.13.0`. Holds to 19.66. This is the poster frame (around 18.9 s).
Sequential/interaction: yes — typed command, then rows one by one with bars and counters
Audio intent: the payoff; each row lands with weight but stays polite
Audio-coupled idea: key ticks, soft impacts per row, count-ups silent
Transition mood: hard cut on the 19.66 strong cue → Scene 5

### Scene 5 — Outro — 3.84s (19.66 to 23.50)
"Jev judges." at 19.75, "Your code decides." at 20.75, big display type anchored left. At 22.37 (strong cue) the wordmark block rises bottom-right: a violet bolt, `prompt2jev`, `github.com/sumleo/prompt2jev`, and "Claude Code · Codex · OpenCode · Cursor · Gemini CLI". Music fades out under it.
Sequential/interaction: two lines, then the wordmark
Audio intent: resolve; one bell, then silence
Audio-coupled idea: soft thud per line, one bell on the wordmark
Transition mood: hold to black-free end (last frame is the wordmark)

**Music mood for this video:** steady, clean, upbeat-but-restrained
**Audio summary:** a warm bed fades in under the prompt, sparse ticks and slides follow the split and the typing, three soft hits land the answers, one bell rings the name, and the bed fades out.
