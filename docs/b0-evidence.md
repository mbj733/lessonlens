# B0 — Environment evidence

Executed: 2026-11-13 (Asia/Shanghai) · Host: Windows 11 · Workspace: `E:\alsl项目\lessonlens`
Every line below is copied from a command that was actually run, not typed from memory.

## 1. Toolchain

| Item | Value | How it was observed |
|---|---|---|
| Python | 3.12.10 (`C:\Program Files\Python312\python.exe`) | `python -V` |
| venv | `.venv` in repo, created with `python -m venv` (4 s) | `Get-ChildItem` / `python -V` on venv python |
| git | 2.55.0.windows.1 (`D:\dev\git\cmd\git.exe`) | `git --version` |
| pip | latest (`pip install -U pip`, exit 0) | install log |

Installed via `pip install -e ".[dev]"` (exit 0, 19.3 s):

```
pdfplumber==0.11.10   pdfminer.six==20260107   python-pptx==1.0.2
jsonschema==4.26.0    lxml==6.1.3              pillow==13.0.0
pytest==9.2.0         ruff==0.17.5             cryptography==50.0.2
usd-core==25.11
```

## 2. B0 gate (the plan's literal verification command)

```
> .venv\Scripts\python.exe -c "import pdfplumber, jsonschema; print('OK', pdfplumber.__version__, jsonschema.__version__)"
OK 0.11.10 4.26.0
exit=0
```

`python -c "import pdfplumber, jsonschema"` on its own also exits 0; the print only makes the
version visible.

## 3. Lint + tests

```
> .venv\Scripts\python.exe -m ruff check .
All checks passed!
exit=0

> .venv\Scripts\python.exe -m pytest -q
...                                                                      [100%]
exit=0
```

3 tests in `tests/test_env.py`: python ≥ 3.11, the three ingest/validation deps import and report a
version, and `import lessonlens` exposes `__version__ == "0.1.0"`.

## 4. Risk R1 resolved early: USDZ validation on Windows

The plan assumed `usdchecker` ships with `usd-core`. On this platform it does **not**, and the newest
release is worse than "missing CLI":

| Probe | Result |
|---|---|
| `Get-ChildItem .venv\Scripts -Filter 'usd*'` | 0 files — no `usdchecker.exe`, no `usdzip.exe` |
| `importlib.metadata.entry_points('usd-core')` on 26.11 | empty — the wheel declares no console scripts |
| wheel scan of `usd_core-24.11` / `25.11` / `26.11` for `ComplianceChecker` | 24.11 ✅, 25.11 ✅, **26.11 ❌ (removed)** |

So `usd-core==26.11` breaks the only official way to validate a USDZ from Python, and no version
provides the CLI on Windows. Decision: **pin `usd-core==25.11`** and call the engine `usdchecker`
wraps, `pxr.UsdUtils.ComplianceChecker`, directly.

```
> .venv\Scripts\python.exe tools\probe_usd.py
staged=C:\...\ll-usdprobe-sy6b_7m5\probe.usda
packaged=C:\...\ll-usdprobe-sy6b_7m5\probe.usdz ok=True size=434
failed_checks=[]
errors=0 warnings=0
probe exit=0
```

`tools/probe_usd.py` builds a cube stage → `UsdUtils.CreateNewUsdzPackage` → `ComplianceChecker(arkit=True)`
and exits non-zero on any error, i.e. the same contract as `usdchecker --arkit`. B5 will expose it as a
`usdchecker` console script so the plan's literal command resolves inside the venv.

Deviation recorded: success criterion #6 in the plan (`usdchecker out/scene.usdz`) is satisfied through
the identical engine, not the identical binary, because the binary does not exist for Windows.

## 5. Reproduce from a clean clone

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -U pip
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pip install usd-core==25.11   # extras: .[usd]
.venv\Scripts\python.exe tools\probe_usd.py
```

## 6. What B0 deliberately did **not** do

- No `scene.json` schema yet (B2), no ingest code (B1) — the directories exist and are empty.
- CI is written but has not run on GitHub yet: the repo is initialized locally, first push happens at
  B6 or earlier on demand.
- `pillow` is installed for the B3/B6 media pipeline but nothing uses it yet.
