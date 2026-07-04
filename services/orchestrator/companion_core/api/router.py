from __future__ import annotations

from dataclasses import dataclass
import mimetypes
from pathlib import Path
import threading
from typing import Any
from urllib.parse import unquote

from companion_core.config import _default_env_path
from companion_core.contracts import VoiceTurnRequest
from companion_core.runtime import RuntimeContext

# Web rejimi: Electron ishlatmasdan ham xuddi shu UI brauzerda ochiladi
# (http://127.0.0.1:8765). Fayllar faqat renderer papkasidan beriladi.
_RENDERER_DIR = _default_env_path().parent / "apps" / "desktop" / "renderer"

# Lokal 3D avatar GLB katalogi (offline-birinchi: tarmoq bloklansa ham ishlaydi).
_AVATAR_DIR = _default_env_path().parent / "assets" / "avatars"
# Foydalanuvchi GLB qo'ymagan bo'lsa, namuna avatar bir marta yuklab keshlanadi
# (RPM'da yaratilgan, ARKit+viseme morphlar; CC BY-NC 4.0 — nokommersial).
_AVATAR_CACHE = _default_env_path().parent / "models" / "cache" / "avatar-fallback.glb"
_AVATAR_FALLBACK_URL = (
    "https://cdn.jsdelivr.net/gh/met4citizen/TalkingHead@master/avatars/brunette.glb"
)
_MIN_GLB_BYTES = 200_000
_AVATAR_DOWNLOAD_LOCK = threading.Lock()


@dataclass(frozen=True)
class ApiResponse:
    status: int
    payload: Any
    headers: dict[str, str] | None = None


