"""B3 gate: drive the real viewer in a real browser and assert the interaction contract.

Serves the repository over loopback, opens ``web/`` in Microsoft Edge (installed, no browser
download), clicks an object at its projected screen position and checks that the sidebar shows the
slide quote the scene claims.

    python tools/web_check.py            # headless
    python tools/web_check.py --headed   # watch it
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCENES = ROOT / "eval" / "scenes"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep the output readable
        pass


def serve(root: Path) -> tuple[socketserver.TCPServer, int]:
    handler = functools.partial(QuietHandler, directory=str(root))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


class Results:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append((name, bool(ok), detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    @property
    def failed(self) -> int:
        return sum(1 for _n, ok, _d in self.rows if not ok)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--scene", default="zh-09-tcp.pptx.json")
    parser.add_argument("--screenshot", default="docs/demo-3d.png")
    args = parser.parse_args()

    expected = json.loads((SCENES / args.scene).read_text("utf-8"))
    httpd, port = serve(ROOT)
    base = f"http://127.0.0.1:{port}"
    results = Results()

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel="msedge",
                headless=not args.headed,
                args=["--enable-unsafe-swiftshader", "--use-angle=swiftshader"],
            )
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            console_errors: list[str] = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: console_errors.append(str(err)))

            page.goto(f"{base}/web/?scene={args.scene}", wait_until="load")
            page.wait_for_function("() => window.__lessonlens && window.__lessonlens.ready === true", timeout=20000)

            scene = page.evaluate("() => window.__lessonlens.scene")
            results.check("scene loaded", scene["deck"]["id"] == expected["deck"]["id"], scene["deck"]["id"])
            results.check(
                "objects rendered",
                len(scene["objects"]) == len(expected["objects"]) == 12,
                f"{len(scene['objects'])} objects",
            )
            results.check("no console errors", not console_errors, "; ".join(console_errors[:2]))

            target = scene["objects"][2]
            position = page.evaluate("(id) => window.__lessonlens.screenPosition(id)", target["id"])
            results.check("object projects on screen", bool(position and position["visible"]), json.dumps(position))

            page.mouse.click(position["x"], position["y"])
            page.wait_for_timeout(150)
            selected = page.evaluate("() => window.__lessonlens.selected")
            results.check("click selects the object", selected == target["id"], f"{selected} vs {target['id']}")

            quote = page.inner_text("#detail-quote")
            results.check("sidebar shows the source quote", quote.strip() == target["claims"][0]["quote"].strip())

            meta = page.inner_text("#detail-meta")
            results.check("meta shows page and kind", f"page {target['page']}" in meta.lower(), meta)

            # Task flow: wrong answer, then the right one.
            task = next(t for t in scene["tasks"] if t["kind"] == "identify")
            wrong_id = next(obj["id"] for obj in scene["objects"] if obj["id"] not in task["answers"])
            page.evaluate("([task, id]) => window.__lessonlens.answerTask(task, id)", [task["id"], wrong_id])
            page.wait_for_timeout(80)
            feedback = page.inner_text(f'.task[data-task-id="{task["id"]}"] [data-role="feedback"]')
            results.check("wrong answer is rejected", "try again" in feedback.lower() or "再想想" in feedback, feedback[:60])

            page.evaluate("([task, id]) => window.__lessonlens.answerTask(task, id)", [task["id"], task["answers"][0]])
            page.wait_for_timeout(80)
            feedback = page.inner_text(f'.task[data-task-id="{task["id"]}"] [data-role="feedback"]')
            results.check("correct answer is accepted", "correct" in feedback.lower() or "正确" in feedback, feedback[:60])

            # i18n toggle round-trip.
            lang_before = page.evaluate("() => document.documentElement.lang")
            page.click("#lang-toggle")
            page.wait_for_timeout(80)
            lang_after = page.evaluate("() => document.documentElement.lang")
            label = page.inner_text('[data-i18n="tasks"]')
            results.check("i18n toggle switches to zh", lang_after == "zh-CN" and label == "练习", f"{lang_before} -> {lang_after} / {label}")

            page.click("#lang-toggle")
            page.wait_for_timeout(80)
            results.check("i18n toggles back", page.evaluate("() => document.documentElement.lang") == "en")

            lcp = page.evaluate(
                "() => { const e = performance.getEntriesByType('largest-contentful-paint');"
                " return e.length ? e[e.length - 1].startTime : null; }"
            )
            first_frame = page.evaluate("() => window.__lessonlens.firstFrameMs")
            # A canvas-only page emits no LCP entry in headless Chromium, so the honest proxy is
            # the time from navigation start to the first rendered frame.
            budget_ms = lcp if lcp is not None else first_frame
            results.check(
                "first paint under 3000 ms",
                0 <= budget_ms < 3000,
                f"LCP={lcp} first_frame={first_frame:.0f} ms" if first_frame is not None else "no timing",
            )

            shot = ROOT / args.screenshot
            shot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(shot))
            results.check("screenshot written", shot.exists(), str(shot.relative_to(ROOT)))

            browser.close()
    finally:
        httpd.shutdown()

    print(f"\n{len(results.rows) - results.failed}/{len(results.rows)} checks passed")
    return 1 if results.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
