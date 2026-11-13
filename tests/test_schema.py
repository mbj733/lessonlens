"""B2 gate: the mock planner emits schema-valid, grounded, deterministic scenes for all 14 decks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lessonlens.ingest import Document, extract_document, normalize
from lessonlens.planner import (
    TRIANGLES,
    CachePlanner,
    DeepSeekPlanner,
    MockPlanner,
    PlannerError,
    build_provider,
    scene_digest,
    validate_scene,
)

ROOT = Path(__file__).resolve().parents[1]
SLIDES = ROOT / "eval" / "slides"
SCENES = ROOT / "eval" / "scenes"


@pytest.fixture(scope="session")
def docs() -> dict[str, Document]:
    files = sorted(p for p in SLIDES.iterdir() if p.suffix.lower() in {".pptx", ".pdf"})
    return {p.name: extract_document(p, root=ROOT) for p in files}


@pytest.fixture(scope="session")
def scenes(docs: dict[str, Document]) -> dict[str, dict]:
    planner = MockPlanner()
    return {name: planner.plan(doc) for name, doc in docs.items()}


def test_every_scene_validates(scenes: dict[str, dict]) -> None:
    for name, scene in scenes.items():
        assert validate_scene(scene) == [], name


def test_object_and_interaction_budget(scenes: dict[str, dict]) -> None:
    for name, scene in scenes.items():
        objects = scene["objects"]
        assert 8 <= len(objects) <= 24, name
        assert len(scene["interactions"]) == len(objects), name
        assert 1 <= len(scene["tasks"]) <= 8, name
        ids = [obj["id"] for obj in objects]
        assert ids == sorted(ids), name
        assert len(set(ids)) == len(ids), name


def test_every_page_is_represented(scenes: dict[str, dict], docs: dict[str, Document]) -> None:
    for name, scene in scenes.items():
        pages = {obj["page"] for obj in scene["objects"]}
        assert pages == set(range(1, len(docs[name].pages) + 1)), name


def test_claims_are_verbatim_grounded(scenes: dict[str, dict], docs: dict[str, Document]) -> None:
    """The core promise: every claim quote really occurs on its source page."""
    for name, scene in scenes.items():
        doc = docs[name]
        for obj in scene["objects"]:
            page_text = normalize(doc.pages[obj["page"] - 1].text)
            for claim in obj["claims"]:
                assert normalize(claim["quote"]) in page_text, f"{name} {obj['id']}"
                assert claim["page"] == obj["page"], f"{name} {obj['id']} claim page"


def test_planning_is_deterministic(docs: dict[str, Document], scenes: dict[str, dict]) -> None:
    planner = MockPlanner()
    for name, doc in docs.items():
        assert scene_digest(planner.plan(doc)) == scene_digest(scenes[name]), name


def test_committed_scenes_are_current(docs: dict[str, Document], scenes: dict[str, dict]) -> None:
    for name, scene in scenes.items():
        committed = SCENES / f"{Path(docs[name].source).name}.json"
        assert committed.exists(), f"{committed.name} missing; run `lessonlens build`"
        assert scene_digest(json.loads(committed.read_text("utf-8"))) == scene_digest(scene), (
            f"{committed.name} is stale; re-run `python -m lessonlens build eval/slides`"
        )


def test_scene_size_under_200kb(scenes: dict[str, dict]) -> None:
    for name, scene in scenes.items():
        payload = json.dumps(scene, ensure_ascii=False, indent=2).encode("utf-8")
        assert len(payload) < 200_000, f"{name}: {len(payload)} bytes"


def test_triangle_budget(scenes: dict[str, dict]) -> None:
    for name, scene in scenes.items():
        expected = sum(TRIANGLES[obj["primitive"]] for obj in scene["objects"])
        assert scene["meta"]["triangle_estimate"] == expected, name
        assert expected <= 60_000, name


def test_invalid_scenes_are_rejected(scenes: dict[str, dict]) -> None:
    base = json.loads(json.dumps(scenes["en-02-bst.pptx"]))

    missing_claim = json.loads(json.dumps(base))
    missing_claim["objects"][0]["claims"] = []
    assert any("claims" in error for error in validate_scene(missing_claim))

    bad_answer = json.loads(json.dumps(base))
    bad_answer["tasks"][0]["answers"] = ["o99"]
    assert any("unknown objects" in error for error in validate_scene(bad_answer))

    bad_target = json.loads(json.dumps(base))
    bad_target["interactions"][0]["target"] = "o77"
    assert any("unknown target" in error for error in validate_scene(bad_target))

    duplicate = json.loads(json.dumps(base))
    duplicate["objects"][1]["id"] = duplicate["objects"][0]["id"]
    errors = validate_scene(duplicate)
    assert any("duplicate" in error for error in errors)

    bad_meta = json.loads(json.dumps(base))
    bad_meta["meta"]["triangle_estimate"] = 1
    assert any("triangle_estimate" in error for error in validate_scene(bad_meta))

    bad_primitive = json.loads(json.dumps(base))
    bad_primitive["objects"][0]["primitive"] = "torus"
    assert any("torus" in error for error in validate_scene(bad_primitive))


def test_cache_provider_writes_then_replays(tmp_path: Path, docs: dict[str, Document]) -> None:
    provider = CachePlanner(tmp_path)
    doc = docs["en-03-hashing.pptx"]
    first = provider.plan(doc)
    target = tmp_path / "en-03-hashing.json"
    assert target.exists()
    second = provider.plan(doc)
    assert second["meta"]["generator"] == "cache"
    # Replay is byte-identical apart from the provenance tag.
    first_as_cache = json.loads(json.dumps(first))
    first_as_cache["meta"]["generator"] = "cache"
    assert scene_digest(first_as_cache) == scene_digest(second)


def test_deepseek_requires_key(docs: dict[str, Document]) -> None:
    planner = DeepSeekPlanner(api_key="")
    with pytest.raises(PlannerError, match="DEEPSEEK_API_KEY"):
        planner.plan(docs["en-04-shortest-paths.pptx"])


def test_deepseek_parses_and_caches(tmp_path: Path, docs: dict[str, Document], scenes: dict) -> None:
    payload_scene = json.loads(json.dumps(scenes["en-04-shortest-paths.pptx"]))
    captured: dict = {}

    def fake_transport(url: str, headers: dict, payload: dict) -> dict:
        captured.update(url=url, headers=headers, payload=payload)
        return {"choices": [{"message": {"content": json.dumps(payload_scene)}}]}

    planner = DeepSeekPlanner(api_key="test-key", cache_dir=tmp_path, transport=fake_transport)
    scene = planner.plan(docs["en-04-shortest-paths.pptx"])

    assert scene["meta"]["generator"] == "deepseek"
    assert validate_scene(scene) == []
    assert captured["url"].startswith("https://api.deepseek.com/")
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["temperature"] == 0
    assert any("Slide text follows" in m["content"] for m in captured["payload"]["messages"])
    assert (tmp_path / "en-04-shortest-paths.json").exists()


def test_deepseek_rejects_non_json(docs: dict[str, Document], scenes: dict) -> None:
    def fake_transport(url: str, headers: dict, payload: dict) -> dict:
        return {"choices": [{"message": {"content": "not json"}}]}

    planner = DeepSeekPlanner(api_key="k", transport=fake_transport)
    with pytest.raises(PlannerError, match="did not return JSON"):
        planner.plan(docs["en-05-processes-threads.pptx"])


def test_deepseek_rejects_invalid_scene(docs: dict[str, Document], scenes: dict) -> None:
    broken = json.loads(json.dumps(scenes["en-05-processes-threads.pptx"]))
    broken["objects"] = broken["objects"][:2]

    def fake_transport(url: str, headers: dict, payload: dict) -> dict:
        return {"choices": [{"message": {"content": json.dumps(broken)}}]}

    planner = DeepSeekPlanner(api_key="k", transport=fake_transport)
    with pytest.raises(PlannerError):
        planner.plan(docs["en-05-processes-threads.pptx"])


def test_build_provider_names() -> None:
    assert build_provider("mock").name == "mock"
    assert build_provider("cache").name == "cache"
    assert build_provider("deepseek").name == "deepseek"
    with pytest.raises(PlannerError):
        build_provider("gpt")


def test_cli_build_smoke(tmp_path: Path) -> None:
    from lessonlens.cli import main

    code = main(
        [
            "build",
            str(SLIDES / "en-05-processes-threads.pptx"),
            "--out",
            str(tmp_path),
            "--root",
            str(ROOT),
            "--llm",
            "mock",
        ]
    )
    assert code == 0
    written = tmp_path / "en-05-processes-threads.pptx.json"
    assert written.exists()
    assert json.loads(written.read_text("utf-8"))["schema"] == "lessonlens/scene@1"
