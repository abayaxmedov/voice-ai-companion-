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


class OpenAISTTClient(Protocol):
    def create_transcript(
        self,
        *,
        api_key: str,
        model: str,
        audio_path: Path,
        language: str | None,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class OpenAISTTHttpClient:
    base_url: str = "https://api.openai.com"
    timeout_seconds: float = 60.0

    def create_transcript(
        self,
        *,
        api_key: str,
        model: str,
        audio_path: Path,
        language: str | None,
    ) -> dict[str, Any]:
        fields: dict[str, str] = {"model": model, "response_format": "json"}
        if language:
            fields["language"] = language

        body, content_type = _multipart_body(fields, "file", audio_path)
        http_request = request.Request(
            f"{self.base_url.rstrip('/')}/v1/audio/transcriptions",
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": content_type,
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise RuntimeError(_openai_stt_http_error_message(exc)) from exc
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"OpenAI transcription request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenAI transcription returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("OpenAI transcription returned an invalid response.")
        return payload


@dataclass(frozen=True)
class OpenAISTTProvider(STTProvider):
    api_key_configured: bool
    api_key_env: str
    api_key: str = field(default="", repr=False, compare=False)
    model: str = "whisper-1"
    base_url: str = "https://api.openai.com"
    language_code: str = "uz"
    client: OpenAISTTClient | None = field(default=None, repr=False, compare=False)
    provider_id: str = "openai_stt"

    def health(self) -> ProviderHealth:
        if not self.api_key_configured or not self.api_key:
            return ProviderHealth(
                self.provider_id,
                ProviderKind.STT,
                ready=False,
                status="missing_key",
                message=f"Set {self.api_key_env} to enable OpenAI Whisper speech-to-text.",
            )
        return ProviderHealth(
            self.provider_id,
            ProviderKind.STT,
            ready=True,
            status="configured",
            message=f"Model {self.model}; language {self.language_code or 'auto'}.",
        )

    def transcribe(self, audio_ref: str, language: str) -> TranscriptResult:
        if not audio_ref.strip():
            raise ValueError("audio_ref is required for OpenAI speech-to-text.")
        if not self.api_key_configured or not self.api_key:
            raise ValueError(f"{self.api_key_env} is not configured.")

        audio_path = _audio_path_from_ref(audio_ref)
        if not audio_path.is_file():
            raise FileNotFoundError("Audio file for transcription was not found.")

        language_code = self.language_code.strip() or _language_code_from_locale(language)
        client = self.client or OpenAISTTHttpClient(base_url=self.base_url)
        payload = client.create_transcript(
            api_key=self.api_key,
            model=self.model,
            audio_path=audio_path,
            language=language_code,
        )
        text = str(payload.get("text", "")).strip()
        if not text:
            raise RuntimeError("OpenAI speech-to-text returned an empty transcript.")
        return TranscriptResult(
            text=text,
            language=str(payload.get("language") or language_code or language),
            confidence=None,
            provider_id=self.provider_id,
        )


def _audio_path_from_ref(audio_ref: str) -> Path:
    if not audio_ref.startswith("file://"):
        raise ValueError("OpenAI speech-to-text currently supports local file:// audio refs.")
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


def _openai_stt_http_error_message(exc: error.HTTPError) -> str:
    if exc.code == 401:
        return (
            "OpenAI API key was rejected as unauthorized. "
            "Check that OPENAI_API_KEY is copied correctly and active."
        )
    try:
        body = exc.read(2000).decode("utf-8", errors="replace")
        detail = json.loads(body).get("error", {})
        message = str(detail.get("message", "")).strip()
        if message:
            return f"OpenAI speech-to-text failed with HTTP {exc.code}: {message[:200]}"
    except Exception:  # noqa: BLE001 - error body is optional context.
        pass
    return f"OpenAI speech-to-text failed with HTTP {exc.code}."


def _language_code_from_locale(language: str) -> str | None:
    normalized = language.strip().lower()
    if not normalized:
        return None
    return normalized.split("-", 1)[0]
