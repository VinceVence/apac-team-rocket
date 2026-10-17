"""Create a complete 720p H.264/AAC copy strictly below 20 decimal MB."""
import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("destination", type=Path)
args = parser.parse_args()
source, dest = args.source.resolve(), args.destination.resolve()
assert source != dest, "Keep the full-quality master"
assert source.is_file() and not dest.exists(), "Use a fresh output filename"
compositor = root / "node_modules/@remotion/compositor-darwin-arm64"
probe = json.loads(subprocess.check_output([
    str(compositor / "ffprobe"), "-v", "error", "-show_format", "-of", "json", str(source)
], env=dict(os.environ, DYLD_LIBRARY_PATH=str(compositor))))
duration = float(probe["format"]["duration"])
assert 0 < duration <= 180.1
# Target 19 MB, leaving a full MB for muxing/encoder variance. No duration truncation.
audio_bitrate = 128_000
video_bitrate = int(19_000_000 * 8 / duration - audio_bitrate)
assert video_bitrate > 400_000
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
dest.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="submission-", dir=dest.parent) as tmp:
    log = str(Path(tmp) / "pass")
    pending = Path(tmp) / "submission.mp4"
    common = [ffmpeg, "-y", "-v", "warning", "-i", str(source), "-map", "0:v:0",
              "-vf", "scale=1280:720:flags=lanczos", "-c:v", "libx264", "-preset", "slow",
              "-b:v", str(video_bitrate), "-pix_fmt", "yuv420p", "-passlogfile", log]
    print(f"Two-pass encode: {video_bitrate} bps video + 128 kbps audio; {duration:.3f}s", flush=True)
    subprocess.run(common + ["-pass", "1", "-an", "-f", "null", os.devnull], check=True)
    subprocess.run(common + ["-pass", "2", "-map", "0:a:0", "-c:a", "aac", "-b:a", str(audio_bitrate),
                            "-movflags", "+faststart", str(pending)], check=True)
    assert pending.stat().st_size < 20_000_000, "Output is over 20 MB; master preserved"
    pending.rename(dest)
print(f"Submission: {dest.stat().st_size:,} bytes ({dest.stat().st_size / 1e6:.2f} MB)")
