# Resolution Agent film

- Active composition: `MintTown-Story`, ten scenes, 175.5 seconds, 30 fps. Keep the approved order and timing unless asked.
- Resolution Agent is the product; Mint Town is the setting. Ana is a resident affected by an illustrated phishing scam. Human fraud analysts verify the agent's work.
- DM Sans, mint/forest colors, vector graphics and original pixel residents. No app screenshots or model/provider names in the narration.
- `story-v2.json` is the script; `src/story/timing.json` pins voiced words to visual and sound cues. Use `word()`/`at()` for changes.
- Source only: no media is committed. Use `npm ci` and `npm run setup:media` once on a fresh clone, then `npm run check`, `npm run check:audio`, and `npm run dev -- --no-open`. Existing local media can be reused.
- Regenerate changed speech with `npm run voice`. This uses generic synthetic voices through Edge TTS; it makes no Gemini calls. Do not run cloud investigations to make video evidence.
- `npm run render` verifies speech, renders and checks the master. `tools/compress_submission.py` creates a separate under-20,000,000-byte copy; retain the master.
- Never commit videos, screenshots, voice caches, raw customer reports, credentials, node_modules or output folders. The illustrated amount is pinned to the saved synthetic case documented in README; no new live evidence is generated.
- Local archived compositions and captures are not part of the shared project. Preserve them on disk.
