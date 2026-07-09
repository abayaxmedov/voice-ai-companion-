#!/usr/bin/env python3
"""Idle "tiriklik"ni editorsiz o'lchaydigan tekshiruv (nigoh + bosh + suyak).

    python3 unreal/CompanionAvatar/Tools/verify_idle_life.py

UE'ni -game -RenderOffscreen rejimida ishga tushiradi (bridge/stack SHART EMAS —
idle harakat BeginPlay'dan boshlanadi), CompanionDirector'ning
"Idle tiriklik OK (...)" logini kutadi va raqamlarni chegaralarga solishtiradi:
  - nigoh max  > 0.05  (ko'z curve'lari harakatlanyapti)
  - saccades   >= 2    (nigoh sakrashlari bo'ldi)
  - bosh suyagi og'ishi > 0.15 deg (HeadYaw/Pitch/Roll ABP orqali suyakni burdi)

Chiqish kodi 0 = PASS, 1 = FAIL/uzilgan zanjir, 2 = ishga tushmadi.
"""
from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
UE = "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor"
PROJ = REPO / "unreal/CompanionAvatar/CompanionAvatar.uproject"
LOG = Path("/tmp/companion_idle_life.log")

GAZE_MIN = 0.05
SACCADES_MIN = 2
HEAD_BONE_MIN = 0.15  # deg

PATTERN = re.compile(
    r"Idle tiriklik OK \(nigoh max=([\d.]+), saccades=(\d+), "
    r"bosh gradus=([\d.]+), bosh suyagi og'ishi=([\d.]+) deg\)"
)


def main() -> int:
    if not Path(UE).exists():
        print(f"XATO: UnrealEditor topilmadi: {UE}")
        return 2
    if LOG.exists():
        LOG.unlink()

    proc = subprocess.Popen(
        ["nice", "-n", "5", UE, str(PROJ), "-game", "-RenderOffscreen",
         "-ResX=640", "-ResY=360", "-Unattended", "-NoSplash", f"-ABSLOG={LOG}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"UE ishga tushdi (PID={proc.pid}), idle tiriklik o'lchanmoqda...")

    match = None
    deadline = time.monotonic() + 240  # 8GB Mac'da yuklanish sekin
    try:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                print("XATO: UE erta chiqib ketdi")
                break
            if LOG.exists():
                text = LOG.read_text(errors="ignore")
                match = PATTERN.search(text)
                if match:
                    break
                if "bosh suyagi qimirlamayapti" in text:
                    print("OGOHLANTIRISH: bosh gradusi bor-u, suyak qimirlamayapti")
            time.sleep(3)
    finally:
        try:
            os.kill(proc.pid, signal.SIGTERM)
            time.sleep(2)
            os.kill(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    if not match:
        print("FAIL: 'Idle tiriklik OK' logi topilmadi (timeout yoki xato)")
        return 1

    gaze, saccades, head_deg, head_bone = (
        float(match.group(1)), int(match.group(2)),
        float(match.group(3)), float(match.group(4)),
    )
    print(f"O'lchandi: nigoh={gaze:.2f} saccades={saccades} "
          f"bosh_gradus={head_deg:.2f} bosh_suyagi={head_bone:.2f}deg")

    ok = True
    if gaze < GAZE_MIN:
        print(f"  FAIL nigoh {gaze:.3f} < {GAZE_MIN}"); ok = False
    if saccades < SACCADES_MIN:
        print(f"  FAIL saccades {saccades} < {SACCADES_MIN}"); ok = False
    if head_bone < HEAD_BONE_MIN:
        print(f"  FAIL bosh suyagi {head_bone:.3f} < {HEAD_BONE_MIN} deg "
              f"(HeadYaw/Pitch/Roll ABP'ga yetmayapti)"); ok = False

    print("NATIJA: PASS ✅ — personaj idle'da tirik" if ok else "NATIJA: FAIL ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
