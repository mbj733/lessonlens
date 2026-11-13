"""Command line entry point.

    python -m lessonlens --version
    python -m lessonlens ingest eval/slides --out eval/extract
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .eval import evaluate, load_scenes, load_usdz_report, load_web_metrics, write_report
from .ingest import extract_paths, write_extract
from .planner import PlannerError, build_provider


def _cmd_ingest(args: argparse.Namespace) -> int:
    docs = extract_paths(args.paths, root=args.root or Path.cwd())
    if not docs:
        print("no .pptx/.pdf inputs found", file=sys.stderr)
        return 1

    rows = []
    for doc in docs:
        stats = doc.stats()
        rows.append((doc.source, doc.kind, stats["pages"], stats["blocks"], stats["chars"], doc.title))
        if args.out:
            write_extract(doc, args.out)

    name_width = max(len(r[0]) for r in rows)
    print(f"{'source':<{name_width}}  kind  pages  blocks   chars  title")
    for source, kind, pages, blocks, chars, title in rows:
        print(f"{source:<{name_width}}  {kind:<4}  {pages:>5}  {blocks:>6}  {chars:>6}  {title}")

    total_pages = sum(r[2] for r in rows)
    total_blocks = sum(r[3] for r in rows)
    total_chars = sum(r[4] for r in rows)
    print(f"\n{len(rows)} documents, {total_pages} pages, {total_blocks} blocks, {total_chars} chars")
    if args.out:
        print(f"extract -> {args.out}")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    docs = extract_paths(args.paths, root=args.root or Path.cwd())
    if not docs:
        print("no .pptx/.pdf inputs found", file=sys.stderr)
        return 1

    try:
        provider = build_provider(args.llm, Path(args.cache))
    except PlannerError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    failures = 0
    for doc in docs:
        try:
            scene = provider.plan(doc)
        except PlannerError as exc:
            failures += 1
            print(f"FAIL {doc.source}: {exc}", file=sys.stderr)
            continue
        target = out / f"{Path(doc.source).name}.json"
        target.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n", "utf-8")
        stats = scene["meta"]
        rows.append(
            (
                doc.source,
                len(scene["objects"]),
                len(scene["interactions"]),
                len(scene["tasks"]),
                stats["triangle_estimate"],
                target.stat().st_size,
            )
        )

    width = max((len(row[0]) for row in rows), default=4)
    print(f"{'deck':<{width}}  objects  clicks  tasks  tris    bytes")
    for source, objects, interactions, tasks, triangles, size in rows:
        print(f"{source:<{width}}  {objects:>7}  {interactions:>6}  {tasks:>5}  {triangles:>5}  {size:>7}")
    print(f"\n{len(rows)} scenes -> {out}  (provider: {args.llm})")

    # Gallery index for the web viewer (deterministic order by file name).
    scenes = []
    for source, objects, _i, _t, _tris, _size in rows:
        scene_path = out / f"{Path(source).name}.json"
        if not scene_path.exists():
            continue
        payload = json.loads(scene_path.read_text("utf-8"))
        scenes.append(
            {
                "file": scene_path.name,
                "id": payload["deck"]["id"],
                "title": payload["deck"]["title"],
                "lang": payload["deck"]["lang"],
                "objects": objects,
            }
        )
    if scenes:
        (out / "index.json").write_text(
            json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2) + "\n", "utf-8"
        )
        print(f"index -> {out / 'index.json'}")
    return 1 if failures else 0


def _cmd_eval(args: argparse.Namespace) -> int:
    scenes = load_scenes(args.scenes)
    if not scenes:
        print(f"no scenes found in {args.scenes}; run `lessonlens build` first", file=sys.stderr)
        return 1

    metrics, checks = evaluate(scenes, root=args.root or Path.cwd())
    metrics.web = load_web_metrics(args.web_metrics)
    metrics.usdz = load_usdz_report(args.usdz)
    target = write_report(metrics, args.out)

    st_rate = metrics.self_test.get("total", {}).get("rate", 0.0)
    rows = [
        ("schema_pass_rate", metrics.schema_pass_rate, "100%"),
        ("grounding_coverage", metrics.grounding_coverage, ">=80%"),
        ("quote_hit_rate", metrics.quote_hit_rate, ">=85%"),
        ("unsupported_rate", metrics.unsupported_rate, "<=10%"),
        ("task_solvable_rate", metrics.task_solvable_rate, "100%"),
        ("verifier_self_test", st_rate, "100%"),
    ]
    print(f"{'metric':<22} {'value':>8}   target")
    for name, value, target_text in rows:
        print(f"{name:<22} {value:>7.1%}   {target_text}")
    print(f"\n{metrics.decks} scenes, {metrics.objects} objects, {metrics.claims} claims")
    failed = sum(1 for check in checks if check.schema_errors) + sum(
        1 for claim in (c for check in checks for c in check.claims) if not claim.ok
    )
    print(f"report -> {target}  (metrics -> {target.parent / 'metrics.json'})")
    if failed:
        print(f"FAIL: {failed} unsupported claim(s) or schema error(s); see report", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lessonlens", description="Slide deck -> grounded 3D scene.")
    parser.add_argument("--version", action="version", version=f"lessonlens {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="extract pages and blocks from .pptx/.pdf decks")
    ingest.add_argument("paths", nargs="+", help="files or directories of decks")
    ingest.add_argument("--out", default="eval/extract", help="directory for extract JSON")
    ingest.add_argument("--root", default=None, help="base directory used to shorten 'source' paths")
    ingest.set_defaults(func=_cmd_ingest)

    build = sub.add_parser("build", help="plan scene.json from decks (schema validated)")
    build.add_argument("paths", nargs="+", help="files or directories of decks")
    build.add_argument("--out", default="eval/scenes", help="directory for scene JSON")
    build.add_argument("--root", default=None, help="base directory used to shorten 'source' paths")
    build.add_argument(
        "--llm", default="mock", choices=["mock", "cache", "deepseek"], help="planner provider"
    )
    build.add_argument("--cache", default="cache", help="directory for cached LLM responses")
    build.set_defaults(func=_cmd_build)

    evaluate_cmd = sub.add_parser("eval", help="verify scenes and write eval/report.md")
    evaluate_cmd.add_argument("--scenes", default="eval/scenes", help="directory of scene JSON")
    evaluate_cmd.add_argument("--out", default="eval/report.md", help="report path")
    evaluate_cmd.add_argument("--root", default=None, help="repository root used to resolve decks")
    evaluate_cmd.add_argument(
        "--web-metrics", default="eval/web-metrics.json", help="browser gate output (optional)"
    )
    evaluate_cmd.add_argument(
        "--usdz", default="out/usdz-report.json", help="USDZ check output (optional)"
    )
    evaluate_cmd.add_argument(
        "--cache-only",
        action="store_true",
        help="use the committed scenes as-is (the only supported mode; kept for CI parity)",
    )
    evaluate_cmd.set_defaults(func=_cmd_eval)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
