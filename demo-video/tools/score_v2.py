"""Original cinematic score + sound effects for the revamped story. Pure numpy, no samples.

    python3 tools/score_v2.py

Writes public/audio/story2/score.wav (3:00, 48 kHz stereo) and public/audio/sfx/*.wav.
The score's section boundaries follow story-v2.json; word-synced hits live in the
scenes as separate SFX so they follow the voice timing.
"""
import json, wave
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SR = 48000
TOTAL = 180.0
rng = np.random.default_rng(7)
N = int(SR * TOTAL)
dry = np.zeros((2, N))
send = np.zeros((2, N))  # goes to reverb
TWO_PI = 2 * np.pi


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def hz(name):
    """'A3' -> Hz, 'C#4' -> Hz"""
    pitch, octave = name[:-1], int(name[-1])
    return midi(12 * (octave + 1) + NOTE[pitch])


def tt(dur):
    return np.arange(int(dur * SR)) / SR


def place(sig, at, gain=1.0, pan=0.0, wet=0.3, bus=None):
    """Add mono or stereo sig at time `at` (s)."""
    i = int(at * SR)
    if i >= N:
        return
    if sig.ndim == 1:
        l = np.cos((pan + 1) * np.pi / 4)
        r = np.sin((pan + 1) * np.pi / 4)
        sig = np.vstack([sig * l * 1.414, sig * r * 1.414])
    j = min(N, i + sig.shape[1])
    seg = sig[:, : j - i] * gain
    if i < 0:
        return
    dry[:, i:j] += seg * (1 - wet * 0.5)
    send[:, i:j] += seg * wet


def env(n, a=0.01, r=0.05):
    e = np.ones(n)
    na, nr = max(1, int(a * SR)), max(1, int(r * SR))
    na, nr = min(na, n), min(nr, n)
    e[:na] = np.linspace(0, 1, na)
    e[n - nr :] *= np.linspace(1, 0, nr)
    return e


def fft_filter(sig, lo=None, hi=None):
    S = np.fft.rfft(sig)
    f = np.fft.rfftfreq(len(sig), 1 / SR)
    g = np.ones_like(f)
    if lo:
        g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1)) ** 4)
    if hi:
        g *= 1 / np.sqrt(1 + (f / hi) ** 4)
    return np.fft.irfft(S * g, len(sig))


def sweep(sig, cut_fn, block=2048):
    """Time-varying lowpass via overlap-add STFT. cut_fn(t_seconds_array)->Hz."""
    hop = block // 2
    win = np.hanning(block)
    out = np.zeros(len(sig) + block)
    pad = np.concatenate([sig, np.zeros(block)])
    f = np.fft.rfftfreq(block, 1 / SR)
    for s in range(0, len(sig), hop):
        c = cut_fn(s / SR)
        g = 1 / np.sqrt(1 + (f / c) ** 6)
        out[s : s + block] += np.fft.irfft(np.fft.rfft(pad[s : s + block] * win) * g, block)
    return out[: len(sig)]


# ---------------------------------------------------------------- instruments
def saw_add(f, t, bright=8.0, nh=14, phase=0.0):
    out = np.zeros_like(t)
    for n in range(1, nh + 1):
        if f * n > 16000:
            break
        out += np.sin(TWO_PI * f * n * t + phase * n) / n * np.exp(-(n - 1) / bright)
    return out


def pad(notes, dur, bright=4.0, a=1.2, r=1.5, detune=0.006, voices=3):
    t = tt(dur)
    L = np.zeros_like(t)
    R = np.zeros_like(t)
    for nm in notes:
        f = hz(nm) if isinstance(nm, str) else nm
        for v in range(voices):
            d = 1 + detune * (v - (voices - 1) / 2)
            s = saw_add(f * d, t, bright, nh=10, phase=rng.uniform(0, 6.28))
            p = (v / max(1, voices - 1)) * 2 - 1
            L += s * (1 - p) * 0.5
            R += s * (1 + p) * 0.5
    e = env(len(t), a, r)
    k = 1 / (len(notes) * voices)
    return np.vstack([L * e * k, R * e * k])


def pluck(f, dur=0.6, ratio=4.0, index=2.2, decay=7.0):
    t = tt(dur)
    mod = np.sin(TWO_PI * f * ratio * t) * index * np.exp(-t * 18)
    s = np.sin(TWO_PI * f * t + mod) * np.exp(-t * decay)
    return s * env(len(t), 0.002, 0.05)


