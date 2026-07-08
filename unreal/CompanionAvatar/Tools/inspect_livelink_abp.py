"""ABP_MH_LiveLink anim grafini tekshirish — LiveLinkPose tuguni sozlamalarini
chiqaradi. Headless:

    UnrealEditor-Cmd <uproject> -run=pythonscript -script=.../inspect_livelink_abp.py \
        -stdout -Unattended -NoP4 -NullRHI -NoSplash

Natija: Tools/inspect_livelink_result.txt
"""
from __future__ import annotations

from pathlib import Path

import unreal

RESULT = Path(__file__).resolve().parent / "inspect_livelink_result.txt"
lines: list[str] = []


def out(msg: str) -> None:
    lines.append(msg)
    RESULT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"INSPECT: {msg}")


def dump_graph(bp, graph_name: str) -> None:
    graph = unreal.BlueprintEditorLibrary.find_graph(bp, graph_name)
    if not graph:
        out(f"  graf topilmadi: {graph_name}")
        return
    out(f"  == {graph_name} ==")
    try:
        nodes = graph.get_graph_nodes_of_class(unreal.AnimGraphNode_Base)
    except Exception as exc:  # noqa: BLE001
        out(f"  AnimGraphNode ro'yxati olinmadi: {exc}")
        return
    for node in nodes:
        cls = node.get_class().get_name()
        out(f"  tugun: {cls}")
        try:
            inner = node.get_editor_property("node")
            out(f"    node: {inner}")
        except Exception as exc:  # noqa: BLE001
            out(f"    node o'qilmadi: {exc}")


def main() -> None:
    for path in (
        "/Game/MetaHumans/Common/Animation/ABP_MH_LiveLink",
        "/Game/MetaHumans/Common/Face/ABP_Face_PostProcess",
    ):
        out(f"ASSET: {path}")
        bp = unreal.load_asset(path)
        if not bp:
            out("  yuklanmadi!")
            continue
        # Barcha graflarni sanab chiqamiz.
        try:
            graphs = unreal.BlueprintEditorLibrary.list_graphs(bp)
            out(f"  graflar: {[g.get_name() for g in graphs]}")
            for g in graphs:
                dump_graph(bp, g.get_name())
        except Exception as exc:  # noqa: BLE001
            out(f"  graflar olinmadi: {exc}")


out("boshlandi")
try:
    main()
    out("DONE")
except Exception:  # noqa: BLE001
    import traceback
    for tb in traceback.format_exc().splitlines():
        out(tb)
    raise
