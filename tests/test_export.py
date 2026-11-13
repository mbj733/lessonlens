"""B5 gate: every scene exports to a USDZ that the `usdchecker` engine passes, with provenance inside."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pxr")

from pxr import Usd, UsdGeom  # noqa: E402

from lessonlens.export_usdz import (  # noqa: E402
    build_stage,
    check_package,
    export_all,
    export_scene,
    write_aggregate,
)

ROOT = Path(__file__).resolve().parents[1]
SCENES = ROOT / "eval" / "scenes"


def load_scene(name: str) -> dict:
    return json.loads((SCENES / name).read_text("utf-8"))


@pytest.fixture(scope="session")
def scene() -> dict:
    return load_scene("zh-09-tcp.pptx.json")


def test_scene_exports_and_passes(scene: dict, tmp_path: Path) -> None:
    report = export_scene(scene, tmp_path / "pkg.usdz", work_dir=tmp_path / "layers")
    assert report["status"] == "PASS", report["error_messages"]
    assert report["errors"] == 0
    assert report["objects"] == 12
    assert report["bytes"] > 1000
    assert (tmp_path / "pkg.usdz").exists()


def test_stage_carries_geometry_and_provenance(scene: dict, tmp_path: Path) -> None:
    layer = tmp_path / "scene.usda"
    build_stage(scene, layer)

    stage = Usd.Stage.Open(str(layer))
    default_prim = stage.GetDefaultPrim()
    assert default_prim and default_prim.GetPath().pathString == "/Scene"
    assert UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.y
    assert UsdGeom.GetStageMetersPerUnit(stage) == pytest.approx(1.0)

    children = [child.GetName() for child in default_prim.GetChildren()]
    assert len(children) == 12
    assert children[0] == "o01"

    payload = default_prim.GetChild("o01").GetChild("geom").GetCustomDataByKey("lessonlens")
    assert payload["objectId"] == "o01"
    assert payload["page"] >= 1
    assert len(payload["quote"]) > 10

    layer_data = stage.GetMetadata("customLayerData")
    assert layer_data["lessonlens:deck"] == scene["deck"]["id"]


def test_every_scene_in_the_corpus_exports(tmp_path: Path) -> None:
    reports = export_all(SCENES, tmp_path, work_dir=tmp_path / "layers")
    assert len(reports) == 14
    assert all(item["status"] == "PASS" for item in reports), [
        (item["deck"], item["error_messages"]) for item in reports if item["status"] != "PASS"
    ]
    assert all(item["errors"] == 0 for item in reports)


def test_aggregate_report(scene: dict, tmp_path: Path) -> None:
    report = export_scene(scene, tmp_path / "pkg.usdz", work_dir=tmp_path / "layers")
    target = write_aggregate([report], tmp_path / "usdz-report.json")
    payload = json.loads(target.read_text("utf-8"))
    assert payload["ok"] is True
    assert payload["status"] == "PASS"
    assert payload["packages"][0]["deck"] == scene["deck"]["id"]


def test_missing_default_prim_fails_the_check(tmp_path: Path) -> None:
    """Negative control: a package without a default prim must not pass."""
    from pxr import UsdUtils

    layer = tmp_path / "bad.usda"
    stage = Usd.Stage.CreateNew(str(layer))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.Cube.Define(stage, "/Loose/Cube").CreateSizeAttr(1.0)
    stage.GetRootLayer().Save()
    del stage

    package = tmp_path / "bad.usdz"
    assert UsdUtils.CreateNewUsdzPackage(str(layer.resolve()), str(package.resolve()))
    report = check_package(package)
    # ComplianceChecker routes "missing defaultPrim" through GetFailedChecks(), not GetErrors().
    assert report["failed_checks"], report
    assert report["status"] == "FAIL"


def test_committed_report_says_pass() -> None:
    payload = json.loads((ROOT / "eval" / "usdz-report.json").read_text("utf-8"))
    assert payload["ok"] is True
    assert payload["status"] == "PASS"
    assert len(payload["packages"]) == 14
    assert all(item["errors"] == 0 for item in payload["packages"])