def bell(f, dur=3.0):
    t = tt(dur)
    mod = np.sin(TWO_PI * f * 3.5 * t) * 3.0 * np.exp(-t * 2.5)
    s = np.sin(TWO_PI * f * t + mod) * np.exp(-t * 1.6)
    s += 0.25 * np.sin(TWO_PI * f * 2.76 * t) * np.exp(-t * 3)
    return s * env(len(t), 0.002, 0.3)


def piano(f, dur=3.0, vel=1.0):
    t = tt(dur)
    s = np.zeros_like(t)
    for n in range(1, 9):
        fn = f * n * np.sqrt(1 + 0.0004 * n * n)
        s += np.sin(TWO_PI * fn * t) * (vel ** (n * 0.3)) / n ** 1.3 * np.exp(-t * (0.9 + n * 0.55))
    hammer = rng.standard_normal(len(t)) * np.exp(-t * 300) * 0.05
    return (s + hammer) * env(len(t), 0.003, 0.4)


def sub(f, dur, drive=1.6):
    t = tt(dur)
    s = np.sin(TWO_PI * f * t) + 0.25 * np.sin(TWO_PI * 2 * f * t)
    return np.tanh(s * drive) / np.tanh(drive) * env(len(t), 0.005, 0.06)


def kick(gain=1.0, low=45.0):
    t = tt(0.55)
    f = low + 120 * np.exp(-t * 30)
    ph = TWO_PI * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * 6.5)
    s += rng.standard_normal(len(t)) * np.exp(-t * 400) * 0.25
    return np.tanh(s * 1.5) * gain


def snare(gain=1.0):
    t = tt(0.35)
    n = rng.standard_normal(len(t))
    n = fft_filter(n, lo=900, hi=9000) * np.exp(-t * 16)
    tone = np.sin(TWO_PI * 185 * t) * np.exp(-t * 28) * 0.6
    return (n + tone) * gain


def clap(gain=1.0):
    t = tt(0.3)
    n = fft_filter(rng.standard_normal(len(t)), lo=1000, hi=7000)
    e = np.zeros_like(t)
    for d in (0, 0.011, 0.022):
        e += np.where(t >= d, np.exp(-(t - d) * 60), 0)
    e += np.exp(-t * 13) * 0.6
    return n * e * gain * 0.7


def hat(open_=False, gain=1.0):
    t = tt(0.25 if open_ else 0.06)
    n = fft_filter(rng.standard_normal(len(t)), lo=7000)
    return n * np.exp(-t * (14 if open_ else 70)) * gain


def tom(f=110, gain=1.0):
    t = tt(0.5)
    fr = f * (1 + 0.6 * np.exp(-t * 20))
    return np.sin(TWO_PI * np.cumsum(fr) / SR) * np.exp(-t * 7) * gain


def heartbeat(gain=1.0):
    a = kick(1.0, 38)[: int(0.4 * SR)]
    b = kick(0.6, 36)[: int(0.4 * SR)]
    out = np.zeros(int(0.75 * SR))
    out[: len(a)] += a
    i = int(0.26 * SR)
    out[i : i + len(b)] += b
    return fft_filter(out, hi=180) * gain


def tick(hi=True):
    t = tt(0.05)
    f = 3200 if hi else 2500
    return (np.sin(TWO_PI * f * t) * np.exp(-t * 160) + rng.standard_normal(len(t)) * np.exp(-t * 500) * 0.4) * 0.5


def riser(dur, lo=300, hi=9000, shepard=True):
    t = tt(dur)
    p = t / dur
    n = rng.standard_normal(len(t))
    n = sweep(n, lambda s: lo * (hi / lo) ** min(1, s / dur))
    s = n * (p ** 2.2) * 0.6
    if shepard:
        for k in range(4):
            base = 110 * 2 ** k
            f = base * 2 ** (p * 1.5)
            ph = TWO_PI * np.cumsum(f) / SR
            w = np.exp(-((np.log2(f / 440)) ** 2) * 0.8)
            s += np.sin(ph) * w * (0.15 + 0.5 * p ** 1.5) * 0.35
    return s * env(len(t), 0.05, 0.01)


