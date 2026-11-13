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
    return 1 if failures else 0


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
