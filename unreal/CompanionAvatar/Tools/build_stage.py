"""CompanionStage sahnasini kafolatlangan holatga keltiruvchi idempotent skript.

Headless ishga tushirish (og'ir qadam — 8GB Mac'da 2-5 daqiqa):

    "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd" \
        "<repo>/unreal/CompanionAvatar/CompanionAvatar.uproject" \
        -run=pythonscript -script="<repo>/unreal/CompanionAvatar/Tools/build_stage.py" \
        -stdout -Unattended -NoP4 -NullRHI -NoSplash

Nima qiladi: /Game/CompanionStage levelini ochadi (yo'q bo'lsa yaratadi),
5 ta aktyorni tekshiradi — yo'g'ini yaratadi, borining muhim xossalarini
spetsifikatsiyaga keltiradi, o'zgarish bo'lsa levelni saqlaydi.
Har tekshiruv "BUILD_STAGE: <holat> <nima>" qatorini chiqaradi
(holat: OK | FIXED | CREATED | ERROR). Xato bo'lsa oxirida FAILED chiqadi.
"""
from __future__ import annotations

from pathlib import Path

import unreal

RESULT_FILE = Path(__file__).resolve().parent / "build_stage_result.txt"
_result_lines: list[str] = []

LEVEL_PATH = "/Game/CompanionStage"
METAHUMAN_BP = "/Game/MetaHumans/NewMetaHumanCharacter/BP_NewMetaHumanCharacter"

# Spetsifikatsiya (docs/UE_HANDOFF_PROMPT.md dagi qiymatlar).
CAMERA_LOC = unreal.Vector(220.0, 0.0, 145.0)
CAMERA_ROT = unreal.Rotator(0.0, 0.0, 180.0)  # roll, pitch, yaw
CAMERA_FOCAL = 35.0
DIRLIGHT_LUX = 40.0
RIM_LOC = unreal.Vector(-90.0, 35.0, 175.0)
RIM_CANDELAS = 60.0
RIM_COLOR = unreal.Color(r=255, g=59, b=64, a=255)  # ~ (1.0, 0.23, 0.25)

changed = False
failed = False


def report(status: str, message: str) -> None:
    # Commandlet stdout'ida faqat Warning+ ko'rinadi; natijani faylga ham yozamiz.
    line = f"BUILD_STAGE: {status} {message}"
    _result_lines.append(line)
    RESULT_FILE.write_text("\n".join(_result_lines) + "\n", encoding="utf-8")
    if status in ("ERROR",):
        unreal.log_error(line)
    else:
        unreal.log_warning(line)


def mark_fixed(message: str) -> None:
    global changed
    changed = True
    report("FIXED", message)


def nearly(a: float, b: float, tol: float = 0.5) -> bool:
    return abs(a - b) <= tol


def vec_nearly(a: unreal.Vector, b: unreal.Vector, tol: float = 1.0) -> bool:
    return nearly(a.x, b.x, tol) and nearly(a.y, b.y, tol) and nearly(a.z, b.z, tol)


def ensure_level() -> None:
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if unreal.EditorAssetLibrary.does_asset_exist(LEVEL_PATH):
        les.load_level(LEVEL_PATH)
        report("OK", f"level {LEVEL_PATH} ochildi")
    else:
        les.new_level(LEVEL_PATH)
        mark_fixed(f"level {LEVEL_PATH} yaratildi")


def all_actors() -> list[unreal.Actor]:
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return list(eas.get_all_level_actors())


def find_by_class(cls) -> list[unreal.Actor]:
    return [a for a in all_actors() if isinstance(a, cls)]


def spawn(cls_or_asset, loc=unreal.Vector(0, 0, 0), rot=unreal.Rotator(0, 0, 0)):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return eas.spawn_actor_from_class(cls_or_asset, loc, rot)


def ensure_transform(actor: unreal.Actor, loc: unreal.Vector, rot: unreal.Rotator | None, label: str) -> None:
    if not vec_nearly(actor.get_actor_location(), loc):
        actor.set_actor_location(loc, False, False)
        mark_fixed(f"{label} joylashuvi {loc} ga keltirildi")
    if rot is not None:
        cur = actor.get_actor_rotation()
        if not (nearly(cur.yaw, rot.yaw, 1.0) and nearly(cur.pitch, rot.pitch, 1.0)):
            actor.set_actor_rotation(rot, False)
            mark_fixed(f"{label} burilishi {rot} ga keltirildi")