def impact(gain=1.0, dur=4.0):
    t = tt(dur)
    f = 30 + 55 * np.exp(-t * 6)
    boom = np.sin(TWO_PI * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    crack = fft_filter(rng.standard_normal(len(t)), hi=5000) * np.exp(-t * 10) * 0.7
    metal = sum(np.sin(TWO_PI * fr * t) * np.exp(-t * 3) for fr in (287, 441, 619, 873)) * 0.06
    return np.tanh((boom * 1.4 + crack + metal) * 1.3) * gain


def reverse_swell(notes, dur):
    p = pad(notes, dur + 0.4, bright=6, a=0.01, r=0.01)
    p = p[:, : int(dur * SR)]
    shape = np.linspace(0, 1, p.shape[1]) ** 3
    n = fft_filter(rng.standard_normal(p.shape[1]), lo=2000) * shape * 0.15
    return p * shape + n


def strings_trem(notes, dur, rate=9.0, a=2.0, r=0.5):
    p = pad(notes, dur, bright=7, a=a, r=r, detune=0.009)
    t = tt(dur)
    trem = 0.65 + 0.35 * np.sin(TWO_PI * rate * t)
    return p * trem


def tape_stop(sig, dur):
    """Slow a stereo segment to a halt (pitch drop) over its own length."""
    n = sig.shape[1]
    t = np.arange(n) / n
    speed = (1 - t) ** 1.6
    pos = np.cumsum(speed)
    pos = np.clip(pos, 0, n - 1)
    return np.vstack([np.interp(pos, np.arange(n), ch) for ch in sig]) * (1 - t) ** 0.5


def chord(root, kind):
    iv = {"maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "maj": [0, 4, 7], "m": [0, 3, 7], "6": [0, 4, 7, 9], "add9": [0, 4, 7, 14], "madd9": [0, 3, 7, 14], "sus2": [0, 2, 7], "7": [0, 4, 7, 10]}[kind]
    r = 12 * (int(root[-1]) + 1) + NOTE[root[:-1]]
    return [midi(r + i) for i in iv]


# ---------------------------------------------------------------- arrangement helpers
def groove(start, end, bpm, prog, *, kick_pat="1_3", clap_on=False, hats=0, arp=None, arp_gain=0.18,
           sub_gain=0.32, pad_gain=0.22, pad_bright=4, cut=None, kick_gain=0.55, arp_rate=2, arp_wet=0.35):
    beat = 60 / bpm
    bar = beat * 4
    nbars = int(np.ceil((end - start) / bar))
    for b in range(nbars):
        t0 = start + b * bar
        if t0 >= end:
            break
        root, kind = prog[b % len(prog)]
        notes = chord(root, kind)
        seg = min(bar, end - t0)
        place(pad(notes, seg + 0.6, bright=pad_bright, a=0.25, r=0.6), t0, pad_gain, wet=0.45)
        bass = notes[0] / 2
        for e8 in range(8):
            ts = t0 + e8 * beat / 2
            if ts >= end:
                break
            place(sub(bass, beat / 2 * 0.9), ts, sub_gain * (1 if e8 % 2 == 0 else 0.7), wet=0.05)
        for q in range(4):
            ts = t0 + q * beat
            if ts >= end:
                break
            if kick_pat == "4" or (kick_pat == "1_3" and q in (0, 2)) or (kick_pat == "1" and q == 0):
                place(kick(), ts, kick_gain, wet=0.05)
            if clap_on and q in (1, 3):
                place(clap(), ts, 0.33, wet=0.35)
            if hats:
                for s in range(hats):
                    th = ts + s * beat / hats
                    if th < end:
                        place(hat(gain=0.6 if s % 2 else 0.35), th, 0.16, pan=0.3, wet=0.1)
        if arp:
            steps = int(4 * arp_rate)
            tones = notes + [notes[1] * 2, notes[2] * 2]
            for s in range(steps):
                ta = t0 + s * beat / arp_rate
                if ta >= end:
                    break
                f = tones[arp[s % len(arp)] % len(tones)] * 2
                g = arp_gain * (1.0 if s % 4 == 0 else 0.7)
                sig = pluck(f, 0.5, decay=8)
                if cut:
                    c = cut(ta)
                    sig = fft_filter(np.concatenate([sig, np.zeros(1024)]), hi=c)[: len(sig)]
                place(sig, ta, g, pan=0.35 * np.sin(s * 1.3), wet=arp_wet)


def birds(start, end):
    t = start + 0.6
    while t < end - 0.5:
        d = 0.14 + rng.uniform(0, 0.08)
        x = tt(d)
        f0 = rng.uniform(2600, 3800)
        chirp = np.sin(TWO_PI * np.cumsum(f0 + 1800 * np.sin(np.pi * x / d)) / SR) * np.sin(np.pi * x / d) ** 2
        place(chirp, t, 0.035, pan=rng.uniform(-0.8, 0.8), wet=0.5)
        if rng.uniform() < 0.5:
            place(chirp, t + d + 0.05, 0.025, pan=rng.uniform(-0.8, 0.8), wet=0.5)
        t += rng.uniform(1.4, 3.2)


def room(start, end, gain=0.012):
    n = fft_filter(rng.standard_normal(int((end - start) * SR)), hi=900) * env(int((end - start) * SR), 0.5, 0.5)
    place(n, start, gain, wet=0.0)


# ================================================================ THE SCORE
# 0-7  COLD OPEN: drone, heartbeat, reverse swell into a title slam at 3.8s
place(pad(["A1", "E2", "A2"], 4.2, bright=2, a=0.6, r=0.4), 0, 0.5, wet=0.4)
place(strings_trem(["A#4", "B4", "E5"], 3.9, rate=11, a=2.5, r=0.2), 0, 0.10, wet=0.6)
for i, at in enumerate([0.35, 1.15, 1.85, 2.45, 2.95, 3.35]):
    place(heartbeat(), at, 0.55 + 0.07 * i, wet=0.1)
place(reverse_swell(chord("A3", "m") + chord("A4", "m"), 1.5), 2.3, 0.6, wet=0.2)
place(impact(1.0, 4.0), 3.8, 0.95, wet=0.55)
place(pad(chord("A2", "madd9"), 3.4, bright=2.5, a=0.05, r=1.6), 3.8, 0.35, wet=0.6)
place(bell(hz("E5"), 2.5), 5.1, 0.12, pan=-0.2, wet=0.8)

# 7-22  MORNING: warm marimba groove, 96 BPM; tape-stop at the phone call
m0 = int(7 * SR)
morning_prog = [("C3", "maj7"), ("A2", "m7"), ("F2", "maj7"), ("G2", "6")]
groove(7.0, 9.6, 96, morning_prog, kick_pat="none", arp=[0, 2, 1, 3, 2, 4, 3, 5], arp_gain=0.15, sub_gain=0.0, pad_gain=0.2, arp_wet=0.4)
groove(9.5, 21.4, 96, morning_prog[1:] + morning_prog[:1], kick_pat="1_3", hats=4, arp=[0, 2, 1, 3, 2, 4, 3, 5], arp_gain=0.17, sub_gain=0.22, pad_gain=0.2, kick_gain=0.35, arp_wet=0.4)
birds(7.2, 21.2)
# tape stop 21.2 -> 22.0 (copy what was rendered, warp it, replace)
a, b = int(21.2 * SR), int(22.0 * SR)
for bus in (dry, send):
    seg = bus[:, a:b].copy()
    bus[:, a:b] = tape_stop(seg, 0.8)
    bus[:, b : b + int(1.2 * SR)] = 0  # clear morning tails after the stop

# 22-42  THE CALL: silence for the ring, then dread
room(22.0, 42.0, 0.010)
place(pad(["A1", "E2"], 15.0, bright=1.8, a=3.0, r=0.6), 24.6, 0.42, wet=0.3)
place(strings_trem(["A4", "A#4", "E5"], 13.6, rate=8, a=9.0, r=0.3), 25.8, 0.13, wet=0.6)
place(strings_trem(["A3", "A#3"], 9.0, rate=6, a=6.0, r=0.3), 30.4, 0.10, wet=0.5)
hb, rate = 31.6, 0.85
while hb < 39.2:
    place(heartbeat(), hb, 0.42 + (hb - 31.6) * 0.03, wet=0.1)
    hb += rate
    rate = max(0.58, rate * 0.95)
place(riser(4.0, 200, 6000), 37.2, 0.35, wet=0.3)
place(impact(0.6, 2.5), 41.3, 0.45, wet=0.5)  # the transfer lands: dull, wrong

# 42-53  AFTERMATH: lonely piano, ticking clock begins
place(pad(chord("A2", "madd9"), 11.0, bright=1.6, a=2.0, r=1.0), 42.3, 0.18, wet=0.6)
for at, nm, v in [(42.8, "A3", 0.6), (44.2, "E4", 0.5), (45.6, "C4", 0.5), (47.4, "B3", 0.45), (48.8, "A3", 0.5), (50.6, "E3", 0.45)]:
    place(piano(hz(nm), 3.5, v), at, 0.30 * v, pan=-0.15, wet=0.7)
for k in range(int((53 - 50.4) / 0.6) + 1):
    place(tick(k % 2 == 0), 50.4 + k * 0.6, 0.20, pan=0.25, wet=0.25)

# 53-77  STAKES: ticking pulse builds; silence before the pivot question
bpm, beat = 100, 0.6
for k in range(int((72.4 - 53.0) / beat)):
    place(tick(k % 2 == 0), 53.0 + k * beat, 0.20 + 0.0025 * k, pan=0.25, wet=0.25)
stakes_prog = [("A2", "m"), ("F2", "maj"), ("D2", "m"), ("E2", "maj")]
for b in range(8):
    t0 = 53.0 + b * 2.4
    if t0 >= 72.4:
        break
    root, kind = stakes_prog[b % 4]
    notes = chord(root, kind)
    place(pad(notes, min(2.4, 72.4 - t0) + 0.4, bright=2.5 + b * 0.35, a=0.4, r=0.4), t0, 0.08 + 0.02 * b, wet=0.5)
    for e8 in range(8):
        ts = t0 + e8 * 0.3
        if ts < 72.4 and t0 >= 55.4:
            place(sub(notes[0] / 2, 0.27), ts, 0.05 + 0.028 * b, wet=0.0)
    if t0 >= 62.6:
        for q in (0, 2):
            place(kick(), t0 + q * 0.6, 0.45, wet=0.05)
place(strings_trem(chord("A3", "m") + [hz("A#4")], 10.0, rate=10, a=8.0, r=0.1), 62.4, 0.10, wet=0.55)
for i, at in enumerate([69.0, 69.6, 70.2, 70.5, 70.8, 71.1, 71.4, 71.7, 71.85, 72.0, 72.15]):
    place(tom(90 + i * 6), at, 0.25 + i * 0.03, wet=0.3)
place(riser(4.6, 250, 10000), 67.8, 0.42, wet=0.3)
# hard cut at 72.4 is natural: everything above ends there. A single bell answers.
place(bell(hz("C6"), 4.0), 72.9, 0.16, wet=0.85)
place(pad(chord("C4", "add9"), 4.2, bright=3, a=1.4, r=0.4), 73.0, 0.13, wet=0.8)
place(reverse_swell(chord("A2", "m") + chord("A3", "m"), 1.4), 75.6, 0.55, wet=0.25)

# 77-114  ACT TWO: the agent works. Driving 100 BPM, filter opening.
place(impact(0.9, 3.0), 77.0, 0.75, wet=0.5)
act2 = [("A2", "m"), ("F2", "maj"), ("C3", "maj"), ("G2", "maj")]
cut = lambda s: 700 * (9000 / 700) ** min(1, max(0, (s - 77) / 36))
groove(77.0, 86.6, 100, act2, kick_pat="1_3", hats=2, arp=[0, 1, 2, 3, 2, 1, 4, 2], arp_rate=4, arp_gain=0.12, cut=cut, sub_gain=0.26, pad_gain=0.13, pad_bright=3)
groove(86.6, 105.4, 100, act2, kick_pat="4", clap_on=True, hats=4, arp=[0, 1, 2, 3, 2, 1, 4, 2], arp_rate=4, arp_gain=0.13, cut=cut, sub_gain=0.28, pad_gain=0.14, pad_bright=3.5, kick_gain=0.5)
# "Just over the line." - the floor drops out for a bar
place(pad(chord("A3", "madd9"), 2.6, bright=3, a=0.05, r=0.8), 105.4, 0.2, wet=0.7)
place(bell(hz("E5"), 2.5), 105.5, 0.10, wet=0.8)
groove(107.8, 113.6, 100, act2[2:] + act2[:2], kick_pat="4", clap_on=True, hats=4, arp=[0, 1, 2, 3, 2, 1, 4, 2], arp_rate=4, arp_gain=0.13, cut=cut, sub_gain=0.28, pad_gain=0.14, pad_bright=3.5, kick_gain=0.5)
for i in range(8):
    place(snare(0.5 + i * 0.06), 112.4 + i * 0.15, 0.22, wet=0.3)
place(riser(1.6, 400, 8000, shepard=False), 112.4, 0.25)

# 114-130  JUDGMENT: breakdown, a heartbeat-slow pulse, then the stamp blooms major
judg = [("F2", "maj7"), ("G2", "6"), ("A2", "m7"), ("A2", "m7")]
for b in range(4):
    t0 = 114.0 + b * 2.4
    place(pad(chord(*judg[b]), 2.9, bright=2.8, a=0.5, r=0.5), t0, 0.17, wet=0.6)
    place(kick(0.8, 40), t0, 0.32, wet=0.1)
    place(piano(chord(*judg[b])[2] * 2, 2.5, 0.5), t0 + 1.2, 0.13, wet=0.7)
place(riser(2.2, 300, 5000, shepard=False), 120.8, 0.22)
place(impact(0.8, 3.0), 122.9, 0.6, wet=0.55)
place(pad(chord("C3", "add9") + chord("C4", "maj7"), 7.4, bright=5, a=0.05, r=1.5), 122.9, 0.24, wet=0.7)
for i, nm in enumerate(["E5", "G5", "C6", "D6"]):
    place(bell(hz(nm), 2.5), 123.0 + i * 0.12, 0.07, pan=-0.5 + i * 0.33, wet=0.85)
groove(126.0, 130.0, 100, [("A2", "m7"), ("F2", "maj7")], kick_pat="none", arp=[0, 2, 1, 3, 2, 4, 3, 5], arp_rate=2, arp_gain=0.12, sub_gain=0.0, pad_gain=0.10)

# 130-148  LESSON: hopeful rebuild
lesson = [("C3", "maj"), ("G2", "maj"), ("A2", "m"), ("F2", "maj")]
groove(130.0, 134.8, 100, lesson, kick_pat="none", arp=[0, 2, 1, 3, 2, 4, 3, 5], arp_rate=2, arp_gain=0.14, sub_gain=0.18, pad_gain=0.15, pad_bright=4)
groove(134.8, 144.4, 100, lesson, kick_pat="1_3", hats=2, arp=[0, 2, 1, 3, 2, 4, 3, 5], arp_rate=4, arp_gain=0.12, sub_gain=0.24, pad_gain=0.15, pad_bright=4.5, kick_gain=0.45)
groove(144.4, 147.0, 100, [("F2", "maj"), ("E2", "maj")], kick_pat="4", clap_on=True, hats=4, arp=[0, 2, 1, 3], arp_rate=4, arp_gain=0.12, sub_gain=0.26, pad_gain=0.16, kick_gain=0.45)
place(pad(["A1", "E2"], 2.0, bright=1.5, a=0.05, r=1.0), 147.0, 0.35, wet=0.4)

# 148-170  INTERCEPT: the mirror. Same dread, bigger riser, then the hold.
room(148.0, 162.2, 0.010)
place(pad(["A1", "E2", "A2"], 14.4, bright=1.8, a=2.0, r=0.05), 148.0, 0.45, wet=0.3)
place(strings_trem(["A4", "A#4", "E5", "F5"], 9.6, rate=9, a=8.0, r=0.02), 152.6, 0.16, wet=0.6)
hb, rate = 152.6, 0.8
while hb < 161.9:
    place(heartbeat(), hb, 0.45 + (hb - 152.6) * 0.035, wet=0.1)
    hb += rate
    rate = max(0.42, rate * 0.94)
place(riser(9.6, 150, 12000), 152.6, 0.55, wet=0.25)
rt, step = 158.6, 0.15
while rt < 162.1:
    place(snare(0.4 + (rt - 158.6) * 0.18), rt, 0.2, wet=0.3)
    rt += step
    step = max(0.05, step * 0.9)
# 162.2-162.5 silence. 162.5: HOLD.
place(impact(1.0, 5.0), 162.5, 1.0, wet=0.6)
place(pad(chord("C3", "add9") + chord("G3", "maj") + [hz("E5")], 3.4, bright=7, a=0.02, r=1.2), 162.5, 0.38, wet=0.7)
for i, nm in enumerate(["C6", "E6", "G6", "C7", "G6", "E6"]):
    place(bell(hz(nm), 2.0), 162.55 + i * 0.07, 0.05, pan=-0.6 + i * 0.24, wet=0.9)
triumph = [("C3", "maj"), ("G2", "maj"), ("A2", "m"), ("F2", "maj")]
groove(163.3, 169.9, 100, triumph, kick_pat="4", clap_on=True, hats=4, arp=[0, 1, 2, 4, 2, 1, 3, 5], arp_rate=4, arp_gain=0.14, sub_gain=0.30, pad_gain=0.18, pad_bright=6, kick_gain=0.5)

# 170-180  RETURN: the morning motif comes home
groove(170.0, 175.0, 96, [("C3", "maj7"), ("F2", "maj7")], kick_pat="1", arp=[0, 2, 1, 3, 2, 4, 3, 5], arp_gain=0.16, sub_gain=0.16, pad_gain=0.2, kick_gain=0.25, arp_wet=0.45)
birds(170.2, 177.5)
place(pad(chord("C3", "add9") + chord("C4", "maj7"), 5.0, bright=4, a=0.1, r=3.5), 175.0, 0.3, wet=0.7)
place(sub(hz("C2"), 4.0, 1.2) * np.exp(-tt(4.0) * 0.8), 175.0, 0.3, wet=0.1)
for i, nm in enumerate(["G5", "C6", "E6"]):
    place(bell(hz(nm), 4.0), 175.05 + i * 0.25, 0.08, pan=-0.3 + i * 0.3, wet=0.85)


# ---------------------------------------------------------------- mixdown
def reverb(x, rt60=2.6, pre=0.02):
    n = int(rt60 * SR)
    t = np.arange(n) / SR
    out = np.zeros_like(x)
    for c in range(2):
        ir = rng.standard_normal(n) * np.exp(-6.9 * t / rt60)
        ir = fft_filter(ir, lo=200, hi=6500)
        ir[: int(pre * SR)] = 0
        ir /= np.sqrt(np.sum(ir ** 2))
        m = 1 << int(np.ceil(np.log2(len(x[c]) + n)))
        out[c] = np.fft.irfft(np.fft.rfft(x[c], m) * np.fft.rfft(ir, m), m)[: len(x[c])]
    return out


mix = dry + reverb(send) * 0.55
mix[:, -int(2.0 * SR) :] *= np.linspace(1, 0, int(2.0 * SR)) ** 1.5
mix[:, : int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))
mix = np.tanh(mix / np.max(np.abs(mix)) * 1.25) / np.tanh(1.25) * 0.89


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if data.ndim == 1:
        data = np.vstack([data, data])
    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2").T.copy()
    with wave.open(str(path), "wb") as w:
        w.setparams((2, 2, SR, 0, "NONE", "not compressed"))
        w.writeframes(pcm.tobytes())


write(ROOT / "public/audio/story2/score.wav", mix)

# ---------------------------------------------------------------- sound effects
def norm(x, peak=0.9):
    return x / (np.max(np.abs(x)) + 1e-9) * peak


def verb_tail(x, amt=0.3, rt=1.2):
    st = np.vstack([x, x]) if x.ndim == 1 else x
    pad_ = np.zeros((2, st.shape[1] + int(rt * SR)))
    pad_[:, : st.shape[1]] = st
    return pad_ + reverb(pad_, rt) * amt


sfx = {}
# phone ring: two-tone trill, two rings
t = tt(2.3)
trill = (np.sin(TWO_PI * 1300 * t) + np.sin(TWO_PI * 1650 * t)) * (np.sin(TWO_PI * 22 * t) > 0)
gate = ((t % 1.25) < 0.8).astype(float)
sfx["ring"] = verb_tail(norm(trill * gate * env(len(t), 0.01, 0.05), 0.5), 0.15, 0.6)
# whoosh (money leaves)
t = tt(0.9)
w = sweep(rng.standard_normal(len(t)), lambda s: 400 * (7000 / 400) ** (min(1, s / 0.9) ** 0.7))
sfx["whoosh"] = verb_tail(norm(w * np.sin(np.pi * t / 0.9) ** 2, 0.7), 0.3)
# sour ding (a sent payment that shouldn't have been)
t = tt(1.6)
sour = np.sin(TWO_PI * 880 * t) * np.exp(-t * 3) + 0.7 * np.sin(TWO_PI * 932 * t) * np.exp(-t * 3)
sfx["ding_sour"] = verb_tail(norm(sour * env(len(t), 0.002, 0.2), 0.5), 0.35)
# good ding
sfx["ding"] = verb_tail(norm(bell(hz("E6"), 1.4) + 0.6 * bell(hz("B6"), 1.4), 0.45), 0.35)
# hang-up tone: three short beeps
t = tt(1.4)
hb_ = np.sin(TWO_PI * 480 * t) * (((t % 0.45) < 0.22).astype(float))
sfx["hangup"] = norm(fft_filter(hb_, lo=300, hi=3400), 0.35)
# impact for statistics + stamps
sfx["impact"] = verb_tail(norm(impact(1.0, 2.5), 0.85), 0.35, 1.8)
sfx["thud"] = verb_tail(norm(np.concatenate([kick(1.0, 36), np.zeros(SR // 2)]), 0.8), 0.25)
# stamp: wood thump + paper slap
t = tt(0.35)
stamp = kick(1.0, 70)[: len(t)] * 0.8 + fft_filter(rng.standard_normal(len(t)), lo=500, hi=4000) * np.exp(-t * 40) * 0.7
sfx["stamp"] = verb_tail(norm(stamp, 0.9), 0.25, 0.8)
# UI blip (tool calls, checks)
t = tt(0.18)
blip = np.sin(TWO_PI * (1200 + 900 * t / 0.18) * t) * np.exp(-t * 22)
sfx["blip"] = verb_tail(norm(blip, 0.4), 0.2, 0.6)
t = tt(0.25)
sfx["check"] = verb_tail(norm(pluck(hz("G5"), 0.25) + pluck(hz("D6"), 0.25) * np.where(t > 0.07, 1, 0), 0.4), 0.25, 0.6)
# typing (report form)
typing = np.zeros(int(2.2 * SR))
pos = 0.0
while pos < 2.0:
    k = tt(0.03)
    c = fft_filter(rng.standard_normal(len(k)), lo=1500, hi=8000) * np.exp(-k * 250)
    i = int(pos * SR)
    typing[i : i + len(c)] += c * rng.uniform(0.5, 1)
    pos += rng.uniform(0.07, 0.16)
sfx["typing"] = norm(typing, 0.35)
# glitch (cold open text)
t = tt(0.5)
g = np.sign(np.sin(TWO_PI * rng.choice([90, 140, 230, 400]) * t)) * (rng.uniform(size=len(t)) > 0.3)
g = g * ((np.floor(t * 40) % 3) != 0)
sfx["glitch"] = norm(fft_filter(g.astype(float), hi=6000) * env(len(t), 0.005, 0.05), 0.35)
# shield bloom (payment held)
t = tt(1.8)
bloom = sum(np.sin(TWO_PI * hz(nm) * t) for nm in ["C5", "E5", "G5", "C6"]) * np.exp(-t * 1.8)
bloom += fft_filter(rng.standard_normal(len(t)), lo=4000) * np.exp(-t * 6) * 0.3
sfx["shield"] = verb_tail(norm(bloom * env(len(t), 0.01, 0.3), 0.6), 0.5, 1.6)
# scan sweep (evidence / footage)
t = tt(1.2)
scan = np.sin(TWO_PI * np.cumsum(500 + 2500 * (t / 1.2)) / SR) * 0.3 * np.sin(np.pi * t / 1.2)
sfx["scan"] = verb_tail(norm(scan + fft_filter(rng.standard_normal(len(t)), lo=3000) * 0.05, 0.3), 0.3)
# coin (legitimate payment completes)
t = tt(0.6)
coin = pluck(hz("B5"), 0.6, ratio=3, decay=6)
coin[int(0.08 * SR) :] += pluck(hz("E6"), 0.6 - 0.08, ratio=3, decay=6)
sfx["coin"] = verb_tail(norm(coin, 0.45), 0.3)

for name, data in sfx.items():
    write(ROOT / f"public/audio/sfx/{name}.wav", data)

# Preserve the approved continuous opening: original 7–22s stretched to 17.5s,
# followed directly by the remaining 22–180s. The compact asset is shared in Git.
import subprocess
import imageio_ffmpeg
subprocess.run([
    imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-i", str(ROOT / "public/audio/story2/score.wav"),
    "-filter_complex", "[0:a]atrim=start=7:end=22,asetpts=PTS-STARTPTS,atempo=0.857142857[intro];"
    "[0:a]atrim=start=22:end=180,asetpts=PTS-STARTPTS[body];[intro][body]concat=n=2:v=0:a=1[music]",
    "-map", "[music]", "-c:a", "libmp3lame", "-b:a", "192k", str(ROOT / "public/audio/story2/score-continuous.mp3"),
], check=True)
print("Score (180s) and", len(sfx), "sound effects written.")
