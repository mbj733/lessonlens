"""Export: scene.json -> USDZ, then validate the package with the engine behind `usdchecker`.

The plan's step 6 wants ``usdchecker out/scene.usdz`` to pass. The PyPI ``usd-core`` wheel ships no
``usdchecker`` binary on Windows and version 26.11 removed ``pxr.UsdUtils.ComplianceChecker``, so this
module pins 25.11 and calls the same engine directly (see ``docs/b0-evidence.md``).

Every object becomes a ``/Scene/<id>`` Xform with one procedural gprim, displayColor from the scene,
and the claim (page + quote) in ``customData``, so the 3D file itself carries its provenance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pxr import Gf, Usd, UsdGeom, UsdUtils


def _linear(color: str) -> Gf.Vec3f:
    """#rrggbb (sRGB) -> linear RGB, which is what USD displayColor expects."""
    value = color.lstrip("#")
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    converted = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return Gf.Vec3f(*converted)


def _gprim(stage: Usd.Stage, path: str, primitive: str) -> UsdGeom.Gprim:
    if primitive == "box":
        gprim = UsdGeom.Cube.Define(stage, path)
        gprim.CreateSizeAttr(1.0)
    elif primitive == "sphere":
        gprim = UsdGeom.Sphere.Define(stage, path)
        gprim.CreateRadiusAttr(0.5)
    elif primitive == "cylinder":
        gprim = UsdGeom.Cylinder.Define(stage, path)
        gprim.CreateRadiusAttr(0.5)
        gprim.CreateHeightAttr(1.0)
    elif primitive == "cone":
        gprim = UsdGeom.Cone.Define(stage, path)
        gprim.CreateRadiusAttr(0.5)
        gprim.CreateHeightAttr(1.0)
    elif primitive == "plane":
        # USD has no plane gprim; a thin cube keeps the package ARKit-safe and the triangle budget low.
        mesh = UsdGeom.Mesh.Define(stage, path)
        half = 0.5
        mesh.CreatePointsAttr(
            [
                Gf.Vec3f(-half, 0, -half),
                Gf.Vec3f(half, 0, -half),
                Gf.Vec3f(half, 0, half),
                Gf.Vec3f(-half, 0, half),
            ]
        )
        mesh.CreateFaceVertexCountsAttr([3, 3])
        mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 0, 2, 3])
        mesh.CreateExtentAttr([Gf.Vec3f(-half, 0, -half), Gf.Vec3f(half, 0, half)])
        gprim = mesh
    else:
        raise ValueError(f"unsupported primitive: {primitive}")
    return gprim


def build_stage(scene: dict[str, Any], path: str | Path) -> Usd.Stage:
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/Scene")
    stage.SetDefaultPrim(root.GetPrim())
    stage.SetMetadata(
        "customLayerData",
        {
            "lessonlens:deck": scene["deck"]["id"],
            "lessonlens:title": scene["deck"]["title"],
            "lessonlens:pages": int(scene["deck"]["pages"]),
            "lessonlens:schema": scene["schema"],
        },
    )

    for obj in scene["objects"]:
        prim_path = f"/Scene/{obj['id']}"
        xform = UsdGeom.Xform.Define(stage, prim_path)
        xform.AddTranslateOp().Set(Gf.Vec3f(*obj["position"]))
        xform.AddScaleOp().Set(Gf.Vec3f(*obj["scale"]))
        if "rotation" in obj:
            xform.AddRotateXYZOp().Set(Gf.Vec3f(*obj["rotation"]))

        gprim = _gprim(stage, f"{prim_path}/geom", obj["primitive"])
        gprim.CreateDisplayColorAttr([_linear(obj["color"])])
        label = obj["label"]
        gprim.GetPrim().SetCustomDataByKey(
            "lessonlens",
            {
                "objectId": obj["id"],
                "page": int(obj["page"]),
                "kind": obj["kind"],
                "label": label,
                "quote": obj["claims"][0]["quote"],
                "claimText": obj["claims"][0]["text"],
            },
        )
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    stage.GetRootLayer().Save()
    return stage


def check_package(path: str | Path, *, arkit: bool = True) -> dict[str, Any]:
    """Same contract as `usdchecker`: a package fails on errors *and* on failed checks.

    ``ComplianceChecker`` reports "missing defaultPrim" through ``GetFailedChecks()`` while
    ``GetErrors()`` stays empty, so checking only the error list would pass broken packages.
    """
    checker = UsdUtils.ComplianceChecker(
        arkit=arkit,
        skipARKitRootLayerCheck=False,
        rootPackageOnly=False,
        skipVariants=False,
    )
    checker.CheckCompliance(str(path))
    errors = list(checker.GetErrors())
    warnings = list(checker.GetWarnings())
    failed = list(checker.GetFailedChecks())
    ok = not errors and not failed
    return {
        "package": Path(path).name,
        "status": "PASS" if ok else "FAIL",
        "errors": len(errors),
        "warnings": len(warnings),
        "failed_checks": [str(item) for item in failed],
        "error_messages": [str(item) for item in errors][:20],
        "warning_messages": [str(item) for item in warnings][:20],
    }


def export_scene(scene: dict[str, Any], out_path: str | Path, *, work_dir: str | Path) -> dict[str, Any]:
    """Write ``<out_path>`` (a .usdz) and return its compliance report."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    # Absolute paths matter: CreateNewUsdzPackage resolves the layer as an asset path, and a
    # relative one silently fails to package on Windows.
    layer = work_dir / f"{out_path.stem}.usda"
    package = out_path.resolve()

    stage = build_stage(scene, layer)
    del stage  # flush handles before packaging
    ok = UsdUtils.CreateNewUsdzPackage(str(layer.resolve()), str(package))
    if not ok or not package.exists():
        raise RuntimeError(f"CreateNewUsdzPackage failed for {package}")

    report = check_package(package)
    report["bytes"] = package.stat().st_size
    report["objects"] = len(scene["objects"])
    report["deck"] = scene["deck"]["id"]
    report["path"] = out_path.as_posix()
    return report

def write_aggregate(reports: list[dict[str, Any]], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = all(item["status"] == "PASS" for item in reports) and bool(reports)
    aggregate = {
        "package": f"{len(reports)} packages",
        "status": "PASS" if ok else "FAIL",
        "errors": sum(item["errors"] for item in reports),
        "warnings": sum(item["warnings"] for item in reports),
        "failed_checks": sum(len(item["failed_checks"]) for item in reports),
        "ok": ok,
        "packages": reports,
    }
    path.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return path


def load_scenes(scenes_dir: str | Path) -> list[tuple[str, dict[str, Any]]]:
    items = []
    for path in sorted(Path(scenes_dir).glob("*.json")):
        if path.name == "index.json":
            continue
        items.append((path.name, json.loads(path.read_text("utf-8"))))
    return items


def export_all(scenes_dir: str | Path, out_dir: str | Path, *, work_dir: str | Path | None = None) -> list[dict[str, Any]]:
    out_dir = Path(out_dir)
    work_dir = Path(work_dir) if work_dir else out_dir / "_layers"
    reports = []
    for name, scene in load_scenes(scenes_dir):
        package = out_dir / f"{Path(name).stem}.usdz"
        reports.append(export_scene(scene, package, work_dir=work_dir))
    return reports
