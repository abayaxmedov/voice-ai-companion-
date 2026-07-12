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

import math
from pathlib import Path

import unreal

RESULT_FILE = Path(__file__).resolve().parent / "build_stage_result.txt"
_result_lines: list[str] = []

LEVEL_PATH = "/Game/CompanionStage"
METAHUMAN_BP = "/Game/MetaHumans/NewMetaHumanCharacter/BP_NewMetaHumanCharacter"

# Spetsifikatsiya (docs/UE_HANDOFF_PROMPT.md dagi qiymatlar).
CAMERA_LOC = unreal.Vector(220.0, 0.0, 145.0)
CAMERA_FOCAL = 35.0
# Kamera qaraydigan nuqta (personaj boshi, dunyo koordinatalarida).
HEAD_TARGET = unreal.Vector(0.0, 0.0, 150.0)
# Personajni kameraga qaratish uchun aktyor yaw'i. Agar RE-RUN'dan keyin
# ORQA tomon/ensa ko'rinsa — bu qiymatni +90.0 ga o'zgartiring (mesh forward
# ±Y bo'lgani uchun 90° burish kerak; sukut -90 bilan boshlanadi).
CHAR_FACE_YAW = -90.0
# Asosiy (key) nur: ilgari 40 lux + yo'nalishsiz edi → yuz orqasi yoritilardi.
# Endi kamera tomonidan, tepadan tushadi va yuzni ochib beradi.
DIRLIGHT_LUX = 180.0
DIRLIGHT_PITCH = -35.0   # tepadan pastga
DIRLIGHT_YAW_OFFSET = -20.0  # kamera yaw'iga nisbatan shakl beruvchi burilish
KEY_COLOR = unreal.Color(r=255, g=234, b=208, a=255)  # iliq oq (Unclaw "warm white")
SKYLIGHT_FILL = 1.2      # soyali tomon qop-qora bo'lmasligi uchun yumshoq to'ldirish

# --- Unclaw-uslub ACCENT (rim) — foydalanuvchi sozlashi mumkin. ---
# Unclaw'da 7 preset bor (warm white/orange/pink/blue/purple/green/custom).
# Bizning imzo — QIZIL; boshqa his uchun shu bitta qatorni o'zgartiring.
ACCENT_COLOR = unreal.Color(r=255, g=48, b=58, a=255)   # qizil
# Butun yoritish rigini personaj atrofida aylantirish (Unclaw LIGHTING dial).
# 0° = old-chapdan key, orqa-o'ngdan qizil rim (etalon ko'rinish).
LIGHT_RIG_YAW = 0.0

# Rim/accent nurlari (personajga nisbatan; LIGHT_RIG_YAW ular ustida aylanadi).
RIM1_LOC = unreal.Vector(-95.0, -60.0, 195.0)  # orqa-yuqori-o'ng (kadr yuqori-o'ng yog'du)
RIM1_CANDELAS = 90.0
RIM2_LOC = unreal.Vector(-95.0, 55.0, 185.0)   # orqa-yuqori-chap (xiraroq wrap)
RIM2_CANDELAS = 40.0

# Sovuq to'ldirish (fill) — old-past-o'ngdan, juda yumshoq.
FILL_LOC = unreal.Vector(120.0, -70.0, 90.0)
FILL_COLOR = unreal.Color(r=120, g=155, b=255, a=255)
FILL_CANDELAS = 16.0

changed = False
failed = False
# ensure_camera() hisoblaydi, ensure_directional() key nurni shunga qarab yo'naltiradi.
CAM_YAW = 180.0


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


def rotate_xy(v: unreal.Vector, yaw_deg: float) -> unreal.Vector:
    """Vektorni Z o'qi atrofida aylantirish (yoritish rigi dial'i uchun)."""
    r = math.radians(yaw_deg)
    c, s = math.cos(r), math.sin(r)
    return unreal.Vector(v.x * c - v.y * s, v.x * s + v.y * c, v.z)