def ensure_metahuman() -> None:
    existing = [a for a in all_actors() if "MetaHuman" in a.get_name()
                and a.get_component_by_class(unreal.SkeletalMeshComponent)]
    if existing:
        ensure_transform(existing[0], unreal.Vector(0, 0, 0), None, "MetaHuman")
        report("OK", f"MetaHuman bor: {existing[0].get_name()}")
        return
    bp_class = unreal.EditorAssetLibrary.load_blueprint_class(METAHUMAN_BP)
    if not bp_class:
        report("ERROR", f"MetaHuman BP topilmadi: {METAHUMAN_BP}")
        global failed
        failed = True
        return
    spawn(bp_class)
    mark_fixed("MetaHuman (0,0,0) ga spawn qilindi")


def ensure_camera() -> None:
    cams = find_by_class(unreal.CineCameraActor)
    if not cams:
        cam = spawn(unreal.CineCameraActor, CAMERA_LOC, CAMERA_ROT)
        mark_fixed("CineCameraActor yaratildi")
    else:
        cam = cams[0]
        ensure_transform(cam, CAMERA_LOC, CAMERA_ROT, "CineCamera")
    comp = cam.get_cine_camera_component()
    if not nearly(comp.get_editor_property("current_focal_length"), CAMERA_FOCAL, 0.1):
        comp.set_editor_property("current_focal_length", CAMERA_FOCAL)
        mark_fixed(f"Focal length {CAMERA_FOCAL}mm qilindi")
    report("OK", "CineCamera spetsifikatsiyada")


def light_component(actor: unreal.Actor):
    return actor.get_component_by_class(unreal.LightComponent)


def ensure_directional() -> None:
    lights = find_by_class(unreal.DirectionalLight)
    if not lights:
        light = spawn(unreal.DirectionalLight, unreal.Vector(0, 0, 300))
        mark_fixed("DirectionalLight yaratildi")
    else:
        light = lights[0]
    comp = light_component(light)
    if not nearly(comp.get_editor_property("intensity"), DIRLIGHT_LUX, 0.5):
        comp.set_editor_property("intensity", DIRLIGHT_LUX)
        mark_fixed(f"DirectionalLight {DIRLIGHT_LUX} lux qilindi")
    report("OK", "DirectionalLight spetsifikatsiyada")


def ensure_skylight() -> None:
    if find_by_class(unreal.SkyLight):
        report("OK", "SkyLight bor")
        return
    spawn(unreal.SkyLight, unreal.Vector(0, 0, 400))
    mark_fixed("SkyLight yaratildi")


def ensure_rim() -> None:
    lights = find_by_class(unreal.PointLight)
    if not lights:
        light = spawn(unreal.PointLight, RIM_LOC)
        mark_fixed("PointLight (qizil rim) yaratildi")
    else:
        light = lights[0]
        ensure_transform(light, RIM_LOC, None, "Rim PointLight")
    comp = light_component(light)
    if comp.get_editor_property("intensity_units") != unreal.LightUnits.CANDELAS:
        comp.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
        mark_fixed("Rim intensity birligi candela qilindi")
    if not nearly(comp.get_editor_property("intensity"), RIM_CANDELAS, 0.5):
        comp.set_editor_property("intensity", RIM_CANDELAS)
        mark_fixed(f"Rim {RIM_CANDELAS} cd qilindi")
    cur = comp.get_editor_property("light_color")
    if (abs(cur.r - RIM_COLOR.r) > 3) or (abs(cur.g - RIM_COLOR.g) > 3) or (abs(cur.b - RIM_COLOR.b) > 3):
        comp.set_editor_property("light_color", RIM_COLOR)
        mark_fixed("Rim rangi qizilga keltirildi")
    report("OK", "Rim PointLight spetsifikatsiyada")


def main() -> None:
    ensure_level()
    ensure_metahuman()
    ensure_camera()
    ensure_directional()
    ensure_skylight()
    ensure_rim()

    if failed:
        report("ERROR", "FAILED — yuqoridagi xatolarga qarang")
        return
    if changed:
        saved = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        report("FIXED" if saved else "ERROR", f"level saqlandi: {saved}")
    else:
        report("OK", "hech narsa o'zgartirilmadi — sahna allaqachon spetsifikatsiyada")
    report("OK", "DONE")


report("OK", "skript boshlandi")
try:
    main()
except Exception:  # noqa: BLE001 — commandlet logida to'liq traceback ko'rinsin
    import traceback
    for tb_line in traceback.format_exc().splitlines():
        report("ERROR", tb_line)
    raise
