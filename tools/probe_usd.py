"""Environment probe: USDZ packaging + the same compliance engine `usdchecker` wraps.

Why this file exists: the PyPI `usd-core` wheel ships no `usdchecker.exe` on Windows,
and usd-core 26.11 removed `UsdUtils.ComplianceChecker` outright. We pin 25.11 and
call the official engine directly, so batch B5 has a validator before any exporter
code is written.

Usage:
    python tools/probe_usd.py            # builds out/_probe.usdz and validates it
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from pxr import Gf, Usd, UsdGeom, UsdUtils


def build_probe_stage(path: Path) -> None:
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/Scene")
    stage.SetDefaultPrim(root.GetPrim())
    cube = UsdGeom.Cube.Define(stage, "/Scene/Cube")
    cube.CreateSizeAttr(1.0)
    cube.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.5, 0.0))
    stage.GetRootLayer().Save()


def validate(package: Path) -> int:
    """Mirror `usdchecker --arkit`: 0 = no errors, 1 = errors found."""
    checker = UsdUtils.ComplianceChecker(arkit=True, skipARKitRootLayerCheck=False)
    checker.CheckCompliance(str(package))
    errors = checker.GetErrors()
    failed = checker.GetFailedChecks()
    warnings = checker.GetWarnings()
    for msg in errors:
        print(f"[ERROR] {msg}")
    for msg in warnings:
        print(f"[WARN]  {msg}")
    print(f"failed_checks={failed}")
    print(f"errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors else 0


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="ll-usdprobe-"))
    layer = out_dir / "probe.usda"
    package = out_dir / "probe.usdz"
    build_probe_stage(layer)
    ok = UsdUtils.CreateNewUsdzPackage(str(layer), str(package))
    print(f"staged={layer}")
    print(f"packaged={package} ok={ok} size={package.stat().st_size if package.exists() else 0}")
    if not ok or not package.exists():
        return 2
    return validate(package)


if __name__ == "__main__":
    sys.exit(main())