def color_near(a, b, tol: int = 4) -> bool:
    return abs(a.r - b.r) <= tol and abs(a.g - b.g) <= tol and abs(a.b - b.b) <= tol


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
    face_rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=CHAR_FACE_YAW)
    existing = [a for a in all_actors() if "MetaHuman" in a.get_name()
                and a.get_component_by_class(unreal.SkeletalMeshComponent)]
    if existing:
        ensure_transform(existing[0], unreal.Vector(0, 0, 0), face_rot, "MetaHuman")
        report("OK", f"MetaHuman bor: {existing[0].get_name()}")
        return
    bp_class = unreal.EditorAssetLibrary.load_blueprint_class(METAHUMAN_BP)
    if not bp_class:
        report("ERROR", f"MetaHuman BP topilmadi: {METAHUMAN_BP}")
        global failed
        failed = True
        return
    spawn(bp_class, unreal.Vector(0, 0, 0), face_rot)
    mark_fixed(f"MetaHuman (0,0,0), kameraga qaragan (yaw={CHAR_FACE_YAW}) spawn qilindi")


def ensure_camera() -> None:
    global CAM_YAW
    # Boshga aniq qaraydigan burilishni hisoblaymiz (pozitsion Rotator xatosidan
    # xoli — find_look_at_rotation to'g'ri Rotator qaytaradi).
    cam_rot = unreal.MathLibrary.find_look_at_rotation(CAMERA_LOC, HEAD_TARGET)
    CAM_YAW = cam_rot.yaw
    cams = find_by_class(unreal.CineCameraActor)
    if not cams:
        cam = spawn(unreal.CineCameraActor, CAMERA_LOC, cam_rot)
        mark_fixed("CineCameraActor yaratildi (boshga look-at)")
    else:
        cam = cams[0]
        ensure_transform(cam, CAMERA_LOC, cam_rot, "CineCamera")
    comp = cam.get_cine_camera_component()
    if not nearly(comp.get_editor_property("current_focal_length"), CAMERA_FOCAL, 0.1):
        comp.set_editor_property("current_focal_length", CAMERA_FOCAL)
        mark_fixed(f"Focal length {CAMERA_FOCAL}mm qilindi")
    report("OK", f"CineCamera boshga qaraydi (yaw={CAM_YAW:.0f})")


def light_component(actor: unreal.Actor):
    return actor.get_component_by_class(unreal.LightComponent)


def ensure_directional() -> None:
    # Key nur kamera tomonidan (CAM_YAW), tepadan (DIRLIGHT_PITCH), iliq oq.
    # LIGHT_RIG_YAW butun rigni aylantiradi (Unclaw dial).
    key_rot = unreal.Rotator(
        roll=0.0, pitch=DIRLIGHT_PITCH,
        yaw=CAM_YAW + DIRLIGHT_YAW_OFFSET + LIGHT_RIG_YAW,
    )
    lights = find_by_class(unreal.DirectionalLight)
    if not lights:
        light = spawn(unreal.DirectionalLight, unreal.Vector(0, 0, 300), key_rot)
        mark_fixed("DirectionalLight yaratildi (yuzga yo'naltirilgan)")
    else:
        light = lights[0]
        cur = light.get_actor_rotation()
        if not (nearly(cur.yaw, key_rot.yaw, 1.0) and nearly(cur.pitch, key_rot.pitch, 1.0)):
            light.set_actor_rotation(key_rot, False)
            mark_fixed(f"DirectionalLight yo'nalishi yuzga qaratildi (yaw={key_rot.yaw:.0f}, pitch={DIRLIGHT_PITCH})")
    comp = light_component(light)
    if not nearly(comp.get_editor_property("intensity"), DIRLIGHT_LUX, 0.5):
        comp.set_editor_property("intensity", DIRLIGHT_LUX)
        mark_fixed(f"DirectionalLight {DIRLIGHT_LUX} lux qilindi")
    if not color_near(comp.get_editor_property("light_color"), KEY_COLOR):
        comp.set_editor_property("light_color", KEY_COLOR)
        mark_fixed("Key nur iliq oq qilindi")
    report("OK", "DirectionalLight (key) spetsifikatsiyada")


def ensure_skylight() -> None:
    lights = find_by_class(unreal.SkyLight)
    if not lights:
        light = spawn(unreal.SkyLight, unreal.Vector(0, 0, 400))
        mark_fixed("SkyLight yaratildi")
    else:
        light = lights[0]
    comp = light_component(light)
    if comp is not None and not nearly(comp.get_editor_property("intensity"), SKYLIGHT_FILL, 0.05):
        comp.set_editor_property("intensity", SKYLIGHT_FILL)
        mark_fixed(f"SkyLight to'ldirish {SKYLIGHT_FILL} qilindi")
    report("OK", "SkyLight spetsifikatsiyada")


