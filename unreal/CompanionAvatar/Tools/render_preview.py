"""CompanionStage sahnasidan CineCamera orqali bitta kadr render qiladi —
yoritish/kadrlashni ko'z bilan tekshirish uchun (headless, RHI bilan).

    "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd" \
        "<repo>/unreal/CompanionAvatar/CompanionAvatar.uproject" \
        -run=pythonscript -script=".../Tools/render_preview.py" \
        -stdout -Unattended -NoP4 -RenderOffscreen -NoSplash

Natija: /tmp/companion_stage_preview.png (RESULT faylida yo'l).
DIQQAT: -NullRHI QO'YMANG (render uchun RHI kerak).
"""
from __future__ import annotations

from pathlib import Path

import unreal

OUT = "/tmp/companion_stage_preview.png"
RESULT = Path(__file__).resolve().parent / "render_preview_result.txt"


def log(msg: str) -> None:
    unreal.log_warning(f"RENDER: {msg}")
    RESULT.write_text(msg + "\n", encoding="utf-8")


def main() -> None:
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    les.load_level("/Game/CompanionStage")

    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    cams = [a for a in eas.get_all_level_actors() if isinstance(a, unreal.CineCameraActor)]
    if not cams:
        log("XATO: CineCameraActor topilmadi")
        return

    # Editor perspektiv viewport'ini kamera transformiga qo'yamiz.
    cam = cams[0]
    loc = cam.get_actor_location()
    rot = cam.get_actor_rotation()
    try:
        unreal.EditorLevelLibrary.set_level_viewport_camera_info(loc, rot)
    except Exception as exc:  # noqa: BLE001
        log(f"viewport camera set xato (davom): {exc}")

    # Kameradan yuqori sifatli kadr (camera argumenti bilan bevosita render).
    try:
        unreal.AutomationLibrary.take_high_res_screenshot(1280, 720, OUT, cam)
        log(f"take_high_res_screenshot chaqirildi -> {OUT}")
    except Exception as exc:  # noqa: BLE001
        log(f"take_high_res_screenshot XATO: {exc}")


try:
    main()
except Exception:  # noqa: BLE001
    import traceback
    log("TRACEBACK:\n" + traceback.format_exc())
    raise
