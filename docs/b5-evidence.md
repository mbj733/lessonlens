# B5 — USDZ export evidence

Executed: 2026-11-13 (Asia/Shanghai) · Repo: `E:\alsl项目\lessonlens`
Engine: `pxr.UsdUtils.ComplianceChecker` from `usd-core==25.11` (the code `usdchecker` runs).

## 1. What exists now

| file | role |
|---|---|
| `src/lessonlens/export_usdz.py` | scene.json → Usd stage → `.usdz`; compliance check; aggregate report |
| `src/lessonlens/cli.py` | `lessonlens export [--scenes …] [--out out] [--report …]` |
| `out/*.usdz` | 14 packages, 0.16 MB total, committed so Pages can serve a clickable AR asset |
| `eval/usdz-report.json` | machine-readable pass/fail for every package (consumed by `eval/report.md`) |
| `tests/test_export.py` | 6 cases, including a negative control |

Every object becomes `/Scene/<id>` (Xform with translate/scale) plus one procedural gprim; the claim
travels inside the file as `customData["lessonlens"] = {objectId, page, kind, label, quote, claimText}`,
and the deck id/title/page count live in `customLayerData`. The USDZ therefore carries its own
provenance instead of depending on a sidecar file.

## 2. Gate output

```
> .venv\Scripts\python.exe -m lessonlens export
deck                     objects  bytes  errors  warnings  status
en-01-sorting                 12  11632       0         0  PASS
en-01-sorting                 12  11993       0         0  PASS
en-02-bst                     12  12083       0         0  PASS
en-03-hashing                 12  11920       0         0  PASS
en-04-shortest-paths          12  11779       0         0  PASS
en-04-shortest-paths          12  11779       0         0  PASS
en-05-processes-threads       12  12038       0         0  PASS
zh-06-binary-tree             12  11706       0         0  PASS
zh-06-binary-tree             12  12030       0         0  PASS
zh-07-dp                      12  12124       0         0  PASS
zh-08-db-normalization        12  12489       0         0  PASS
zh-09-tcp                     12  11930       0         0  PASS
zh-09-tcp                     12  12357       0         0  PASS
zh-10-backprop                12  11716       0         0  PASS

14 packages -> out   report -> eval\usdz-report.json
```

`eval/report.md` picks the aggregate up:

```
## USDZ
- package: `14 packages`
- usdchecker-equivalent engine: **PASS** (errors: 0, warnings: 0)
```

The plan's criterion #6 ("`usdchecker out/scene.usdz` passes") is met through the identical engine
rather than the identical binary — no `usd-core` wheel ships `usdchecker.exe` on Windows, and 26.11
removed `ComplianceChecker` entirely (details in `docs/b0-evidence.md`).

## 3. Two defects found here

**(a) Relative paths silently fail `CreateNewUsdzPackage`.** The first run died with

```
Warning: ... Failed to resolve asset path: out\_layers\en-01-sorting.pdf.usda
RuntimeError: CreateNewUsdzPackage failed
```

The packager treats the source layer as an asset path and could not resolve a relative Windows path.
Fixed by resolving both the layer and the package to absolute paths before packaging.

**(b) A broken package passed the first version of the check.** `ComplianceChecker` routes "Stage has
missing or invalid defaultPrim" through `GetFailedChecks()`, **not** `GetErrors()`:

```
GetErrors()       -> []
GetFailedChecks() -> ["Stage has missing or invalid defaultPrim. (fails 'StageMetadataChecker')"]
```

The first implementation returned `status: PASS` whenever `GetErrors()` was empty, i.e. it would have
blessed a USDZ that Apple's Quick Look rejects. The check now fails on errors **or** failed checks,
and `tests/test_export.py::test_missing_default_prim_fails_the_check` keeps a defaultPrim-less package
as a permanent negative control.

## 4. Limits

- **No device:** no iPhone, no Vision Pro, no macOS. Nothing here proves the package opens in Quick
  Look or on visionOS; the README must say "USDZ passes the usdchecker engine (not tested on device)".
- No materials beyond `displayColor`, no textures, no animation — the plan's scope is procedural
  geometry, and the triangle estimate stays under 10k per scene.
- Materials are single-sided by default; the viewer's `plane` primitive is exported as a thin
  invisible-free quad, but the mock planner never emits `plane`.
- Compliance is not aesthetics: a passing package can still look wrong.

## 5. Reproduce

```powershell
.venv\Scripts\python.exe -m pip install -e ".[usd]"
.venv\Scripts\python.exe -m lessonlens export
.venv\Scripts\python.exe -m pytest tests/test_export.py -q
.venv\Scripts\python.exe -m lessonlens eval      # report picks up eval/usdz-report.json
```
