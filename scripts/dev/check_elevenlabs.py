from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib import error, request
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ElevenLabs .env configuration without printing secrets.")
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--audio-file", default="")
    parser.add_argument("--skip-tts", action="store_true")
    args = parser.parse_args()

    env = read_env(Path(args.env_file))
    api_key = env.get("ELEVENLABS_API_KEY", "")
    voice_id = env.get("ELEVENLABS_VOICE_ID", "")
    base_url = env.get("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io").rstrip("/")
    output_format = env.get("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128")
    tts_model = env.get("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
    tts_language = elevenlabs_language_code(env.get("ELEVENLABS_LANGUAGE_CODE", "auto"))
    stt_model = env.get("ELEVENLABS_STT_MODEL_ID", "scribe_v2")
    stt_language = env.get("ELEVENLABS_STT_LANGUAGE_CODE", "uz").strip() or None

    result: dict[str, object] = {
        "api_key": "SET" if api_key else "EMPTY",
        "voice_id": "SET" if voice_id else "EMPTY",
        "tts_model": tts_model,
        "tts_language_code": tts_language or "omitted",
        "stt_model": stt_model,
        "stt_language_code": stt_language or "omitted",
    }

    if not api_key:
        result["ok"] = False
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1

    voices_payload = get_json(f"{base_url}/v1/voices", api_key)
    voices = voices_payload.get("voices", []) if isinstance(voices_payload, dict) else []
    result["voice_list"] = {"ok": True, "count": len(voices)}
    if voice_id:
        result["configured_voice"] = {
            "ok": any(item.get("voice_id") == voice_id for item in voices if isinstance(item, dict))
        }

    if voice_id and not args.skip_tts:
        audio = post_tts(base_url, api_key, voice_id, tts_model, output_format, tts_language)
        result["tts"] = {"ok": True, "bytes_sampled": len(audio)}

    if args.audio_file:
        transcript = post_stt(base_url, api_key, stt_model, stt_language, Path(args.audio_file))
        result["stt"] = {
            "ok": True,
            "text_preview": str(transcript.get("text", ""))[:120],
            "language_code": transcript.get("language_code"),
        }

    result["ok"] = True
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = strip_env_value(value)
    return values


def strip_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def get_json(url: str, api_key: str) -> dict[str, object]:
    http_request = request.Request(url, headers={"Accept": "application/json", "xi-api-key": api_key})
    with request.urlopen(http_request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def post_tts(
    base_url: str,
    api_key: str,
    voice_id: str,
    model_id: str,
    output_format: str,
    language_code: str | None,
) -> bytes:
    payload: dict[str, object] = {"text": "Salom.", "model_id": model_id}
    if language_code:
        payload["language_code"] = language_code
    url = f"{base_url}/v1/text-to-speech/{voice_id}?output_format={output_format}"
    http_request = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key,
        },
    )
    with request.urlopen(http_request, timeout=30) as response:
        return response.read(64)


def post_stt(
    base_url: str,
    api_key: str,
    model_id: str,
    language_code: str | None,
    audio_path: Path,
) -> dict[str, object]:
    fields = {"model_id": model_id}
    if language_code:
        fields["language_code"] = language_code
    body, content_type = multipart_body(fields, "file", audio_path)
    http_request = request.Request(
        f"{base_url}/v1/speech-to-text",
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": content_type,
            "xi-api-key": api_key,
        },
    )
    with request.urlopen(http_request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def multipart_body(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
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
    parts.extend(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{file_path.name or "audio.webm"}"\r\n'
            ).encode("utf-8"),
            b"Content-Type: application/octet-stream\r\n\r\n",
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def elevenlabs_language_code(value: str) -> str | None:
    normalized = value.strip().lower()
    if normalized in {"", "auto", "none", "default"}:
        return None
    return normalized


def safe_error_code(body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return "unknown"
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, dict):
        return str(detail.get("code", "unknown"))
    return "unknown"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except error.HTTPError as exc:
        body = exc.read(1200).decode("utf-8", errors="replace")
        print(
            json.dumps(
                {
                    "ok": False,
                    "http_status": exc.code,
                    "error": safe_error_code(body),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        raise SystemExit(1)
