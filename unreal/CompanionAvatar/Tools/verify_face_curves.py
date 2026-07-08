#!/usr/bin/env python3
"""Yuz lab-sinxron zanjiri (LiveLink yo'li) butunligini TEZ tekshirish — editor'siz.

    python3 unreal/CompanionAvatar/Tools/verify_face_curves.py

Zanjir: CompanionLipSync --LiveLink push--> ABP_MH_LiveLink
        --PA_MetaHuman_ARKit_Mapping--> yuz rigi.

Skript statik tekshiradi:
  1. ABP_MH_LiveLink va PA_MetaHuman_ARKit_Mapping assetlari joyida;
  2. PoseAsset'da ARKit poza nomlari (JawOpen, MouthSmileLeft, ...) bor;
  3. BP_NewMetaHumanCharacter'da UseARKit/LLink_Face_Subj bor;
  4. Kompilyatsiya qilingan modulda LiveLink push kodi bor
     (dylib ichida "LLink_Face_Subj").

Runtime tekshiruv esa avtomatik: o'yin paytida CompanionDirector logga
"Yuz curve oqimi OK" yoki aniq ogohlantirish yozadi (1.5s kechikish bilan,
birinchi avatar.play'dan keyin).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
UE_DIR = REPO / "unreal/CompanionAvatar"

CHECKS: list[tuple[str, Path, list[bytes]]] = [
    (
        "ABP_MH_LiveLink (LiveLink yuz rigi)",
        UE_DIR / "Content/MetaHumans/Common/Animation/ABP_MH_LiveLink.uasset",
        [b"AnimNode_LiveLinkPose", b"LLink_Face_Subj"],
    ),
    (
        "PA_MetaHuman_ARKit_Mapping (ARKit pozalar)",
        UE_DIR / "Content/MetaHumans/Common/Face/ARKit/PA_MetaHuman_ARKit_Mapping.uasset",
        [b"JawOpen", b"MouthSmileLeft", b"BrowInnerUp", b"EyeBlinkLeft"],
    ),
    (
        "BP_NewMetaHumanCharacter (ARKit rejim bayroqlari)",
        UE_DIR / "Content/MetaHumans/NewMetaHumanCharacter/BP_NewMetaHumanCharacter.uasset",
        [b"UseARKit", b"LiveLinkSubjectName", b"LLink_Face_Subj"],
    ),
    (
        "Kompilyatsiya qilingan modul (LiveLink push kodi)",
        UE_DIR / "Binaries/Mac/libUnrealEditor-CompanionAvatar.dylib",
        [b"LLink_Face_Subj", b"CompanionLipSync"],
    ),
]


def main() -> int:
    ok = True
    for title, path, needles in CHECKS:
        if not path.exists():
            print(f"❌ {title}: fayl yo'q — {path.relative_to(REPO)}")
            ok = False
            continue
        data = path.read_bytes()
        # TEXT() literallar dylib'da UTF-16 bo'ladi — ikkala kodlashda qidiramiz.
        def found(needle: bytes) -> bool:
            return needle in data or needle.decode().encode("utf-16-le") in data
        missing = [n.decode() for n in needles if not found(n)]
        if missing:
            print(f"❌ {title}: ichida topilmadi: {missing}")
            ok = False
        else:
            print(f"✅ {title}")

    if ok:
        print("\nNATIJA: zanjir butun ✅ — runtime'da Director logi yakuniy tasdiq beradi.")
        return 0
    print("\nNATIJA: zanjir uzilgan ❌ — yuqoridagi bandlarga qarang.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
