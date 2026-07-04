"""Audio-driven mouth curves for phoneme-accurate, *intensity-accurate* lip-sync.

The viseme timeline (visemes.py) says WHICH mouth shape; these curves say
HOW MUCH and EXACTLY WHEN, measured from the synthesized audio itself:

  energy  - overall loudness envelope (0..1)
  jaw     - voiced/low-band energy -> jaw opening
  close   - silence detector -> lips actually close between words
  spread  - high-band (fricative s/sh/f) dominance -> lip corners spread
  round   - low-band dominance while voiced -> rounding (o/u) bias

Pure stdlib (wave/array/math): works offline, adds ~milliseconds per turn.

Neural upgrade hook: drop an ONNX audio->blendshape model into
``models/lipsync.onnx`` and ``pip install onnxruntime`` - ``neural_curves``
below is the single integration point (returns None until both exist).
"""

from __future__ import annotations

from array import array
import math
from pathlib import Path
import wave

from companion_core.contracts import TTSResult

CURVE_FPS = 50  # 20ms hop
MAX_ANALYZE_SECONDS = 90.0


def mouth_curves_for_tts(tts: TTSResult) -> dict | None:
    """Analyze the cached WAV of a TTS result. None for non-WAV/mock refs."""
    audio_ref = tts.audio_ref or ""
    if not audio_ref.startswith("file://") or not audio_ref.endswith(".wav"):
        return None
    path = Path(audio_ref.removeprefix("file://"))
    if not path.is_file():
        return None

    neural = neural_curves(path)
    if neural is not None:
        return neural

    samples, sample_rate = _read_wav_mono(path)
    if not samples or sample_rate <= 0:
        return None
    return curves_from_pcm(samples, sample_rate)


def neural_curves(path: Path) -> dict | None:
    """ONNX audio->blendshape kancasi (ixtiyoriy kuchaytirish).

    models/lipsync.onnx mavjud bo'lsa va onnxruntime o'rnatilgan bo'lsa,
    shu yerda ishga tushiriladi; aks holda None -> DSP tahlil ishlaydi.
    Kutilayotgan kontrakt: model 16kHz mono float PCM oladi, chiqishi
    (frames, blendshapes) bo'lib, natija quyidagi dict formatiga o'giriladi.
    """
    model_path = _repo_root() / "models" / "lipsync.onnx"
    if not model_path.is_file():
        return None
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return None
    # Model topilgan holat: integratsiya keyingi bosqichda modelning aniq
    # kirish/chiqish sxemasiga qarab yoziladi. Hozircha xavfsiz fallback.
    return None


