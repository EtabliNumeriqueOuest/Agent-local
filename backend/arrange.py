# /// script
# requires-python = "==3.11.*"
# dependencies = ["basic-pitch", "demucs", "librosa", "music21", "soundfile", "setuptools<81"]  # setuptools: basic-pitch pins resampy<0.4.3, which imports pkg_resources
# ///
"""Arrange an electronic track as a score of arpeggio, pad chords and sub bass: MIDI, MusicXML and PDF.

The track is split into stems first so drums never become notes. Pads are read from Basic Pitch's
frame activations, which see held notes that have no attack, and written as one chord per
harmonic section. The sub bass is tracked from the bass stem's spectrum. Plucked notes with a
clear attack form the arpeggio staff.
"""

import argparse
import copy
import subprocess
from pathlib import Path
from statistics import median

import librosa
import numpy as np
import soundfile as sf
from basic_pitch import ICASSP_2022_MODEL_PATH
from basic_pitch.inference import Model, predict, run_inference
from music21 import chord, clef, harmony, instrument, key, layout, metadata, meter, note, pitch, stream, tempo

GRID = 4  # quantization steps per quarter note (sixteenth notes)
HOP = 128  # onset envelope hop in samples
PHASE_BINS = 48  # subdivisions of one beat used to locate the beat
PAD_RANGE = (48, 84)  # C3 to C6
PAD_VOICES = 6
PAD_CLASSES = 4
PAD_SPLIT = 60  # middle C: pad notes at or above it go to the right-hand staff
ARP_LOWEST = 60
ARP_VOICES = 2
CHORD_CHANGE_PENALTY = 0.05  # template-fit cost of starting a new chord section
OUT_OF_KEY_PENALTY = 0.01  # per chord tone outside the key, breaks ties toward diatonic chords
BASS_LOWEST = 21  # A0
BASS_SLOTS_PER_BEAT = 2
BASS_GATE_DB = -35  # bass stem level below which the bass rests
BASS_SMOOTH_SLOTS = 5
BASS_MIN_SLOTS = 2  # shorter notes are blips from a quiet bass crossing the gate
BASS_STAFF_BOTTOM = 43  # G2

NAMES = "C Db D Eb E F Gb G Ab A Bb B".split()
QUALITIES = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10), "maj7": (0, 4, 7, 11),
             "sus2": (0, 2, 7), "sus4": (0, 5, 7)}
