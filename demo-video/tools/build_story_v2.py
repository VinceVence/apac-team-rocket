"""Voice + caption builder for the revamped story (story-v2.json).

    uv run --project tools python tools/build_story_v2.py            # synthesize missing lines, then time them
    uv run --project tools python tools/build_story_v2.py --force    # re-synthesize every line
    python3 tools/build_story_v2.py --estimate                       # no network: placeholder timing only

Each line is spoken by its character voice (Edge TTS), the scammer is passed
through a phone-line filter, and any line longer than its `max` window is
time-stretched (atempo) to fit. Output:
  public/audio/story2/<id>.mp3     final per-line audio
  src/story/timing.json            scene-local word timing used by the film
  mint-town-story-v2.srt           subtitles
"""
import argparse, asyncio, hashlib, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = json.loads((ROOT / "story-v2.json").read_text())
AUDIO = ROOT / "public/audio/story2"
TIMING = ROOT / "src/story/timing.json"
MAX_STRETCH = 1.18
FILTERS = {
    "phone": "highpass=f=330,lowpass=f=3300,acompressor=threshold=-20dB:ratio=5:attack=5:release=60,acrusher=bits=11:mix=0.18,volume=1.5",
}


def ffmpeg():
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def duration_of(path: Path) -> float:
    raw = subprocess.run([ffmpeg(), "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = map(float, re.search(r"Duration: ([0-9:.]+)", raw).group(1).split(":"))
    return h * 3600 + m * 60 + s


def voice_for(line):
    return {**SCRIPT["voices"][line["speaker"]], **line.get("delivery", {})}


def key(line):
    v = voice_for(line)
    return hashlib.sha1(json.dumps([line["text"], v], sort_keys=True).encode()).hexdigest()[:10]


async def synthesize(lines, force):
    import truststore

    truststore.inject_into_ssl()
    import edge_tts

    for line in lines:
        raw = AUDIO / f"{line['id']}.raw.mp3"
        meta = AUDIO / f"{line['id']}.raw.jsonl"
        stamp = AUDIO / f"{line['id']}.key"
        if not force and raw.exists() and meta.exists() and stamp.exists() and stamp.read_text() == key(line):
            continue
        v = voice_for(line)
        com = edge_tts.Communicate(line["text"], v["voice"], rate=v["rate"], pitch=v["pitch"], boundary="WordBoundary")
        await com.save(str(raw), str(meta))
        stamp.write_text(key(line))
        print("voiced", line["id"], f"({line['speaker']})", flush=True)


def words_from_meta(line, meta: Path, rate: float):
    bounds = [json.loads(l) for l in meta.read_text().splitlines() if l.strip()]
    bounds = [b for b in bounds if b.get("type") == "WordBoundary"]
    display = line["text"].split()
    use_display = len(display) == len(bounds)
    out = []
    for i, b in enumerate(bounds):
        s = b["offset"] / 1e7 / rate
        e = (b["offset"] + b["duration"]) / 1e7 / rate
        out.append({"t": display[i] if use_display else b["text"], "s": round(s, 3), "e": round(e, 3)})
    return out


def estimate_words(text):
    toks = text.split()
    t, out = 0.12, []
    for w in toks:
        letters = len(re.sub(r"[^A-Za-z0-9]", "", w))
        d = 0.11 + 0.058 * letters
        out.append({"t": w, "s": round(t, 3), "e": round(t + d, 3)})
        t += d + 0.03 + (0.32 if re.search(r"[.?!:]$", w) else 0.16 if w.endswith(",") else 0)
    k = 0.83  # calibrated against the previous Andrew narration (actual / estimate)
    return [{"t": o["t"], "s": round(o["s"] * k, 3), "e": round(o["e"] * k, 3)} for o in out], t * k


def check_audio():
    """Never export placeholder captions as if narration were present."""
    timing = json.loads(TIMING.read_text())
    if timing.get("estimated"):
        raise SystemExit("Narration is still a silent preview. Run npm run voice first.")
    scenes = {s["id"]: s for s in SCRIPT["scenes"]}
    previous_end = {}
    for line in sorted(SCRIPT["lines"], key=lambda l: (scenes[l["scene"]]["start"], l["at"])):
        lid = line["id"]
        audio = AUDIO / f"{lid}.mp3"
        stamp = AUDIO / f"{lid}.key"
        if not audio.exists() or audio.stat().st_size < 1000 or not stamp.exists() or stamp.read_text() != key(line):
            raise SystemExit(f"Missing or stale narration: {lid}. Run npm run voice.")
        cue = timing["lines"][lid]
        duration = duration_of(audio)
        if cue["at"] != line["at"] or abs(cue["duration"] - duration) > 0.05 or not cue["words"]:
            raise SystemExit(f"Stale audio timing: {lid}. Run npm run voice.")
        if line["at"] < previous_end.get(line["scene"], 0) - 0.02 or line["at"] + duration > scenes[line["scene"]]["duration"] + 0.02:
            raise SystemExit(f"Overlapping or cut-off speech: {lid}.")
        previous_end[line["scene"]] = line["at"] + duration
    print(f"Narration verified: {len(SCRIPT['lines'])} voiced lines, no overlaps or cut-offs.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--estimate", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", action="store_true", help="Verify existing narration offline; never synthesize")
    args = ap.parse_args()
    if args.check:
        check_audio()
        return
    AUDIO.mkdir(parents=True, exist_ok=True)
    lines = SCRIPT["lines"]
    scenes = {s["id"]: s for s in SCRIPT["scenes"]}
    if not args.estimate:
        asyncio.run(synthesize(lines, args.force))

    timing, warnings = {"estimated": args.estimate, "lines": {}}, []
    for line in lines:
        if args.estimate:
            words, natural = estimate_words(line["text"])
            rate = max(1.0, natural / line["max"])
            words = [{"t": w["t"], "s": round(w["s"] / rate, 3), "e": round(w["e"] / rate, 3)} for w in words]
            dur = natural / rate
        else:
            raw = AUDIO / f"{line['id']}.raw.mp3"
            # The provider appends up to 1.4 s of silence even to "Hello".
            # Keep a short speech tail instead of speeding up silence or cutting the next speaker.
            meta = AUDIO / f"{line['id']}.raw.jsonl"
            bounds = [json.loads(v) for v in meta.read_text().splitlines() if v.strip()]
            ends = [(v["offset"] + v["duration"]) / 1e7 for v in bounds if v.get("type") == "WordBoundary"]
            if not ends:
                raise SystemExit(f"Missing speech timing: {line['id']}")
            natural = min(duration_of(raw), max(ends) + 0.24)
            rate = max(1.0, natural / line["max"])
            if rate > MAX_STRETCH:
                warnings.append(f"{line['id']}: needs {rate:.2f}x to fit {line['max']}s; capped at {MAX_STRETCH}x - shorten the text or widen the window")
                rate = MAX_STRETCH
            chain = [f"atrim=duration={natural:.4f}", "asetpts=PTS-STARTPTS"]
            filt = voice_for(line).get("filter")
            if filt:
                chain.append(FILTERS[filt])
            if rate > 1.001:
                chain.append(f"atempo={rate:.4f}")
            cmd = [ffmpeg(), "-y", "-v", "error", "-i", str(raw)]
            if chain:
                cmd += ["-af", ",".join(chain)]
            cmd += ["-ar", "48000", "-b:a", "192k", str(AUDIO / f"{line['id']}.mp3")]
            subprocess.run(cmd, check=True)
            dur = duration_of(AUDIO / f"{line['id']}.mp3")
            words = words_from_meta(line, AUDIO / f"{line['id']}.raw.jsonl", rate)
        timing["lines"][line["id"]] = {
            "scene": line["scene"],
            "speaker": line["speaker"],
            "at": line["at"],
            "duration": round(dur, 3),
            "rate": round(rate, 4),
            "words": [{"t": w["t"], "s": round(line["at"] + w["s"], 3), "e": round(line["at"] + w["e"], 3)} for w in words],
        }

    # Overlap / scene-fit checks
    by_scene = {}
    for line in lines:
        by_scene.setdefault(line["scene"], []).append(line)
    for sid, ls in by_scene.items():
        ls.sort(key=lambda l: l["at"])
        for a, b in zip(ls, ls[1:] + [None]):
            end = a["at"] + timing["lines"][a["id"]]["duration"]
            limit = b["at"] if b else scenes[sid]["duration"]
            if end > limit + 0.02:
                warnings.append(f"{a['id']}: ends at {end:.2f}s but next cue is {limit:.2f}s in '{sid}'")

    # Every visual cue in the scenes must point at a real spoken word.
    clean = lambda s: re.sub(r"[^a-z0-9-]", "", s.lower())
    for f in sorted((ROOT / "src/story").glob("*.tsx")):
        for lid, prefix in re.findall(r'word(?:End)?\("(\w+)",\s*"([^"]+)"', f.read_text()):
            ws = timing["lines"].get(lid, {}).get("words", [])
            p = clean(prefix)
            if not any(clean(w["t"]).startswith(p) or clean(w["t"]).startswith(p.split("-")[0]) for w in ws):
                warnings.append(f"{f.name}: cue word '{prefix}' not found in line {lid}")

    if warnings and not args.estimate:
        for warning in warnings:
            print("WARN", warning)
        raise SystemExit("Narration needs timing fixes; the previous preview is preserved.")
    TIMING.write_text(json.dumps(timing, indent=1) + "\n")

    def ts(sec):
        ms = round(sec * 1000)
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    names = {"ana": "ANA", "jun": "JUN", "scammer": "CALLER"}
    srt = []
    for line in sorted(lines, key=lambda l: scenes[l["scene"]]["start"] + l["at"]):
        base = scenes[line["scene"]]["start"]
        ws = timing["lines"][line["id"]]["words"]
        for i in range(0, len(ws), 7):
            g = ws[i : i + 7]
            text = " ".join(w["t"] for w in g)
            if line["speaker"] in names and i == 0:
                text = f"{names[line['speaker']]}: {text}"
            srt.append(f"{len(srt) + 1}\n{ts(base + g[0]['s'])} --> {ts(base + g[-1]['e'])}\n{text}\n")
    (ROOT / "mint-town-story-v2.srt").write_text("\n".join(srt))

    total = sum(s["duration"] for s in SCRIPT["scenes"])
    print(f"Timed {len(lines)} lines across {len(scenes)} scenes · film {total}s · {'ESTIMATED (silent preview)' if args.estimate else 'voiced'}")
    for w in warnings:
        print("WARN", w)
    if warnings and not args.estimate:
        sys.exit(1)


if __name__ == "__main__":
    main()
