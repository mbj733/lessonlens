"""B4 gate: metrics are computed from artifacts, the report is reproducible, and a broken scene moves the numbers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lessonlens.eval import evaluate, load_scenes, load_web_metrics, write_report

ROOT = Path(__file__).resolve().parents[1]
SCENES = ROOT / "eval" / "scenes"


@pytest.fixture(scope="session")
def scenes() -> list[dict]:
    return load_scenes(SCENES)


@pytest.fixture(scope="session")
def result(scenes: list[dict]):
    return evaluate(scenes, root=ROOT)


def test_metrics_cover_every_scene(result) -> None:
    metrics, checks = result
    assert metrics.decks == 14
    assert len(checks) == 14
    assert metrics.objects == 168
    assert metrics.claims == 168
    assert metrics.tasks == 42


def test_mock_scenes_meet_the_plan_targets(result) -> None:
    metrics, _ = result
    assert metrics.schema_pass_rate == 1.0
    assert metrics.grounding_coverage >= 0.80
    assert metrics.quote_hit_rate >= 0.85
    assert metrics.unsupported_rate <= 0.10
    assert metrics.task_solvable_rate == 1.0


def test_every_claim_is_supported(result) -> None:
    metrics, checks = result
    assert metrics.unsupported_rate == 0.0
    assert metrics.verdicts == {"SUPPORTED": 168}
    assert all(claim.ok for check in checks for claim in check.claims)


def test_projection_limits_hold(result) -> None:
    metrics, _ = result
    assert metrics.max_scene_bytes < 200_000
    assert metrics.max_triangles <= 60_000


def test_self_test_catches_all_corruptions(result) -> None:
    metrics, _ = result
    assert metrics.self_test["total"]["trials"] > 0
    assert metrics.self_test["total"]["rate"] == 1.0


def test_broken_scene_moves_the_numbers(scenes: list[dict]) -> None:
    """Negative control: tampering with a quote must show up in unsupported_rate."""
    tampered = json.loads(json.dumps(scenes))
    tampered[0]["objects"][0]["claims"][0]["quote"] = "a sentence that appears nowhere in the deck"
    metrics, _ = evaluate(tampered, root=ROOT)
    assert metrics.unsupported_rate > 0
    assert metrics.verdicts.get("UNSUPPORTED", 0) >= 1


def test_report_is_byte_reproducible(result, tmp_path: Path) -> None:
    metrics, _ = result
    first = write_report(metrics, tmp_path / "a" / "report.md")
    second = write_report(metrics, tmp_path / "b" / "report.md")
    assert first.read_text("utf-8") == second.read_text("utf-8")
    assert (tmp_path / "a" / "metrics.json").exists()


def test_report_contains_the_required_sections(result, tmp_path: Path) -> None:
    metrics, _ = result
    text = write_report(metrics, tmp_path / "report.md").read_text("utf-8")
    for needle in (
        "# LessonLens evaluation report",
        "## Headline",
        "schema_pass_rate",
        "grounding_coverage",
        "quote_hit_rate",
        "unsupported_rate",
        "task_solvable_rate",
        "## Verifier self-test",
        "## Honest notes",
        "Do not edit by hand",
    ):
        assert needle in text, needle
    assert "mock planner" in text


def test_committed_report_is_current(result) -> None:
    metrics, _ = result
    committed = (ROOT / "eval" / "report.md").read_text("utf-8")
    assert "sandbox" not in committed
    # The committed report must contain the same headline rows as a fresh computation.
    assert f"{metrics.grounding_coverage:.1%}" in committed
    assert f"{metrics.quote_hit_rate:.1%}" in committed
    assert f"{metrics.schema_pass_rate:.1%}" in committed


def test_web_metrics_are_recorded() -> None:
    web = load_web_metrics(ROOT / "eval" / "web-metrics.json")
    assert web, "run tools/web_check.py to record the browser gate"
    assert web["checks_passed"] == web["checks_total"] == 13
    assert web["first_frame_ms"] < 3000


def test_empty_input_is_handled(tmp_path: Path) -> None:
    metrics, checks = evaluate([], root=ROOT)
    assert metrics.decks == 0
    assert checks == []
    assert metrics.schema_pass_rate == 0.0
    text = write_report(metrics, tmp_path / "empty.md").read_text("utf-8")
    assert "0 scenes" in text