TEMPLATES = [{(root + i) % 12 for i in intervals} for root in range(12) for intervals in QUALITIES.values()]
TEMPLATE_NAMES = [NAMES[root] + quality for root in range(12) for quality in QUALITIES]
KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
SCALES = {"major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10)}


def separate(audio: Path, stem_dir: Path) -> dict[str, Path]:
    """Split the track into drums, bass and other (vocals folded into other), cached as FLAC."""
    paths = {name: stem_dir / f"{name}.flac" for name in ("drums", "bass", "other")}
    if all(p.exists() for p in paths.values()):
        return paths
    import torch
    from demucs.api import Separator

    stem_dir.mkdir(parents=True, exist_ok=True)
    separator = Separator(model="htdemucs", device="mps" if torch.backends.mps.is_available() else "cpu")
    _, stems = separator.separate_audio_file(audio)
    stems["other"] = stems["other"] + stems.pop("vocals")
    for name, path in paths.items():
        sf.write(path, stems[name].cpu().numpy().T, separator.samplerate)
    return paths


def detect_tempo(audio: Path, bpm: float | None) -> tuple[float, float]:
    """Return the tempo in BPM and the time of the first beat in seconds, assuming a constant tempo.

    librosa's estimate is quantized to whole lags of the onset envelope, about 1% apart at this hop,
    enough to push notes off the grid within a few bars, so it is refined to 0.01 BPM by finding the
    constant pulse that best matches the onsets over the whole track. The beat falls where the
    onsets, folded over one beat, peak.
    """
    y, sr = librosa.load(audio, sr=22050, mono=True)
    onsets = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    times = np.arange(len(onsets)) * HOP / sr
    if bpm is None:
        coarse = librosa.feature.tempo(onset_envelope=onsets, sr=sr, hop_length=HOP)[0]
        centered = onsets - onsets.mean()
        pulse = lambda b: abs(centered @ np.exp(2j * np.pi * times * b / 60))
        bpm = float(max(np.arange(0.94 * coarse, 1.06 * coarse, 0.01), key=pulse))
    beat = 60 / bpm
    bins = (times % beat / beat * PHASE_BINS).astype(int)
    profile = np.bincount(bins, weights=onsets, minlength=PHASE_BINS) / np.bincount(bins, minlength=PHASE_BINS)
    return bpm, (profile.argmax() + 0.5) / PHASE_BINS * beat


def align_to_notes(starts: np.ndarray, bpm: float, phase: float) -> float:
    """Move the beat phase by up to half a grid step to where the note onsets cluster.

    Detected note onsets sit at a constant offset from the onset-envelope beat; quantizing on the
    envelope grid would put the rounding boundary inside that cluster and split it in two.
    """
    step = 60 / bpm / GRID
    return phase + np.angle(np.exp(2j * np.pi * (starts - phase) / step).mean()) / (2 * np.pi) * step


def detect_key(profile: np.ndarray) -> key.Key:
    """Krumhansl-Schmuckler: the key whose profile best correlates with the pitch-class profile."""
    _, root, mode = max((np.corrcoef(profile, np.roll(ks, r))[0, 1], r, mode) for r in range(12)
                        for mode, ks in (("major", KS_MAJOR), ("minor", KS_MINOR)))
    return key.Key(NAMES[root], mode)


def pitch_classes(bars: np.ndarray) -> np.ndarray:
    """Fold per-bar activations over the 88 piano keys into normalized 12-bin pitch-class profiles."""
    profile = np.zeros((len(bars), 12))
    for k in range(88):
        profile[:, (k + 21) % 12] += bars[:, k]
    return profile / np.maximum(np.linalg.norm(profile, axis=1, keepdims=True), 1e-9)


def chord_sections(bars: np.ndarray, k: key.Key) -> list[tuple[int, int, str]]:
    """Split the bars into harmonic sections: Viterbi over chord templates with a cost per change.

    Returns (first bar, end bar, template chord name) per section.
    """
    templates = np.array([[pc in tones for pc in range(12)] for tones in TEMPLATES], float)
    templates /= np.linalg.norm(templates, axis=1, keepdims=True)
    scale = {p.pitchClass for p in k.getPitches()}
    fit = pitch_classes(bars) @ templates.T - OUT_OF_KEY_PENALTY * np.array([len(t - scale) for t in TEMPLATES])
    score, back = fit[0].copy(), np.zeros(fit.shape, int)
    for b in range(1, len(fit)):
        best = score.argmax()
        stay = score >= score[best] - CHORD_CHANGE_PENALTY
        back[b] = np.where(stay, np.arange(len(score)), best)
        score = np.where(stay, score, score[best] - CHORD_CHANGE_PENALTY) + fit[b]
    labels = [int(score.argmax())]
    for b in range(len(fit) - 1, 0, -1):
        labels.append(back[b][labels[-1]])
    labels.reverse()
    starts = [b for b in range(len(labels)) if b == 0 or labels[b] != labels[b - 1]]
    return [(b, e, TEMPLATE_NAMES[labels[b]]) for b, e in zip(starts, starts[1:] + [len(labels)])]


def pad_voicing(mean: np.ndarray) -> tuple[int, ...]:
    """The held pitches of a section.

    Pitch classes come first so octave doublings cannot crowd out a chord tone: the strongest
    classes at least half as loud as the loudest pitch, at most PAD_CLASSES, each at its strongest
    octave. Other octaves of those classes that are as loud fill the voicing up to PAD_VOICES.
    """
    lo, hi = PAD_RANGE
    strength = {m: mean[m - 21] for m in range(lo, hi)}
    floor = 0.5 * max(strength.values())
    best: dict[int, int] = {}
    for m in strength:
        if m % 12 not in best or strength[m] > strength[best[m % 12]]:
            best[m % 12] = m
    classes = sorted((pc for pc in best if strength[best[pc]] >= floor), key=lambda pc: strength[best[pc]], reverse=True)[:PAD_CLASSES]
    core = [best[pc] for pc in classes]
    doublings = sorted((m for m in strength if m % 12 in classes and m not in core and strength[m] >= floor), key=strength.get, reverse=True)
    return tuple(sorted(core + doublings[:PAD_VOICES - len(core)]))


def pads(activations: np.ndarray, fps: float, phase: float, bar: float, k: key.Key) -> list[tuple[int, int, tuple[int, ...], str]]:
    """Return (first bar, bar count, MIDI pitches, chord symbol) per pad chord, merging equal neighbours.

    The symbol names the voicing itself, or the section's template chord when music21 cannot name it.
    """
    nbars = int((len(activations) / fps - phase) // bar)
    bars = np.array([activations[int((phase + b * bar) * fps):int((phase + (b + 1) * bar) * fps)].mean(0)
                     for b in range(nbars)])
    chords = []
    for start, end, template in chord_sections(bars, k):
        voicing = pad_voicing(bars[start:end].mean(0))
        if chords and chords[-1][2] == voicing:
            chords[-1] = (chords[-1][0], end - chords[-1][0], voicing, chords[-1][3])
            continue
        figure = harmony.chordSymbolFigureFromChord(chord.Chord([spell(m, k) for m in voicing]))
        chords.append((start, end - start, voicing, template if figure == "Chord Symbol Cannot Be Identified" else figure))
    return chords


def bass_line(path: Path, bpm: float, phase: float) -> list[tuple[float, float, int]]:
    """Return (offset, length, MIDI pitch) in quarter notes for the sub bass.

    Each slot takes the pitch whose first four harmonics carry the most energy, so a sub whose
    fundamental is quieter than its overtones is still read at its own octave. Slots are smoothed
    by majority vote, and neighbouring notes an octave apart are merged at the octave that lasts
    longer: note attacks briefly read an octave high.
    """
    y, sr = librosa.load(path, sr=22050)
    hop = 512
    spec = np.abs(librosa.cqt(y, sr=sr, hop_length=hop, fmin=librosa.midi_to_hz(BASS_LOWEST), n_bins=60))
    times = np.arange(spec.shape[1]) * hop / sr
    span = 36
    # offsets 12/19/24 semitones are harmonics 2-4; weights fall as 1/h, a steeper 1/h**gamma (gamma > 1) would trust the fundamental more
    salience = sum(spec[o:o + span] / h for h, o in ((1, 0), (2, 12), (3, 19), (4, 24)))
    # ref=np.max: levels are deltas from the loudest frame, so BASS_GATE_DB is relative to this stem's peak
    level = librosa.amplitude_to_db(spec.sum(0), ref=np.max)
    slot = 60 / bpm / BASS_SLOTS_PER_BEAT
    slots = []
    for s in range(int((times[-1] - phase) // slot)):
        sel = (times >= phase + s * slot) & (times < phase + (s + 1) * slot)
        slots.append(int(BASS_LOWEST + salience[:, sel].mean(1).argmax()) if level[sel].mean() > BASS_GATE_DB else None)
    # mode filter, not an EWMA: averaging MIDI numbers, whatever the alpha, would invent pitches between two notes
    half = BASS_SMOOTH_SLOTS // 2
    voted = []
    for s, p in enumerate(slots):
        window = [q for q in slots[max(0, s - half):s + half + 1] if q is not None]
        voted.append(max(set(window), key=window.count) if p is not None else None)

    runs = []  # [first slot, slot count, pitch]
    for s, p in enumerate(voted):
        if p is not None and runs and runs[-1][2] == p and sum(runs[-1][:2]) == s:
            runs[-1][1] += 1
        elif p is not None:
            runs.append([s, 1, p])
    merged = []
    for run in runs:
        prev = merged[-1] if merged else None
        if prev and sum(prev[:2]) == run[0] and prev[2] % 12 == run[2] % 12:
            prev[2] = prev[2] if prev[1] > run[1] else run[2] if run[1] > prev[1] else min(prev[2], run[2])
            prev[1] += run[1]
        else:
            merged.append(run)
    return [(s / BASS_SLOTS_PER_BEAT, n / BASS_SLOTS_PER_BEAT, p) for s, n, p in merged if n >= BASS_MIN_SLOTS]


def arpeggio(notes, bpm: float, phase: float) -> list[tuple[float, float, int]]:
    """Return (offset, length, MIDI pitch) in quarter notes for plucked notes, at most ARP_VOICES per step."""
    beat = 60 / bpm
    plucks = [(s, e, p, a) for s, e, p, a, _ in notes if p >= ARP_LOWEST and e - s < beat]
    phase = align_to_notes(np.array([s for s, *_ in plucks]), bpm, phase)
    steps: dict[int, dict[int, tuple[float, int]]] = {}
    for s, e, p, a in plucks:
        step = round((s - phase) / beat * GRID)
        if step >= 0 and a > steps.setdefault(step, {}).get(p, (0.0, 0))[0]:
            steps[step][p] = (a, max(1, round((e - s) / beat * GRID)))
    kept = []
    for step, by_pitch in sorted(steps.items()):
        for p, (_, length) in sorted(by_pitch.items(), key=lambda item: item[1][0], reverse=True)[:ARP_VOICES]:
            kept.append((step / GRID, length / GRID, p))
    return kept


def spell(midi: int, k: key.Key) -> pitch.Pitch:
    """Spell a MIDI pitch with the key's note names, or with flats in a flat key.

    The result is rebuilt from its name: pitches made from MIDI numbers carry an explicit natural
    accidental that music21 would otherwise print on repeated notes.
    """
    p = pitch.Pitch(midi)
    in_key = {s.name for s in k.getPitches()}
    chosen = next((c for c in (p, *p.getAllCommonEnharmonics()) if c.name in in_key), None)
    if chosen is None:
        chosen = p.getEnharmonic() if k.sharps < 0 and p.alter > 0 else p
    return pitch.Pitch(chosen.nameWithOctave)


def staff(name: str, events, k: key.Key, staff_clef: clef.Clef) -> stream.Part:
    """Build one staff from (offset, length, MIDI pitches) events, merging simultaneous notes into chords."""
    part = stream.Part()
    part.partName = name
    part.insert(0, instrument.Instrument(instrumentName=name))
    for offset, length, pitches in events:
        part.insert(offset, chord.Chord([spell(m, k) for m in pitches], quarterLength=length))
    notated = part.chordify() if events else part
    notated.partName = name
    notated.insert(0, meter.TimeSignature("4/4"))
    notated.insert(0, key.KeySignature(k.sharps))
    notated.insert(0, staff_clef)
    return notated.makeNotation()


def bass_clef(pitches: list[int]) -> clef.Clef:
    """A bass clef shifted down one or two octaves so the line's median sits on the staff."""
    c = clef.BassClef()
    c.octaveChange = -min(2, max(0, -(-(BASS_STAFF_BOTTOM - int(median(pitches))) // 12))) if pitches else 0
    return c


def build_score(chords, bass, arp, k: key.Key, bpm: float, title: str, composer: str) -> stream.Score:
    bar_q = 4.0
    pad_rh = [(b * bar_q, n * bar_q, [m for m in v if m >= PAD_SPLIT]) for b, n, v, _ in chords]
    pad_lh = [(b * bar_q, n * bar_q, [m for m in v if m < PAD_SPLIT]) for b, n, v, _ in chords]
    parts = [
        staff("Arp", [(o, l, [p]) for o, l, p in arp], k, clef.TrebleClef()),
        staff("Pad", [e for e in pad_rh if e[2]], k, clef.TrebleClef()),
        staff("Pad", [e for e in pad_lh if e[2]], k, clef.BassClef()),
        staff("Sub bass", [(o, l, [p]) for o, l, p in bass], k, bass_clef([p for _, _, p in bass])),
    ]
    for pad in parts[1:3]:
        pad.partName = ""  # the brace carries the name once
    for b, _, _, figure in chords:
        parts[0].measure(b + 1).insert(0, harmony.ChordSymbol(figure))
    parts[0].measure(1).insert(0, tempo.MetronomeMark(number=round(bpm)))
    score = stream.Score()
    score.metadata = metadata.Metadata(movementName=title, composer=composer)
    for part in parts:
        score.insert(0, part)
    score.insert(0, layout.StaffGroup(parts[1:3], name="Pad", symbol="brace"))
    return score


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("audio", type=Path)
    parser.add_argument("outdir", type=Path)
    parser.add_argument("--title", default=None)
    parser.add_argument("--composer", default="")
    parser.add_argument("--bpm", type=float, help="override the detected tempo")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    stem = args.audio.stem
    stems = separate(args.audio, args.outdir / "stems")
    bpm, phase = detect_tempo(args.audio, args.bpm)
    bar = 4 * 60 / bpm

    model = Model(ICASSP_2022_MODEL_PATH)
    activations = run_inference(str(stems["other"]), model)["note"]
    fps = len(activations) / librosa.get_duration(path=stems["other"])
    profile = pitch_classes(activations.mean(0, keepdims=True))[0]
    k = detect_key(profile)
    _, _, notes = predict(str(stems["other"]), model, onset_threshold=0.6, frame_threshold=0.3, minimum_note_length=60)

    chords = pads(activations, fps, phase, bar, k)
    bass = bass_line(stems["bass"], bpm, phase)
    arp = arpeggio(notes, bpm, phase)
    print(f"Key {k}, {bpm:.2f} BPM, first beat {phase:.3f} s: {len(chords)} pad chords, {len(bass)} bass notes, {len(arp)} arp notes")
    print("Pads:", " | ".join(f"bar {b + 1}: {figure} x{n}" for b, n, _, figure in chords))

    score = build_score(chords, bass, arp, k, bpm, args.title or stem, args.composer)
    playable = copy.deepcopy(score)  # music21 would play chord symbols as held notes
    for symbol in list(playable.recurse().getElementsByClass(harmony.ChordSymbol)):
        symbol.activeSite.remove(symbol)
    playable.write("midi", fp=args.outdir / f"{stem}.mid")
    xml = score.write("musicxml", fp=args.outdir / f"{stem}.musicxml")
    ly = args.outdir / f"{stem}.ly"
    subprocess.run(["musicxml2ly", "--no-beaming", "-o", str(ly), str(xml)], check=True)
    subprocess.run(["lilypond", "--pdf", "-o", str(args.outdir / stem), str(ly)], check=True)
    print(f"Wrote {args.outdir / stem}.pdf")


if __name__ == "__main__":
    main()
