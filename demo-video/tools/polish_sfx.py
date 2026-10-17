"""Give the original effects clearer attacks without altering the story score."""
import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg

root = Path(__file__).resolve().parents[1] / "public/audio/sfx"
dest = root / "polished"
dest.mkdir(exist_ok=True)
for source in sorted(root.glob("*.wav")):
    if source.stem in {"blip", "check", "coin", "ding"}:
        filters = "highpass=f=110,lowpass=f=10000,equalizer=f=2400:t=q:w=0.8:g=1.5,volume=1.45"
    elif source.stem in {"stamp", "impact", "shield"}:
        filters = "highpass=f=55,equalizer=f=150:t=q:w=0.8:g=2,equalizer=f=1800:t=q:w=0.8:g=2,acompressor=threshold=0.28:ratio=2:attack=3:release=80:makeup=1.15"
    elif source.stem in {"whoosh", "scan"}:
        filters = "highpass=f=180,lowpass=f=8500,equalizer=f=2800:t=q:w=0.8:g=3,volume=1.25"
    else:
        shutil.copy2(source, dest / source.name)
        continue
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-i", str(source),
                    "-af", filters + ",alimiter=limit=0.88:level=false:latency=true",
                    "-c:a", "pcm_s16le", str(dest / source.name)], check=True)
print(f"Prepared {len(list(dest.glob('*.wav')))} effects; originals preserved.")
