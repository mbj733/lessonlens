"""Planner: extract.json -> scene.json, constrained by ``schema/scene.schema.json``.

Three providers, one contract (``plan(doc) -> dict``):

``mock``      deterministic rules; needs no network and no key, so every number in the report is
              reproducible by anyone who clones the repo
``deepseek``  HTTP call to the DeepSeek chat API, response parsed and validated; costs a key
``cache``     build once with ``deepseek``, commit the result under ``cache/``, replay it in CI

Whatever the provider, the output is validated before it leaves this module: JSON Schema first,
then the rules a schema cannot express (cross references, page range, triangle budget).
"""

from __future__ import annotations

import hashlib
import json
import math
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from jsonschema import Draft202012Validator

from .ingest import Document, Page, normalize

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schema" / "scene.schema.json"
SCENE_SCHEMA_VERSION = "lessonlens/scene@1"

#: Approximate triangle count per procedural primitive; the budget is 60k for the whole scene.
TRIANGLES = {"box": 12, "sphere": 960, "cylinder": 96, "cone": 96, "plane": 2}
TRIANGLE_BUDGET = 60_000

PALETTE = [
    "#4e79a7",
    "#f28e2b",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc948",
    "#b07aa1",
    "#ff9da7",
]

PRIMITIVE_BY_KIND = {
    "definition": "box",
    "concept": "sphere",
    "example": "cylinder",
    "summary": "cone",
}

TARGET_OBJECTS = 12
MIN_OBJECTS = 8
MAX_OBJECTS = 24
MIN_QUOTE = 16  # characters: a full Chinese sentence, a short English one


class PlannerError(RuntimeError):
    """Raised when a provider cannot produce a schema-valid scene."""


class Provider(Protocol):
    name: str

    def plan(self, doc: Document) -> dict[str, Any]: ...


# --------------------------------------------------------------------------- validation


def load_schema(path: str | Path | None = None) -> dict[str, Any]:
    return json.loads(Path(path or SCHEMA_PATH).read_text("utf-8"))


def validate_scene(scene: dict[str, Any], schema: dict[str, Any] | None = None) -> list[str]:
    """Return every problem found, schema-level and cross-reference-level."""
    schema = schema or load_schema()
    errors: list[str] = []

    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(scene), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{where}: {error.message}")

    if errors:
        return errors

    objects = scene["objects"]
    ids = [obj["id"] for obj in objects]
    if len(ids) != len(set(ids)):
        errors.append("objects: duplicate object ids")
    known = set(ids)
    pages = scene["deck"]["pages"]

    for obj in objects:
        if obj["page"] > pages:
            errors.append(f"objects/{obj['id']}: page {obj['page']} exceeds deck pages {pages}")
        for claim in obj["claims"]:
            if claim["page"] > pages:
                errors.append(f"objects/{obj['id']}/claims: page {claim['page']} out of range")
            if not claim["quote"].strip():
                errors.append(f"objects/{obj['id']}/claims: empty quote")

    for interaction in scene["interactions"]:
        if interaction["target"] not in known:
            errors.append(f"interactions/{interaction['id']}: unknown target {interaction['target']}")

    for task in scene["tasks"]:
        missing = [answer for answer in task["answers"] if answer not in known]
        if missing:
            errors.append(f"tasks/{task['id']}: answers point at unknown objects {missing}")

    triangles = sum(TRIANGLES[obj["primitive"]] for obj in objects)
    if triangles > TRIANGLE_BUDGET:
        errors.append(f"objects: triangle estimate {triangles} exceeds budget {TRIANGLE_BUDGET}")
    if scene["meta"]["triangle_estimate"] != triangles:
        errors.append(
            f"meta: triangle_estimate {scene['meta']['triangle_estimate']} != recomputed {triangles}"
        )

    return errors


def assert_scene(scene: dict[str, Any]) -> dict[str, Any]:
    errors = validate_scene(scene)
    if errors:
        raise PlannerError("invalid scene:\n  " + "\n  ".join(errors))
    return scene