def ensure_point_light(label: str, loc: unreal.Vector, candelas: float,
                       color, radius: float = 650.0) -> None:
    """Nomlangan PointLight (rim/fill) — idempotent, LIGHT_RIG_YAW bilan aylanadi."""
    loc = rotate_xy(loc, LIGHT_RIG_YAW)
    named = [a for a in find_by_class(unreal.PointLight) if a.get_actor_label() == label]
    if named:
        light = named[0]
        ensure_transform(light, loc, None, label)
    else:
        # Eski nomsiz rim'ni qayta ishlatamiz (birinchi run), aks holda yangi.
        spare = [a for a in find_by_class(unreal.PointLight)
                 if not a.get_actor_label().startswith("Companion")]
        if spare:
            light = spare[0]
            ensure_transform(light, loc, None, label)
        else:
            light = spawn(unreal.PointLight, loc)
            mark_fixed(f"{label} yaratildi")
        light.set_actor_label(label)
    comp = light_component(light)
    if comp.get_editor_property("intensity_units") != unreal.LightUnits.CANDELAS:
        comp.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
        mark_fixed(f"{label} birligi candela")
    if not nearly(comp.get_editor_property("intensity"), candelas, 0.5):
        comp.set_editor_property("intensity", candelas)
        mark_fixed(f"{label} {candelas} cd")
    if not color_near(comp.get_editor_property("light_color"), color):
        comp.set_editor_property("light_color", color)
        mark_fixed(f"{label} rangi o'rnatildi")
    if not nearly(comp.get_editor_property("attenuation_radius"), radius, 5.0):
        comp.set_editor_property("attenuation_radius", radius)
        mark_fixed(f"{label} radius {radius}")
    report("OK", f"{label} spetsifikatsiyada")


def ensure_rims_and_fill() -> None:
    # Unclaw-uslub: kuchli qizil rim orqa-yuqori-o'ngdan (kadr yuqori-o'ng
    # yog'du), xiraroq ikkinchi rim orqa-chapdan (wrap), sovuq fill oldindan.
    ensure_point_light("CompanionRim1", RIM1_LOC, RIM1_CANDELAS, ACCENT_COLOR, 700.0)
    ensure_point_light("CompanionRim2", RIM2_LOC, RIM2_CANDELAS, ACCENT_COLOR, 650.0)
    ensure_point_light("CompanionFill", FILL_LOC, FILL_CANDELAS, FILL_COLOR, 800.0)


def ensure_post_process() -> None:
    # Kinematik mood: vignette (e'tiborni yuzga), bloom (rim fon yuqorisida
    # yog'du beradi), yengil iliq/qizg'ish ambient (Unclaw dark-red feel).
    existing = find_by_class(unreal.PostProcessVolume)
    if existing:
        ppv = existing[0]
        created = False
    else:
        ppv = spawn(unreal.PostProcessVolume)
        ppv.set_actor_label("CompanionPostProcess")
        created = True
        mark_fixed("PostProcessVolume yaratildi")
    ppv.set_editor_property("unbound", True)  # butun sahnaga ta'sir qiladi
    s = ppv.get_editor_property("settings")
    already = (not created
               and s.get_editor_property("override_vignette_intensity")
               and nearly(s.get_editor_property("vignette_intensity"), 0.5, 0.02))
    if not already:
        s.set_editor_property("override_vignette_intensity", True)
        s.set_editor_property("vignette_intensity", 0.5)
        s.set_editor_property("override_bloom_intensity", True)
        s.set_editor_property("bloom_intensity", 0.7)
        s.set_editor_property("override_color_gain", True)
        s.set_editor_property("color_gain", unreal.Vector4(1.0, 0.93, 0.93, 1.0))
        ppv.set_editor_property("settings", s)
        mark_fixed("PostProcess: vignette 0.5 + bloom 0.7 + iliq ambient")
    report("OK", "PostProcessVolume (mood) spetsifikatsiyada")


def main() -> None:
    ensure_level()
    ensure_metahuman()
    ensure_camera()
    ensure_directional()
    ensure_skylight()
    ensure_rims_and_fill()
    ensure_post_process()

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