class LocalApiRouter:
    def __init__(self, runtime: RuntimeContext) -> None:
        self._runtime = runtime

    def handle(self, method: str, path: str, payload: dict[str, Any] | None = None) -> ApiResponse:
        method = method.upper()
        payload = payload or {}

        if method == "GET" and path == "/health":
            return ApiResponse(200, self._runtime.health())
        if method == "GET" and path == "/runtime/state":
            return ApiResponse(200, self._runtime.runtime_state())
        if method == "GET" and path == "/agents":
            return ApiResponse(200, {"agents": self._runtime.agents()})
        if method == "GET" and path == "/providers/health":
            return ApiResponse(200, {"providers": self._runtime.provider_health()})
        if method == "GET" and path == "/providers/catalog":
            return ApiResponse(200, self._runtime.provider_catalog())
        if method == "GET" and path.startswith("/audio/cache/"):
            return self._cached_audio(path)
        if method == "GET" and path == "/avatar/model":
            return self._avatar_model()
        if method == "GET" and path == "/settings":
            return ApiResponse(200, self._runtime.settings())
        if method in {"PATCH", "POST"} and path == "/settings":
            return self._update_settings(payload)
        if method == "GET" and path == "/profile":
            return ApiResponse(200, self._runtime.profile())
        if method in {"PATCH", "POST"} and path == "/profile":
            return self._update_profile(payload)
        if method == "GET" and path == "/conversation":
            return ApiResponse(200, self._runtime.conversation())
        if method in {"DELETE", "POST"} and path == "/conversation/clear":
            return ApiResponse(200, self._runtime.clear_conversation())
        if method == "POST" and path == "/audio/upload":
            return self._audio_upload(payload)
        if method == "POST" and path == "/voice/turn":
            return self._voice_turn(payload)
        if method == "GET":
            static = self._static_file(path)
            if static is not None:
                return static

        return ApiResponse(404, {"error": "not_found", "path": path})

    def _static_file(self, path: str) -> ApiResponse | None:
        """Serve the desktop renderer as a local web app (browser mode).

        Subdirectories (masalan vendor/three/...) ham beriladi; har bir
        segmentda yashirin fayl/`..` taqiqlanadi va resolve() ildizdan
        chiqib ketishni bloklaydi.
        """
        name = unquote(path.lstrip("/")) or "index.html"
        if "\\" in name:
            return None
        segments = [s for s in name.split("/") if s]
        if not segments or any(s.startswith(".") for s in segments):
            return None
        root = _RENDERER_DIR.resolve()
        file_path = (root / Path(*segments)).resolve()
        try:
            file_path.relative_to(root)
        except ValueError:
            return None
        if not file_path.is_file():
            return None
        mime, _ = mimetypes.guess_type(file_path.name)
        return ApiResponse(
            200,
            file_path.read_bytes(),
            headers={
                "Content-Type": mime or "application/octet-stream",
                "Cache-Control": "no-store",
            },
        )

    def _avatar_model(self) -> ApiResponse:
        """Serve the avatar GLB from local disk (renderer's fastest source).

        Priority: assets/avatars/*.glb (user's own, e.g. RPM with
        ?morphTargets=ARKit) -> models/cache/avatar-fallback.glb (namuna,
        birinchi so'rovda bir marta yuklab keshlanadi). Diskdan berilgani
        uchun web rejimda ham 3D ko'rinish darhol ochiladi.
        """
        model_path = self._resolve_avatar_glb()
        if model_path is None:
            return ApiResponse(
                404,
                {
                    "error": "avatar_model_not_found",
                    "message": (
                        "Put a Ready Player Me GLB (morphTargets=ARKit) into "
                        "assets/avatars/ (fallback download ham muvaffaqiyatsiz)."
                    ),
                },
            )
        return ApiResponse(
            200,
            model_path.read_bytes(),
            headers={
                "Content-Type": "model/gltf-binary",
                "Cache-Control": "no-store",
                "X-Avatar-Filename": model_path.name,
            },
        )

    def _resolve_avatar_glb(self) -> Path | None:
        avatar_dir = _AVATAR_DIR.resolve()
        candidates = sorted(avatar_dir.glob("*.glb")) if avatar_dir.is_dir() else []
        for candidate in candidates:
            if candidate.stat().st_size >= _MIN_GLB_BYTES:
                return candidate
        if _AVATAR_CACHE.is_file() and _AVATAR_CACHE.stat().st_size >= _MIN_GLB_BYTES:
            return _AVATAR_CACHE
        return self._download_fallback_avatar()

    def _download_fallback_avatar(self) -> Path | None:
        """Namuna GLB'ni bir marta yuklab keshlash (poyga xavfsiz)."""
        with _AVATAR_DOWNLOAD_LOCK:
            if _AVATAR_CACHE.is_file() and _AVATAR_CACHE.stat().st_size >= _MIN_GLB_BYTES:
                return _AVATAR_CACHE
            try:
                from urllib import request as _request

                with _request.urlopen(_AVATAR_FALLBACK_URL, timeout=60) as response:
                    data = response.read()
                if len(data) < _MIN_GLB_BYTES:
                    return None
                _AVATAR_CACHE.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = _AVATAR_CACHE.with_suffix(".tmp")
                tmp_path.write_bytes(data)
                tmp_path.replace(_AVATAR_CACHE)
                return _AVATAR_CACHE
            except Exception:  # noqa: BLE001 - offline bo'lsa renderer o'zi CDN'ga o'tadi.
                return None

    def _voice_turn(self, payload: dict[str, Any]) -> ApiResponse:
        try:
            request = VoiceTurnRequest(
                session_id=str(payload.get("session_id", "dev-session")),
                agent_id=str(payload.get("agent_id", "default")),
                audio_ref=payload.get("audio_ref"),
                transcript_override=payload.get("transcript_override"),
                interrupt_previous=bool(payload.get("interrupt_previous", False)),
                user_locale=str(payload.get("user_locale", "uz-Latn")),
            )
            result = self._runtime.run_voice_turn(request)
        except Exception as exc:  # noqa: BLE001 - API boundary returns safe error.
            return ApiResponse(400, {"error": "voice_turn_failed", "message": str(exc)})
        return ApiResponse(200, result)

    def _update_profile(self, payload: dict[str, Any]) -> ApiResponse:
        try:
            result = self._runtime.update_profile(payload)
        except Exception as exc:  # noqa: BLE001 - API boundary returns safe error.
            return ApiResponse(400, {"error": "profile_update_failed", "message": str(exc)})
        return ApiResponse(200, result)

    def _update_settings(self, payload: dict[str, Any]) -> ApiResponse:
        try:
            result = self._runtime.update_settings(payload)
        except Exception as exc:  # noqa: BLE001 - API boundary returns safe error.
            return ApiResponse(400, {"error": "settings_update_failed", "message": str(exc)})
        return ApiResponse(200, result)

    def _audio_upload(self, payload: dict[str, Any]) -> ApiResponse:
        try:
            result = self._runtime.save_audio_upload(
                audio_base64=str(payload.get("audio_base64", "")),
                mime_type=str(payload.get("mime_type", "application/octet-stream")),
                session_id=str(payload.get("session_id", "dev-session")),
            )
        except Exception as exc:  # noqa: BLE001 - API boundary returns safe error.
            return ApiResponse(400, {"error": "audio_upload_failed", "message": str(exc)})
        return ApiResponse(200, result)

    def _cached_audio(self, path: str) -> ApiResponse:
        filename = unquote(path.removeprefix("/audio/cache/"))
        try:
            audio = self._runtime.read_cached_audio(filename)
        except FileNotFoundError as exc:
            return ApiResponse(404, {"error": "audio_not_found", "message": str(exc)})
        except Exception as exc:  # noqa: BLE001 - API boundary returns safe error.
            return ApiResponse(400, {"error": "audio_read_failed", "message": str(exc)})
        return ApiResponse(
            200,
            audio.content,
            headers={
                "Content-Type": audio.mime_type,
                "Cache-Control": "no-store",
                "X-Audio-Filename": audio.filename,
            },
        )
