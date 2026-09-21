# The README video

`prompt2jev-walkthrough.mp4` is the 23-second walkthrough linked at the top of both READMEs. It
follows the [end-to-end example](../README.md#example) from prompt to real answers, and
every line on screen is lifted from this repository:

| On screen | Source |
|---|---|
| The support-ticket prompt | the usage prompt in `README.md` |
| The three questions, their types, and the `team` options | `examples/triage/request.json` |
| `prompt2jev validate ...`, `prompt2jev code ...`, `python3 triage.py` | the commands in `README.md` |
| The constants block and `decide()` | `examples/triage/triage.py` |
| account 1.00 / confidence 0.99, urgent yes 0.98, refund no 0.01, `jev-1.13.0` | `examples/triage/output.json` |
| "Jev judges. Your code decides." | the first line of the README overview |

`tests/test_skill.py` checks that the composition still contains that material, so a
change to the example files fails the tests until the video is updated and re-rendered.

## Files

```
video/
  prompt2jev-walkthrough.mp4         the rendered video, 1920x1080, 23.5 s; frame 0 is the poster
  prompt2jev-walkthrough-poster.jpg  the poster frame (the answers panel at 18.9 s)
  plan.md                            the creative plan and beat-by-beat storyboard
  brief.md                           the composition brief handed to Hyperframes
  share-copy.txt                     a caption for posting the video
  composition/                       the Hyperframes project
    index.html                       scenes, timeline, audio cues
    assets/audio-data.js             per-frame music energy that drives the background glow
    assets/sfx/                      the sound effects used (Kenney, CC0)
    assets/music/cues/               beat grid and strong cues of the music track
```

The music track itself, `assets/music/happy-beats-business-moves-vol-12-by-ende-dot-app.mp3`,
is not committed: it ships with the [brag](https://github.com/latent-spaces/brag) skill under
`skills/brag/assets/music/`, and its license is documented there, not here. Copy it into
`composition/assets/music/` before rendering.

## Re-render

Needs Node 22+, FFmpeg, and Chrome. The composition pins `hyperframes@0.8.50`.

```bash
cd video/composition
npx hyperframes@0.8.50 check                                   # lint, runtime, layout, contrast
npx hyperframes@0.8.50 render --quality delivery --output ../prompt2jev-walkthrough.mp4
cd ..
ffmpeg -y -ss 18.9 -i prompt2jev-walkthrough.mp4 -frames:v 1 -q:v 2 prompt2jev-walkthrough-poster.jpg       # poster
ffmpeg -y -i prompt2jev-walkthrough.mp4 -i prompt2jev-walkthrough-poster.jpg \
  -filter_complex "[0:v][1:v]overlay=0:0:enable='eq(n,0)'[v]" \
  -map "[v]" -map '0:a?' -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p \
  -c:a copy -movflags +faststart prompt2jev-walkthrough.poster.mp4 && mv prompt2jev-walkthrough.poster.mp4 prompt2jev-walkthrough.mp4
```

The last step replaces frame 0 with the poster so thumbnails show the answers panel
everywhere; playback is unaffected. `npx hyperframes@0.8.50 preview` opens the timeline
in the browser for edits.

## Credits

Made with the [brag](https://github.com/latent-spaces/brag) skill and
[Hyperframes](https://hyperframes.heygen.com/). Music: "Happy Beats / Business Moves" vol. 12
by [ende.app](https://ende.app/en). Sound effects: [Kenney](https://kenney.nl/) and
[Keyboard Soundpack #1](https://opengameart.org/content/keyboard-soundpack-1-typing-and-single-keystrokes)
by unicae_games, both CC0.
