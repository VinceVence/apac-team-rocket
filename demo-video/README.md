# Resolution Agent — product film

**2:55.5 · 1920×1080 · 30 fps · English · H.264/AAC**

**Resolution Agent is the product. Mint Town is the fictional demonstration setting.**

The compact submission is `out/resolution-agent-case-first.mp4` (720p H.264/AAC, strictly below 20,000,000 bytes). The updated full-quality source is `out/resolution-agent-case-first-master.mp4`. Both keep the same 175.5-second story. The bridge asks whether there is a faster way to resolve Ana’s case. A calendar illustrates days passing, and Ana reacts in a close-up. The closing is **“Close the gap. From report to resolution.”**

The revised YouTube export is `out/resolution-agent-youtube-4k.mp4`: **3840×2160, 30 fps**, with the same **175.5-second** story. Ana says “Oh no... my money’s gone!” and the calendar advances through days **1, 4, 7**. Earlier MP4s remain unchanged. Recreate the source render with `npm run render:youtube -- --browser-executable="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"`. Media files stay local and out of GitHub. The retained duration is the user's explicit choice; it is below the submission form's stated three-minute minimum.

To recreate the small copy from a mastered export, choose a new destination filename:

```sh
uv run --project tools --locked python tools/compress_submission.py out/resolution-agent-case-first-master.mp4 out/resolution-agent-case-first.mp4
uv run --project tools --locked python tools/verify_video.py --story-v2 --film out/resolution-agent-case-first.mp4 --width 1280 --height 720 --max-bytes 20000000
```

The encoder uses two passes with a 19 MB target, retains the complete video and 128 kbps AAC audio, and rejects an oversized output. It never overwrites the master. Do not run `--master` on this compressed copy; master the full-quality file first.

Open `MintTown-Story` in Remotion Studio. Each chapter is its own composition under **Story-scenes**. The GitHub project contains the current vector story. Earlier compositions and captures remain archived locally and are not published.

## Source-only handoff

GitHub contains code, narration scripts and timing, with no videos, audio, fonts or generated media. Existing local media is preserved. On a fresh clone, run `npm ci`, then `npm run setup:media` to copy the app’s licensed fonts/logo, synthesize the original score/effects locally, and generate generic voices through Edge TTS. This does not call Gemini or require Google Cloud credentials. Then run `npm run check`, `npm run check:audio`, and `npm run dev -- --no-open`.

## Finish the film on your Mac (one command)

```sh
npm ci                # first time only
npm run story         # voices every line, re-times captions + cues, type-checks, renders out/mint-town-story-v2.mp4
```

Once local media is prepared, `npm run story` runs `npm run voice` (Edge TTS → `public/audio/story2/*.mp3`, auto time-stretch to fit each line's window, `src/story/timing.json`, `mint-town-story-v2.srt`), then `npm run check` and `npm run render`. The render hooks verify narration first, then master the exported audio with headroom and verify the final 1080p film. If a line is too long for its window, the voice step stops and names it; shorten the text in `story-v2.json` or widen its `max`. To avoid a Chrome download, append `-- --browser-executable="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"` to `npm run render`.

Until the voices are generated, Studio plays a silent preview with estimated captions (`npm run voice:preview`). `npm run render` checks for real, current voice tracks and rejects silent placeholders, overlapping speech, and cut-off lines.

## How it fits together

- `story-v2.json`: the whole script. Scenes (fixed start/duration, totaling 175.5 s), voices, and every line with its speaker, start offset (`at`) and maximum length (`max`). Optional per-line `delivery` overrides rate/pitch, so Ana can be tentative before the scam and urgent afterward.
- `src/story/script.ts`: cue helpers. Scenes call `word("line_id", "word")` so visuals and sound effects follow the voice timing after any re-voice.
- `src/story/Voice.tsx`: per-line audio, speaker-aware captions (CALLER / ANA / JUN chips, spoken-word highlight), sound effect placement, music ducking under every line.
- `src/story/*.tsx`: one file per chapter: `Cold`, `Morning`, `Call`, `After`, `Stakes`, `Investigate`, `Model`, `Judgment`, `Lesson`, `Intercept`, `Return`. `Kit.tsx` and `CallPhone.tsx` hold shared motion pieces.
- `tools/score_v2.py` → `public/audio/story2/score.wav` + `public/audio/sfx/*.wav`: original score and effects, synthesized in numpy (`npm run score`). No samples or borrowed melodies.
- `tools/polish_sfx.py` → `public/audio/sfx/polished/`: clearer attacks and controlled effect levels, retaining the original files. Run after regenerating the score. The scene highlights and audio accents take cues from the local `ds-agent-video` reference; its brand assets and soundtrack are not used.

### The arc

| Start | Story beat |
|---|---|
| 0:00.0 | Meet Ana |
| 0:17.5 | The phishing message |
| 0:37.5 | A customer needs help |
| 0:48.5 | Why it matters |
| 1:12.5 | Resolution Agent |
| 1:31.5 | Models as tools |
| 1:49.5 | Helping the fraud analyst |
| 2:05.5 | Learning from reviewed cases |
| 2:23.5 | Protecting the next customer |
| 2:45.5 | Resolution Agent |

## What the film can substantiate

Case **SC-a1a870cc4e** called `get_case_evidence`, `score_models`, then `submit_case_resolution`. The `ledger_transaction_v1` classifier returned **0.705251 vs 0.700**, pinned to receipt **PRED-d210179fb60f02520955**. The draft cited it, passed local contract checks, and received **simulated** analyst approval. The prevention agent's approved narrow rule stopped a changed-recipient ₱900 attempt with **zero debit and zero journal entries**. A legitimate control settled. The original run used four AI calls and no retries.

The source world and evaluations are synthetic. Scores are uncalibrated advisory signals. No production accuracy, guaranteed recovery, or measured analyst time reduction is claimed. Local judges validate contracts and references, not factual certainty. Source traces were recorded on October 17, 2026; the film is not a new live investigation.

See `PRODUCTION.md` for rules, source links and credits, and `SUBMISSION.md` for upload and evaluation checks. No public upload or competition submission has been made.

The phishing text, fake wallet page, and customer complaint are an illustrated adaptation. Vector agent scenes reproduce saved system receipts from the earlier bank-impersonation case; they do not claim a new live phishing investigation. The approved safe-account plus secrecy pattern and changed-recipient hold are backed by that saved run. Narration and resident dialogue use synthetic voices. Screen time is editorial, not measured latency. No screenshots are used in the active story composition.
