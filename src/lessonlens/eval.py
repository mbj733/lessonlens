"""Evaluation: turn verified scenes into the metric table in ``eval/report.md``.

Every number in the report is computed here — nothing is typed by hand (plan H2). The report is
byte-stable for a given set of scenes, so CI can diff it.

Definitions (also printed in the report):

``schema_pass_rate``     scenes that satisfy the JSON Schema and the cross-reference rules / scenes
``grounding_coverage``   objects with at least one SUPPORTED claim / objects
``quote_hit_rate``       claims whose quote occurs on the page they name / claims
``unsupported_rate``     claims that are not SUPPORTED (wrong page, ungrounded or missing) / claims
``task_solvable_rate``   tasks whose answers all point at existing objects / tasks
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ingest import Document, extract_document
from .planner import TRIANGLES, validate_scene
from .verify import SUPPORTED, SceneCheck, check_scene, self_test

ROOT = Path(__file__).resolve().parents[2]


def load_scenes(scenes_dir: str | Path) -> list[dict[str, Any]]:
    scenes = []
    for path in sorted(Path(scenes_dir).glob("*.json")):
        if path.name == "index.json":
            continue
        scenes.append(json.loads(path.read_text("utf-8")))
    return scenes


@dataclass
class Metrics:
    decks: int = 0
    objects: int = 0
    claims: int = 0
    tasks: int = 0
    schema_pass_rate: float = 0.0
    grounding_coverage: float = 0.0
    quote_hit_rate: float = 0.0
    unsupported_rate: float = 0.0
    task_solvable_rate: float = 0.0
    max_triangles: int = 0
    max_scene_bytes: int = 0
    verdicts: dict[str, int] = field(default_factory=dict)
    per_deck: list[dict[str, Any]] = field(default_factory=list)
    self_test: dict[str, Any] = field(default_factory=dict)
    web: dict[str, Any] = field(default_factory=dict)
    usdz: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decks": self.decks,
            "objects": self.objects,
            "claims": self.claims,
            "tasks": self.tasks,
            "schema_pass_rate": round(self.schema_pass_rate, 4),
            "grounding_coverage": round(self.grounding_coverage, 4),
            "quote_hit_rate": round(self.quote_hit_rate, 4),
            "unsupported_rate": round(self.unsupported_rate, 4),
            "task_solvable_rate": round(self.task_solvable_rate, 4),
            "max_triangles": self.max_triangles,
            "max_scene_bytes": self.max_scene_bytes,
            "verdicts": self.verdicts,
            "per_deck": self.per_deck,
            "self_test": self.self_test,
            "web": self.web,
            "usdz": self.usdz,
        }


def evaluate(scenes: list[dict[str, Any]], *, root: str | Path | None = None) -> tuple[Metrics, list[SceneCheck]]:
    root = Path(root or ROOT)
    metrics = Metrics(decks=len(scenes))
    checks: list[SceneCheck] = []
    pairs: list[tuple[dict[str, Any], Document]] = []

    schema_pass = 0
    objects_total = 0
    claims_total = 0
    tasks_total = 0
    solvable_tasks = 0
    grounded_objects = 0
    quote_hits = 0
    unsupported = 0
    verdict_totals: dict[str, int] = {}
    max_triangles = 0
    max_bytes = 0

    for scene in scenes:
        scene_bytes = len(json.dumps(scene, ensure_ascii=False).encode("utf-8"))
        max_bytes = max(max_bytes, scene_bytes)
        triangles = sum(TRIANGLES[obj["primitive"]] for obj in scene["objects"])
        max_triangles = max(max_triangles, triangles)

        errors = validate_scene(scene)
        doc = extract_document(root / scene["deck"]["source"], root=root)
        check = check_scene(scene, doc)
        check.schema_ok = not errors
        check.schema_errors = errors
        checks.append(check)
        pairs.append((scene, doc))

        if not errors:
            schema_pass += 1
        objects_total += len(scene["objects"])
        claims_total += len(check.claims)
        tasks_total += len(scene["tasks"])
        grounded_objects += check.objects_with_supported_claim
        quote_hits += sum(1 for claim in check.claims if claim.page in claim.quote_pages)
        unsupported += sum(1 for claim in check.claims if claim.verdict != SUPPORTED)
        ids = {obj["id"] for obj in scene["objects"]}
        for task in scene["tasks"]:
            if task["answers"] and all(answer in ids for answer in task["answers"]):
                solvable_tasks += 1
        for verdict, count in check.verdicts().items():
            verdict_totals[verdict] = verdict_totals.get(verdict, 0) + count

        metrics.per_deck.append(
            {
                "deck": scene["deck"]["id"],
                "file": f"{Path(scene['deck']['source']).name}.json",
                "objects": len(scene["objects"]),
                "claims": len(check.claims),
                "schema": "pass" if not errors else "FAIL",
                "supported": check.supported,
                "verdicts": check.verdicts(),
                "triangles": triangles,
                "bytes": scene_bytes,
            }
        )

    metrics.objects = objects_total
    metrics.claims = claims_total
    metrics.tasks = tasks_total
    metrics.schema_pass_rate = schema_pass / len(scenes) if scenes else 0.0
    metrics.grounding_coverage = grounded_objects / objects_total if objects_total else 0.0
    metrics.quote_hit_rate = quote_hits / claims_total if claims_total else 0.0
    metrics.unsupported_rate = unsupported / claims_total if claims_total else 0.0
    metrics.task_solvable_rate = solvable_tasks / tasks_total if tasks_total else 0.0
    metrics.max_triangles = max_triangles
    metrics.max_scene_bytes = max_bytes
    metrics.verdicts = dict(sorted(verdict_totals.items()))
    metrics.self_test = self_test(pairs)
    return metrics, checks


# --------------------------------------------------------------------------- report


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _verdict_table(verdicts: dict[str, int]) -> str:
    rows = ["| verdict | claims |", "|---|---|"]
    for verdict, count in sorted(verdicts.items()):
        rows.append(f"| `{verdict}` | {count} |")
    return "\n".join(rows)


def write_report(metrics: Metrics, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = metrics.to_dict()
    st_rate = metrics.self_test.get("total", {}).get("rate", 0.0)

    lines = [
        "# LessonLens evaluation report",
        "",
        "Generated by `python -m lessonlens eval` from the committed scenes in `eval/scenes/`.",
        "**Do not edit by hand** — every number below is recomputed from the artifacts.",
        "",
        "## Headline",
        "",
        "| metric | value | target | pass |",
        "|---|---|---|---|",
        f"| schema_pass_rate | {_pct(metrics.schema_pass_rate)} | 100% | {'yes' if metrics.schema_pass_rate == 1 else 'NO'} |",
        f"| grounding_coverage | {_pct(metrics.grounding_coverage)} | ≥ 80% | {'yes' if metrics.grounding_coverage >= 0.8 else 'NO'} |",
        f"| quote_hit_rate | {_pct(metrics.quote_hit_rate)} | ≥ 85% | {'yes' if metrics.quote_hit_rate >= 0.85 else 'NO'} |",
        f"| unsupported_rate | {_pct(metrics.unsupported_rate)} | ≤ 10% | {'yes' if metrics.unsupported_rate <= 0.10 else 'NO'} |",
        f"| task_solvable_rate | {_pct(metrics.task_solvable_rate)} | 100% | {'yes' if metrics.task_solvable_rate == 1 else 'NO'} |",
        f"| verifier self-test | {_pct(st_rate)} | 100% | {'yes' if st_rate == 1 else 'NO'} |",
        "",
        f"Scope: **{metrics.decks} scenes · {metrics.objects} objects · {metrics.claims} claims · "
        f"{metrics.tasks} tasks**. Largest scene {metrics.max_scene_bytes:,} bytes (compact JSON), "
        f"largest triangle estimate {metrics.max_triangles:,}.",
        "",
        "## Verdicts",
        "",
        _verdict_table(metrics.verdicts),
        "",
        "## Per deck",
        "",
        "| deck | file | objects | claims | supported | schema | triangles | bytes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in metrics.per_deck:
        lines.append(
            f"| {row['deck']} | `{row['file']}` | {row['objects']} | {row['claims']} | "
            f"{row['supported']} | {row['schema']} | {row['triangles']:,} | {row['bytes']:,} |"
        )

    lines += ["", "## Verifier self-test (negative control)", ""]
    lines += [
        "Known-good scenes are deliberately corrupted; every corruption must be caught, otherwise the",
        "metrics above would be measuring nothing.",
        "",
        "| corruption | trials | detected | rate |",
        "|---|---|---|---|",
    ]
    for kind, item in sorted(metrics.self_test.get("corruptions", {}).items()):
        lines.append(f"| {kind} | {item['trials']} | {item['detected']} | {_pct(item['rate'])} |")
    total = metrics.self_test.get("total", {})
    lines.append(f"| **total** | **{total.get('trials', 0)}** | **{total.get('detected', 0)}** | **{_pct(total.get('rate', 0.0))}** |")

    lines += ["", "## Web runtime", ""]
    if metrics.web:
        lines += [
            f"- first frame: **{metrics.web.get('first_frame_ms')} ms**",
            f"- largest-contentful-paint entries: {metrics.web.get('lcp_entries', 0)} "
            f"(a canvas page has none; the first-frame number is the honest proxy)",
            f"- browser gate: {metrics.web.get('checks_passed')}/{metrics.web.get('checks_total')} assertions passed",
            f"- source: `{metrics.web.get('source', 'eval/web-metrics.json')}`",
        ]
    else:
        lines.append("No `eval/web-metrics.json` found; run `tools/web_check.py` to record the browser gate.")

    lines += ["", "## USDZ", ""]
    if metrics.usdz:
        lines += [
            f"- package: `{metrics.usdz.get('package')}`",
            f"- usdchecker-equivalent engine: **{metrics.usdz.get('status')}** "
            f"(errors: {metrics.usdz.get('errors')}, warnings: {metrics.usdz.get('warnings')})",
        ]
    else:
        lines.append("No `out/usdz-report.json` found; run `python -m lessonlens export` (batch B5).")

    lines += [
        "",
        "## Definitions",
        "",
        "- `schema_pass_rate` — scenes that satisfy `schema/scene.schema.json` **and** the cross-reference",
        "  rules (answer/target ids exist, pages in range, triangle budget consistent).",
        "- `grounding_coverage` — objects with at least one claim whose quote really occurs on its page.",
        "- `quote_hit_rate` — claims whose quote occurs on the page they name, after whitespace",
        "  normalisation.",
        "- `unsupported_rate` — claims that are not `SUPPORTED` (wrong page, ungrounded, or missing).",
        "- `task_solvable_rate` — tasks whose answers are non-empty and all point at existing objects.",
        "- `verifier self-test` — corruption trials in `lessonlens.verify.self_test` whose effect the",
        "  gates detected.",
        "",
        "## Honest notes",
        "",
        "- These scenes come from the **mock planner**, whose claim text is a prefix of the slide quote.",
        "  A rule engine cannot hallucinate, so the grounding metrics are perfect by construction; they",
        "  become informative only when a model generates the claims (`--llm deepseek`, not exercised",
        "  against the live API in this environment).",
        "- The grounding gate is **lexical** (token/bigram overlap ≥ 0.5), not semantic. A paraphrase",
        "  that shares no tokens with its quote would be marked `UNGROUNDED`.",
        "- `quote_hit_rate` uses the same normalisation as ingest (whitespace collapsed, control",
        "  characters removed); it does not tolerate reordered words or edited numbers.",
        "",
    ]

    path.write_text("\n".join(lines), "utf-8")
    (path.parent / "metrics.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    return path


def load_web_metrics(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    candidate = Path(path)
    if not candidate.exists():
        return {}
    payload = json.loads(candidate.read_text("utf-8"))
    payload.setdefault("source", str(candidate))
    return payload


def load_usdz_report(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    candidate = Path(path)
    if not candidate.exists():
        return {}
    return json.loads(candidate.read_text("utf-8"))
