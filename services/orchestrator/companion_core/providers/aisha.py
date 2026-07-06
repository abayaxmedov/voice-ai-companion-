"""Aisha AI (aisha.group) — o'zbek tiliga ixtisoslashgan STT/TTS adapterlari.

API: https://aisha.group/en/api-documentation (Base URL: https://back.aisha.group)
- STT (sync):  POST /api/v1/stt/post/   (multipart: audio, language) -> {"transcript": ...}
- TTS (sync):  POST /api/v1/tts/post/   (multipart: transcript, language, model,
               mood, speed | voice_id) -> 201 {"audio_path": "/media/..."}
Autentifikatsiya: X-Api-Key sarlavhasi. Kalitlar hech qachon loglanmaydi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import socket
from typing import Any, Protocol
from urllib import error, request
from uuid import uuid4

from companion_core.contracts import (
    ProviderHealth,
    ProviderKind,
    TranscriptResult,
    TTSResult,
)
from companion_core.providers.base import STTProvider, TTSProvider

_TTS_CHAR_LIMIT = 1000  # API kalit bilan limit (hujjatdan)
_ALLOWED_MOODS = {"Neutral", "Cheerful", "Happy", "Sad"}


class AishaClient(Protocol):
    def transcribe(
        self,
        *,
        api_key: str,
        audio_path: Path,
        language: str,
    ) -> dict[str, Any]:
        ...

    def synthesize(
        self,
        *,
        api_key: str,
        transcript: str,
        language: str,
        model: str,
        mood: str,
        speed: str,
        voice_id: str,
    ) -> bytes:
        ...


@dataclass(frozen=True)
class AishaHttpClient:
    base_url: str = "https://back.aisha.group"
    timeout_seconds: float = 60.0

    def transcribe(
        self,
        *,
        api_key: str,
        audio_path: Path,
        language: str,
    ) -> dict[str, Any]:
        fields = {"language": language or "uz", "has_diarization": "false"}
        body, content_type = _multipart_body(fields, "audio", audio_path)
        http_request = request.Request(
            f"{self.base_url.rstrip('/')}/api/v1/stt/post/",
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Accept-Language": language or "uz",
                "Content-Type": content_type,
                "X-Api-Key": api_key,
            },
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise RuntimeError(_aisha_http_error_message("STT", exc)) from exc
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"Aisha STT request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Aisha STT returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Aisha STT returned an invalid response.")
        return payload

    def synthesize(
        self,
        *,
        api_key: str,
        transcript: str,
        language: str,
        model: str,
        mood: str,
        speed: str,
        voice_id: str,
    ) -> bytes:
        fields: dict[str, str] = {
            "transcript": transcript,
            "language": language or "uz",
        }
        if voice_id:
            # READY custom ovoz: mood/model yuborilmaydi (hujjat talabi).
            fields["voice_id"] = voice_id
        elif (language or "uz") == "uz":
            # Built-in Gulnoza oqimi faqat uz uchun.
            fields["model"] = model or "Gulnoza"
            if mood:
                fields["mood"] = mood
            if speed:
                fields["speed"] = speed

        body, content_type = _multipart_fields_only(fields)
        http_request = request.Request(
            f"{self.base_url.rstrip('/')}/api/v1/tts/post/",
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Accept-Language": language or "uz",
                "Content-Type": content_type,
                "X-Api-Key": api_key,
            },
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise RuntimeError(_aisha_http_error_message("TTS", exc)) from exc
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"Aisha TTS request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Aisha TTS returned invalid JSON.") from exc

        audio_path = str(payload.get("audio_path") or payload.get("audio_url") or "").strip()
        if not audio_path:
            raise RuntimeError(
                "Aisha TTS did not return audio_path (async rejim bu adapterda ishlatilmaydi)."
            )
        return self._download_audio(audio_path, api_key)

    def _download_audio(self, audio_path: str, api_key: str) -> bytes:
        url = (
            audio_path
            if audio_path.startswith("http")
            else f"{self.base_url.rstrip('/')}/{audio_path.lstrip('/')}"
        )
        # Media server ham kalit talab qiladi (aks holda 403).
        http_request = request.Request(
            url,
            method="GET",
            headers={
                "Accept": "*/*",
                "X-Api-Key": api_key,
                "User-Agent": "ovozli-hamroh/1.0",
            },
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                audio = response.read()
        except error.HTTPError as exc:
            raise RuntimeError(f"Aisha TTS audio download failed with HTTP {exc.code}.") from exc
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"Aisha TTS audio download failed: {exc}") from exc
        if not audio:
            raise RuntimeError("Aisha TTS returned an empty audio file.")
        return audio


@dataclass(frozen=True)
class AishaSTTProvider(STTProvider):
    api_key_configured: bool
    api_key_env: str
    api_key: str = field(default="", repr=False, compare=False)
    base_url: str = "https://back.aisha.group"
    language_code: str = "uz"
    client: AishaClient | None = field(default=None, repr=False, compare=False)
    provider_id: str = "aisha_stt"

    def health(self) -> ProviderHealth:
        if not self.api_key_configured or not self.api_key:
            return ProviderHealth(
                self.provider_id,
                ProviderKind.STT,
                ready=False,
                status="missing_key",
                message=f"Set {self.api_key_env} to enable Aisha speech-to-text.",
            )
        return ProviderHealth(
            self.provider_id,
            ProviderKind.STT,
            ready=True,
            status="configured",
            message=f"Aisha STT v1 (sync); language {self.language_code or 'uz'}.",
        )

    def transcribe(self, audio_ref: str, language: str) -> TranscriptResult:
        if not audio_ref.strip():
            raise ValueError("audio_ref is required for Aisha speech-to-text.")
        if not self.api_key_configured or not self.api_key:
            raise ValueError(f"{self.api_key_env} is not configured.")

        audio_path = _audio_path_from_ref(audio_ref)
        if not audio_path.is_file():
            raise FileNotFoundError("Audio file for transcription was not found.")

        language_code = self.language_code.strip() or _language_from_locale(language)
        client = self.client or AishaHttpClient(base_url=self.base_url)
        payload = client.transcribe(
            api_key=self.api_key,
            audio_path=audio_path,
            language=language_code,
        )
        text = str(payload.get("transcript", "")).strip()
        if not text:
            raise RuntimeError("Aisha speech-to-text returned an empty transcript.")
        return TranscriptResult(
            text=text,
            language=language_code or language,
            confidence=None,
            provider_id=self.provider_id,
        )


@dataclass(frozen=True)
class AishaTTSProvider(TTSProvider):
    api_key_configured: bool
    api_key_env: str
    api_key: str = field(default="", repr=False, compare=False)
    base_url: str = "https://back.aisha.group"
    model: str = "Gulnoza"
    mood: str = "Neutral"
    speed: str = "1.0"
    voice_id: str = ""
    language_code: str = "uz"
    audio_cache_dir: str = "/private/tmp/voice-ai-companion/audio"
    client: AishaClient | None = field(default=None, repr=False, compare=False)
    provider_id: str = "aisha_tts"

    def health(self) -> ProviderHealth:
        if not self.api_key_configured or not self.api_key:
            return ProviderHealth(
                self.provider_id,
                ProviderKind.TTS,
                ready=False,
                status="missing_key",
                message=f"Set {self.api_key_env} to enable Aisha text-to-speech.",
            )
        voice = self.voice_id or f"{self.model} ({self.mood})"
        return ProviderHealth(
            self.provider_id,
            ProviderKind.TTS,
            ready=True,
            status="configured",
            message=f"Aisha TTS v1 (sync); voice {voice}; language {self.language_code or 'uz'}.",
        )

    def synthesize(self, text: str, voice_profile_id: str, language: str) -> TTSResult:
        return self.synthesize_styled(text, voice_profile_id, language)

    def synthesize_styled(
        self,
        text: str,
        voice_profile_id: str,
        language: str,
        mood: str = "neutral",
        speech_style: str = "normal",
    ) -> TTSResult:
        del voice_profile_id, speech_style
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Cannot synthesize empty text.")
        if not self.api_key_configured or not self.api_key:
            raise ValueError(f"{self.api_key_env} is not configured.")
        if len(normalized_text) > _TTS_CHAR_LIMIT:
            normalized_text = normalized_text[:_TTS_CHAR_LIMIT].rsplit(" ", 1)[0]

        language_code = self.language_code.strip() or _language_from_locale(language)
        client = self.client or AishaHttpClient(base_url=self.base_url)
        audio = client.synthesize(
            api_key=self.api_key,
            transcript=normalized_text,
            language=language_code,
            model=self.model,
            mood=_aisha_mood(self.mood, mood),
            speed=self.speed,
            voice_id=self.voice_id,
        )

        cache_path = self._write_audio(audio)
        return TTSResult(
            audio_ref=f"file://{cache_path}",
            provider_id=self.provider_id,
            duration_ms=_estimate_duration_ms(normalized_text),
            sample_rate_hz=None,
            timing={
                "model": self.voice_id or self.model,
                "language_code": language_code,
                "language": language,
            },
        )

    def _write_audio(self, audio: bytes) -> Path:
        cache_dir = Path(self.audio_cache_dir).expanduser()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"aisha-{uuid4()}{_extension_for_audio(audio)}"
        cache_path.write_bytes(audio)
        return cache_path


def _aisha_mood(configured: str, llm_mood: str) -> str:
    """LLM mood -> Aisha mood (Gulnoza uchun 4 kayfiyat mavjud)."""
    mapped = {
        "happy": "Happy",
        "excited": "Cheerful",
        "concerned": "Sad",
        "apologetic": "Sad",
    }.get((llm_mood or "").lower())
    mood = mapped or (configured or "Neutral")
    return mood if mood in _ALLOWED_MOODS else "Neutral"


def _extension_for_audio(audio: bytes) -> str:
    if audio[:4] == b"RIFF":
        return ".wav"
    if audio[:3] == b"ID3" or (len(audio) > 1 and audio[0] == 0xFF and (audio[1] & 0xE0) == 0xE0):
        return ".mp3"
    if audio[:4] == b"OggS":
        return ".ogg"
    return ".wav"


def _audio_path_from_ref(audio_ref: str) -> Path:
    if not audio_ref.startswith("file://"):
        raise ValueError("Aisha speech-to-text currently supports local file:// audio refs.")
    return Path(audio_ref.removeprefix("file://")).expanduser()


def _language_from_locale(language: str) -> str:
    normalized = language.strip().lower()
    if not normalized:
        return "uz"
    code = normalized.split("-", 1)[0]
    return code if code in {"uz", "en", "ru"} else "uz"


def _multipart_body(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----companion-{uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    filename = file_path.name or "audio.webm"
    parts.extend(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{filename}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {_mime_for_filename(filename)}\r\n\r\n".encode("utf-8"),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _multipart_fields_only(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = f"----companion-{uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _mime_for_filename(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".wav"):
        return "audio/wav"
    if lowered.endswith(".mp3"):
        return "audio/mpeg"
    if lowered.endswith((".m4a", ".mp4")):
        return "audio/mp4"
    if lowered.endswith(".ogg"):
        return "audio/ogg"
    if lowered.endswith(".webm"):
        return "audio/webm"
    return "application/octet-stream"


def _aisha_http_error_message(kind: str, exc: error.HTTPError) -> str:
    if exc.code == 401 or exc.code == 403:
        return (
            f"Aisha {kind} API key was rejected (HTTP {exc.code}). "
            "Check that AISHA_API_KEY is copied correctly and active."
        )
    if exc.code == 402:
        return f"Aisha {kind}: balans yetarli emas (HTTP 402). space.aisha.group da to'ldiring."
    try:
        body = exc.read(2000).decode("utf-8", errors="replace").strip()
        detail = json.loads(body)
        message = str(
            detail.get("detail") or detail.get("message") or detail.get("error") or ""
        ).strip()
        if message:
            return f"Aisha {kind} failed with HTTP {exc.code}: {message[:200]}"
    except Exception:  # noqa: BLE001 - error body is optional context.
        pass
    return f"Aisha {kind} failed with HTTP {exc.code}."


def _estimate_duration_ms(text: str) -> int:
    words = max(1, len(text.split()))
    return max(700, int(words * 310))