def scene_digest(scene: dict[str, Any]) -> str:
    """Stable hash for determinism tests (key order does not matter)."""
    payload = json.dumps(scene, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# --------------------------------------------------------------------------- mock rules


def _kind_of(text: str, page_index: int, page_count: int) -> str:
    lowered = text.casefold()
    if page_index == page_count:
        return "summary"
    if any(marker in lowered for marker in ("definition", "定义", "称为", "是指", "记作")):
        return "definition"
    if any(marker in lowered for marker in ("example", "for instance", "例子", "例如", "例：")):
        return "example"
    return "concept"


def _label_of(text: str, limit: int = 48) -> str:
    """A short, honest label: the opening clause of the slide text, never an invented summary."""
    text = normalize(text)
    for separator in ("：", ":", "；", ";", "，", ",", " — ", " – "):
        cut = text.find(separator)
        if 6 <= cut <= limit:
            return text[:cut].rstrip("。.")
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut:
        cut = cut[: cut.rindex(" ")]
    return cut.rstrip("，,、;；:：") + "…"


def _pick_blocks(doc: Document, target: int = TARGET_OBJECTS) -> list[tuple[Page, int, Any]]:
    """First block of every page, then the second block of every page, until the target is met."""
    per_page: list[tuple[Page, list[tuple[int, Any]]]] = []
    for page in doc.pages:
        blocks = [
            (index, block)
            for index, block in enumerate(page.blocks)
            if block.type in {"bullet", "body", "table"}
            and len(normalize(block.text)) >= MIN_QUOTE
        ]
        per_page.append((page, blocks))

    picked: list[tuple[Page, int, Any]] = []
    depth = 0
    while len(picked) < target and depth < 8:
        added = False
        for page, blocks in per_page:
            if len(picked) >= target:
                break
            if len(blocks) > depth:
                block_index, block = blocks[depth]
                picked.append((page, block_index, block))
                added = True
        if not added:
            break
        depth += 1
    return picked[: max(MIN_OBJECTS, min(target, MAX_OBJECTS))]


def _position(index: int, count: int) -> list[float]:
    columns = 4 if count > 8 else 3
    rows = math.ceil(count / columns)
    column = index % columns
    row = index // columns
    x = (column - (columns - 1) / 2) * 2.7
    z = (row - (rows - 1) / 2) * 2.7
    return [round(x, 3), 0.0, round(z, 3)]


def _claim(block_text: str, page_index: int) -> dict[str, Any]:
    quote = normalize(block_text)[:300]
    # The mock provider does not paraphrase: the claim text is a prefix of the quote by construction.
    # It is honest about that in `meta.notes`, and B4's verifier tests use hand-made negatives.
    text = quote if len(quote) <= 140 else quote[:140].rsplit(" ", 1)[0] + "…"
    return {"text": text, "quote": quote, "page": page_index}


class MockPlanner:
    """Deterministic, dependency-free scene builder used by default and in CI."""

    name = "mock"

    def plan(self, doc: Document) -> dict[str, Any]:
        picked = _pick_blocks(doc)
        if len(picked) < MIN_OBJECTS:
            raise PlannerError(
                f"{doc.source}: only {len(picked)} usable blocks, need at least {MIN_OBJECTS}"
            )

        objects: list[dict[str, Any]] = []
        for index, (page, _block_index, block) in enumerate(picked):
            kind = _kind_of(block.text, page.index, len(doc.pages))
            primitive = PRIMITIVE_BY_KIND[kind]
            scale = 1.0 + 0.12 * (index % 3)
            height = 0.9 if primitive in {"sphere", "cone"} else 0.7
            x, _, z = _position(index, len(picked))
            label = " | ".join(block.rows[0]) if block.rows else block.text
            objects.append(
                {
                    "id": f"o{index + 1:02d}",
                    "label": _label_of(label)[:80],
                    "primitive": primitive,
                    "position": [x, 0.0, z],
                    "scale": [round(scale, 3), round(height * scale, 3), round(scale, 3)],
                    "color": PALETTE[index % len(PALETTE)],
                    "page": page.index,
                    "kind": kind,
                    "claims": [_claim(block.text, page.index)],
                }
            )
        # Sit every object on the floor: y = half its height.
        for obj in objects:
            obj["position"][1] = round(obj["scale"][1] / 2, 3)

        interactions = [
            {
                "id": f"i{index + 1:02d}",
                "type": "click",
                "target": obj["id"],
                "reveal": {
                    "title": obj["label"],
                    "body": f'Page {obj["page"]} — “{obj["claims"][0]["quote"]}”',
                },
            }
            for index, obj in enumerate(objects)
        ]

        tasks = self._tasks(doc, objects)
        triangles = sum(TRIANGLES[obj["primitive"]] for obj in objects)
        scene = {
            "schema": SCENE_SCHEMA_VERSION,
            "deck": {
                "id": Path(doc.source).stem,
                "title": doc.title,
                "lang": doc.lang,
                "pages": len(doc.pages),
                "source": doc.source,
            },
            "objects": objects,
            "interactions": interactions,
            "tasks": tasks,
            "meta": {
                "generator": "mock",
                "object_count": len(objects),
                "triangle_estimate": triangles,
                "notes": "Mock planner: one object per slide plus detail objects. Claim text is a "
                "prefix of the slide quote, not a paraphrase.",
            },
        }
        return assert_scene(scene)

    @staticmethod
    def _tasks(doc: Document, objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_page: dict[int, list[str]] = {}
        for obj in objects:
            by_page.setdefault(obj["page"], []).append(obj["id"])

        tasks: list[dict[str, Any]] = []
        ordered_pages = sorted(by_page)
        probe_page = 3 if 3 in by_page else ordered_pages[min(1, len(ordered_pages) - 1)]
        tasks.append(
            {
                "id": "t01",
                "kind": "identify",
                "prompt": f"Which object presents the idea from page {probe_page}?",
                "answers": by_page[probe_page][:1],
                "explanation": f"The object was grounded on page {probe_page} of the source deck.",
            }
        )

        last_page = sorted(by_page)[-1]
        tasks.append(
            {
                "id": "t02",
                "kind": "identify",
                "prompt": f"Which object summarises the deck, from page {last_page}?",
                "answers": by_page[last_page][:1],
                "explanation": "The last slide is the summary, so its object answers the task.",
            }
        )

        ordered: list[dict[str, Any]] = []
        seen_pages: set[int] = set()
        for obj in sorted(objects, key=lambda item: (item["page"], item["id"])):
            if obj["page"] in seen_pages:
                continue
            seen_pages.add(obj["page"])
            ordered.append(obj)
            if len(ordered) == 3:
                break
        tasks.append(
            {
                "id": "t03",
                "kind": "order",
                "prompt": "Order these three objects as their pages appear in the deck.",
                "answers": [obj["id"] for obj in ordered],
                "explanation": "Each listed object comes from a different page, in deck order.",
            }
        )
        return tasks


# --------------------------------------------------------------------------- cache provider


class CachePlanner:
    """Replays a committed ``cache/<deck>.json``; falls back to the inner provider on a miss."""

    name = "cache"

    def __init__(self, cache_dir: str | Path, inner: Provider | None = None) -> None:
        self.cache_dir = Path(cache_dir)
        self.inner = inner or MockPlanner()

    def path_for(self, doc: Document) -> Path:
        return self.cache_dir / f"{Path(doc.source).stem}.json"

    def plan(self, doc: Document) -> dict[str, Any]:
        target = self.path_for(doc)
        if target.exists():
            scene = json.loads(target.read_text("utf-8"))
            assert_scene(scene)
            scene.setdefault("meta", {})["generator"] = "cache"
            return scene
        scene = self.inner.plan(doc)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n", "utf-8")
        return scene


# --------------------------------------------------------------------------- deepseek provider

Transport = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]

SYSTEM_PROMPT = """You convert lecture slides into a JSON scene description for a 3D viewer.
Rules:
- Reply with JSON only, matching the provided schema exactly.
- Every object must carry at least one claim whose `quote` is copied verbatim from the slide text
  of the page named in `page`. Never invent facts, numbers or quotes.
- Use only these primitives: box, sphere, cylinder, cone, plane.
- Keep 8 to 24 objects.
- Tasks must reference existing object ids in `answers`.
"""


def _extract_for_prompt(doc: Document, max_chars: int = 6000) -> str:
    lines: list[str] = []
    for page in doc.pages:
        lines.append(f"--- page {page.index}: {page.title}")
        for block in page.blocks:
            if block.type in {"bullet", "body", "title"} and block.text:
                lines.append(block.text)
        if sum(len(line) for line in lines) > max_chars:
            break
    return "\n".join(lines)[:max_chars]


def build_prompt(doc: Document) -> str:
    pages = len(doc.pages)
    return (
        f"Deck: {doc.title} (language: {doc.lang}, {pages} pages).\n"
        f'Use deck.id="{Path(doc.source).stem}", schema="{SCENE_SCHEMA_VERSION}".\n'
        "Slide text follows; quote it verbatim in claims.\n\n" + _extract_for_prompt(doc)
    )


def _urllib_transport(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - fixed https URL
        return json.loads(response.read().decode("utf-8"))


class DeepSeekPlanner:
    """Calls the DeepSeek chat completions API; response is validated and cached on success."""

    name = "deepseek"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com/chat/completions",
        cache_dir: str | Path | None = None,
        transport: Transport | None = None,
        timeout: int = 120,
    ) -> None:
        import os

        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.model = model
        self.base_url = base_url
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.transport = transport or _urllib_transport
        self.timeout = timeout

    def plan(self, doc: Document) -> dict[str, Any]:
        if not self.api_key:
            raise PlannerError("DEEPSEEK_API_KEY is not set; use --llm mock or --llm cache")
        schema = load_schema()
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_prompt(doc)
                    + "\n\nJSON Schema:\n"
                    + json.dumps(schema, ensure_ascii=False),
                },
            ],
        }
        response = self.transport(
            self.base_url,
            {"Authorization": f"Bearer {self.api_key}"},
            payload,
        )
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise PlannerError(f"unexpected API response shape: {response!r}") from exc
        try:
            scene = json.loads(content)
        except json.JSONDecodeError as exc:
            raise PlannerError(f"model did not return JSON: {content[:200]!r}") from exc

        scene.setdefault("meta", {})["generator"] = "deepseek"
        assert_scene(scene)
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            target = self.cache_dir / f"{Path(doc.source).stem}.json"
            target.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n", "utf-8")
        return scene


def build_provider(name: str, cache_dir: str | Path | None = None) -> Provider:
    name = name.lower()
    if name == "mock":
        return MockPlanner()
    if name == "cache":
        return CachePlanner(cache_dir or ROOT / "cache")
    if name == "deepseek":
        return DeepSeekPlanner(cache_dir=cache_dir or ROOT / "cache")
    raise PlannerError(f"unknown provider {name!r} (expected mock, cache or deepseek)")
