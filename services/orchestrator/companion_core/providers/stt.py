from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import socket
from typing import Any, Protocol
from urllib import error, request
from uuid import uuid4

from companion_core.contracts import ProviderHealth, ProviderKind, TranscriptResult
from companion_core.providers.base import STTProvider


class ElevenLabsSTTClient(Protocol):
    def create_transcript(
        self,
        *,
        api_key: str,
        model_id: str,
        audio_path: Path,
        language_code: str | None,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ElevenLabsSTTHttpClient:
    base_url: str = "https://api.elevenlabs.io"
    timeout_seconds: float = 45.0

    def create_transcript(
        self,
        *,
        api_key: str,
        model_id: str,
        audio_path: Path,
        language_code: str | None,
    ) -> dict[str, Any]:
        fields: dict[str, str] = {"model_id": model_id}
        if language_code:
            fields["language_code"] = language_code

        body, content_type = _multipart_body(fields, "file", audio_path)
        http_request = request.Request(
            f"{self.base_url.rstrip('/')}/v1/speech-to-text",
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": content_type,
                "xi-api-key": api_key,
            },
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise RuntimeError(_elevenlabs_stt_http_error_message(exc)) from exc
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"ElevenLabs speech-to-text request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("ElevenLabs speech-to-text returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("ElevenLabs speech-to-text returned an invalid response.")
        return payload


@dataclass(frozen=True)
class ElevenLabsSTTProvider(STTProvider):
    api_key_configured: bool
    api_key_env: str
    api_key: str = field(default="", repr=False, compare=False)
    model_id: str = "scribe_v2"
    base_url: str = "https://api.elevenlabs.io"
    language_code: str = "uz"
    client: ElevenLabsSTTClient | None = field(default=None, repr=False, compare=False)
    provider_id: str = "elevenlabs_stt"

    def health(self) -> ProviderHealth:
        if not self.api_key_configured or not self.api_key:
            return ProviderHealth(
                self.provider_id,
                ProviderKind.STT,
                ready=False,
                status="missing_key",
                message=f"Set {self.api_key_env} to enable ElevenLabs speech-to-text.",
            )
        return ProviderHealth(
            self.provider_id,
            ProviderKind.STT,
            ready=True,
            status="configured",
            message=f"Model {self.model_id}; language {self.language_code or 'auto'}.",
        )

    def transcribe(self, audio_ref: str, language: str) -> TranscriptResult:
        if not audio_ref.strip():
            raise ValueError("audio_ref is required for ElevenLabs speech-to-text.")
        if not self.api_key_configured or not self.api_key:
            raise ValueError(f"{self.api_key_env} is not configured.")

        audio_path = _audio_path_from_ref(audio_ref)
        if not audio_path.is_file():
            raise FileNotFoundError("Audio file for transcription was not found.")

        language_code = self.language_code.strip() or _language_code_from_locale(language)
        client = self.client or ElevenLabsSTTHttpClient(base_url=self.base_url)
        payload = client.create_transcript(
            api_key=self.api_key,
            model_id=self.model_id,
            audio_path=audio_path,
            language_code=language_code,
        )
        text = str(payload.get("text", "")).strip()
        if not text:
            raise RuntimeError("ElevenLabs speech-to-text returned an empty transcript.")

        detected_language = str(payload.get("language_code") or language_code or language)
        confidence = _optional_float(payload.get("language_probability"))
        return TranscriptResult(
            text=text,
            language=detected_language,
            confidence=confidence,
            provider_id=self.provider_id,
        )


def _audio_path_from_ref(audio_ref: str) -> Path:
    if not audio_ref.startswith("file://"):
        raise ValueError("ElevenLabs speech-to-text currently supports local file:// audio refs.")
    return Path(audio_ref.removeprefix("file://")).expanduser()


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
            b"Content-Type: application/octet-stream\r\n\r\n",
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _elevenlabs_stt_http_error_message(exc: error.HTTPError) -> str:
    error_payload = _safe_error_payload(exc)
    detail = error_payload.get("detail") if isinstance(error_payload, dict) else None
    if isinstance(detail, dict):
        code = str(detail.get("code", ""))
        message = str(detail.get("message", ""))
        if "speech_to_text" in message:
            return (
                "ElevenLabs API key does not have speech_to_text permission. "
                "Create or update the key in ElevenLabs with speech_to_text permission, "
                "then restart the local stack."
            )
        if code == "unauthorized":
            return (
                "ElevenLabs API key was rejected as unauthorized. "
                "Check that ELEVENLABS_API_KEY is copied correctly, active, and has speech_to_text permission."
            )
        if code:
            return f"ElevenLabs speech-to-text failed with HTTP {exc.code}: {code}."
    return f"ElevenLabs speech-to-text failed with HTTP {exc.code}."


def _safe_error_payload(exc: error.HTTPError) -> object:
    try:
        body = exc.read(2000).decode("utf-8", errors="replace").strip()
    except Exception:  # noqa: BLE001 - error body is optional context.
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def _language_code_from_locale(language: str) -> str | None:
    normalized = language.strip().lower()
    if not normalized:
        return None
    return normalized.split("-", 1)[0]


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