def curves_from_pcm(samples: list[float], sample_rate: int) -> dict | None:
    """Spectral-envelope mouth curves from mono float samples (-1..1)."""
    max_samples = int(MAX_ANALYZE_SECONDS * sample_rate)
    if len(samples) > max_samples:
        samples = samples[:max_samples]
    hop = max(1, sample_rate // CURVE_FPS)
    if len(samples) < hop * 3:
        return None

    # Bir o'tishli bir-qutbli filtrlar: past (~900Hz) va yuqori (~3.2kHz).
    low = _one_pole_lowpass(samples, sample_rate, 900.0)
    mid = _one_pole_lowpass(samples, sample_rate, 3200.0)

    n_frames = len(samples) // hop
    energy_raw: list[float] = []
    low_raw: list[float] = []
    high_raw: list[float] = []
    f0_raw: list[float] = []
    for i in range(n_frames):
        a = i * hop
        b = a + hop
        energy_raw.append(_rms(samples, a, b))
        low_raw.append(_rms(low, a, b))
        high_raw.append(_rms_diff(samples, mid, a, b))
        # Qo'pol F0: lowpass signalning nol kesishmalaridan (prosodiya konturi).
        f0_raw.append(_zero_cross_f0(low, a, b, sample_rate))

    e_scale = _percentile(energy_raw, 0.95) or 1e-6
    l_scale = _percentile(low_raw, 0.95) or 1e-6

    energy: list[float] = []
    jaw: list[float] = []
    close: list[float] = []
    spread: list[float] = []
    rounde: list[float] = []
    for i in range(n_frames):
        e = min(1.0, energy_raw[i] / e_scale)
        lo = min(1.0, low_raw[i] / l_scale)
        # Spektral balans XOM qiymatlardan: normalizatsiya nisbatni buzadi.
        ratio_hi = high_raw[i] / (high_raw[i] + low_raw[i] + 1e-9)

        energy.append(e)
        # Jag' asosan past chastota (unli) energiyasidan ochiladi.
        jaw.append(min(1.0, (lo ** 0.75) * (0.35 + 0.65 * e)))
        # Sukut -> lablar yopiq (so'zlar orasida og'iz ochiq qolib ketmasin).
        close.append(1.0 if e < 0.055 else 0.0)
        # Frikativlar (s, sh, f): yuqori chastota ustun, umumiy energiya past-o'rta.
        spread.append(min(1.0, max(0.0, (ratio_hi - 0.55) * 2.2) * (0.3 + 0.7 * e)))
        # Yumaloq unlilar (o, u): kuchli past chastota + yuqori deyarli yo'q.
        rounde.append(min(1.0, max(0.0, (0.42 - ratio_hi) * 2.0) * lo))

    # Pitch konturi (prosodiya -> qosh/bosh): ovozli kadrlarda median atrofidagi
    # og'ish, yarim tonlarda; 0.5 = neytral, 1.0 = ~+5 yarim ton.
    voiced_f0 = [
        f0_raw[i]
        for i in range(n_frames)
        if energy[i] > 0.15 and 70.0 <= f0_raw[i] <= 450.0
    ]
    median_f0 = _percentile(voiced_f0, 0.5) if voiced_f0 else 0.0
    pitch: list[float] = []
    prev_pitch = 0.5
    for i in range(n_frames):
        if median_f0 > 0 and energy[i] > 0.15 and 70.0 <= f0_raw[i] <= 450.0:
            semitones = 12.0 * math.log2(f0_raw[i] / median_f0)
            value = min(1.0, max(0.0, 0.5 + semitones / 10.0))
            prev_pitch = value
        else:
            prev_pitch += (0.5 - prev_pitch) * 0.25  # jimlikda neytralga qaytadi
        pitch.append(prev_pitch)

    # Asimmetrik silliqlash: tez hujum, yumshoq qaytish (tabiiy artikulyatsiya).
    for curve, up, down in (
        (energy, 0.55, 0.35),
        (jaw, 0.5, 0.3),
        (close, 0.45, 0.25),
        (spread, 0.5, 0.3),
        (rounde, 0.45, 0.28),
        (pitch, 0.4, 0.4),
    ):
        _smooth_inplace(curve, up, down)

    q = lambda xs: [round(x, 3) for x in xs]  # noqa: E731 - JSON hajmi uchun
    return {
        "fps": CURVE_FPS,
        "energy": q(energy),
        "jaw": q(jaw),
        "close": q(close),
        "spread": q(spread),
        "round": q(rounde),
        "pitch": q(pitch),
    }


class StreamingMouthAnalyzer:
    """Inkremental og'iz-egri-chiziq tahlili (streaming TTS uchun).

    curves_from_pcm bilan bir xil egri chiziqlar, lekin filtr/silliqlash
    holatini saqlab, har chunk uchun faqat YANGI kadrlarni qaytaradi.
    Normalizatsiya to'liq klip o'rniga oqib boruvchi cho'qqi bilan.
    """

    def __init__(self, sample_rate: int) -> None:
        self.sr = max(8000, int(sample_rate))
        self.hop = max(1, self.sr // CURVE_FPS)
        self._alpha_low = 1.0 - math.exp(-2.0 * math.pi * 900.0 / self.sr)
        self._alpha_mid = 1.0 - math.exp(-2.0 * math.pi * 3200.0 / self.sr)
        self._low_y = 0.0
        self._mid_y = 0.0
        self._residual: list[float] = []
        self._e_scale = 0.08  # oqib boruvchi cho'qqi (past floor bilan)
        self._l_scale = 0.06
        self._smooth = {k: 0.0 for k in ("energy", "jaw", "close", "spread", "round")}
        self._smooth["pitch"] = 0.5
        self._voiced_f0: list[float] = []
        self._median_f0 = 0.0

    def feed(self, pcm: bytes) -> dict | None:
        if not pcm:
            return None
        data = array("h")
        data.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
        self._residual.extend(s / 32768.0 for s in data)
        if len(self._residual) < self.hop:
            return None

        out = {k: [] for k in ("energy", "jaw", "close", "spread", "round", "pitch")}
        n_frames = len(self._residual) // self.hop
        for f in range(n_frames):
            frame = self._residual[f * self.hop : (f + 1) * self.hop]
            sum_e = sum_lo = sum_hi = 0.0
            crossings = 0
            prev_low = self._low_y
            for x in frame:
                self._low_y += self._alpha_low * (x - self._low_y)
                self._mid_y += self._alpha_mid * (x - self._mid_y)
                d = x - self._mid_y
                sum_e += x * x
                sum_lo += self._low_y * self._low_y
                sum_hi += d * d
                if (prev_low < 0.0) != (self._low_y < 0.0):
                    crossings += 1
                prev_low = self._low_y
            n = len(frame)
            rms_e = math.sqrt(sum_e / n)
            rms_lo = math.sqrt(sum_lo / n)
            rms_hi = math.sqrt(sum_hi / n)
            self._e_scale = max(self._e_scale, rms_e)
            self._l_scale = max(self._l_scale, rms_lo)

            e = min(1.0, rms_e / self._e_scale)
            lo = min(1.0, rms_lo / self._l_scale)
            ratio_hi = rms_hi / (rms_hi + rms_lo + 1e-9)

            f0 = crossings * self.sr / (2.0 * n)
            if e > 0.15 and 70.0 <= f0 <= 450.0:
                if len(self._voiced_f0) < 60:
                    self._voiced_f0.append(f0)
                    self._median_f0 = _percentile(self._voiced_f0, 0.5)
                pitch_v = (
                    min(1.0, max(0.0, 0.5 + 12.0 * math.log2(f0 / self._median_f0) / 10.0))
                    if self._median_f0 > 0
                    else 0.5
                )
            else:
                pitch_v = self._smooth["pitch"] + (0.5 - self._smooth["pitch"]) * 0.25

            raw = {
                "energy": e,
                "jaw": min(1.0, (lo ** 0.75) * (0.35 + 0.65 * e)),
                "close": 1.0 if e < 0.055 else 0.0,
                "spread": min(1.0, max(0.0, (ratio_hi - 0.55) * 2.2) * (0.3 + 0.7 * e)),
                "round": min(1.0, max(0.0, (0.42 - ratio_hi) * 2.0) * lo),
                "pitch": pitch_v,
            }
            for key, (up, down) in _SMOOTH_RATES.items():
                y = self._smooth[key]
                x = raw[key]
                k = up if x > y else down
                y += k * (x - y)
                self._smooth[key] = y
                out[key].append(round(y, 3))

        self._residual = self._residual[n_frames * self.hop :]
        out["fps"] = CURVE_FPS
        return out


_SMOOTH_RATES = {
    "energy": (0.55, 0.35),
    "jaw": (0.5, 0.3),
    "close": (0.45, 0.25),
    "spread": (0.5, 0.3),
    "round": (0.45, 0.28),
    "pitch": (0.4, 0.4),
}


def _read_wav_mono(path: Path) -> tuple[list[float], int]:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    if width != 2 or channels < 1:
        return [], 0
    raw = array("h")
    raw.frombytes(frames[: len(frames) - (len(frames) % 2)])
    if channels > 1:
        mono = [
            sum(raw[i + c] for c in range(channels)) / channels / 32768.0
            for i in range(0, len(raw) - channels + 1, channels)
        ]
    else:
        mono = [s / 32768.0 for s in raw]
    return mono, rate


def _one_pole_lowpass(samples: list[float], sample_rate: int, cutoff_hz: float) -> list[float]:
    alpha = 1.0 - math.exp(-2.0 * math.pi * cutoff_hz / sample_rate)
    out = [0.0] * len(samples)
    y = 0.0
    for i, x in enumerate(samples):
        y += alpha * (x - y)
        out[i] = y
    return out


def _rms(samples: list[float], a: int, b: int) -> float:
    total = 0.0
    for i in range(a, min(b, len(samples))):
        total += samples[i] * samples[i]
    n = max(1, min(b, len(samples)) - a)
    return math.sqrt(total / n)


def _rms_diff(samples: list[float], lowpassed: list[float], a: int, b: int) -> float:
    total = 0.0
    for i in range(a, min(b, len(samples))):
        d = samples[i] - lowpassed[i]
        total += d * d
    n = max(1, min(b, len(samples)) - a)
    return math.sqrt(total / n)


def _zero_cross_f0(samples: list[float], a: int, b: int, sample_rate: int) -> float:
    b = min(b, len(samples))
    if b - a < 8:
        return 0.0
    crossings = 0
    prev = samples[a]
    for i in range(a + 1, b):
        cur = samples[i]
        if (prev < 0.0) != (cur < 0.0):
            crossings += 1
        prev = cur
    return crossings * sample_rate / (2.0 * (b - a))


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(len(ordered) * q))
    return ordered[idx]


def _smooth_inplace(curve: list[float], attack: float, release: float) -> None:
    y = 0.0
    for i, x in enumerate(curve):
        k = attack if x > y else release
        y += k * (x - y)
        curve[i] = round(y, 4)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]
