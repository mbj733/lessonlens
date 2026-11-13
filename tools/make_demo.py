"""B6 gate: record a demo GIF and MP4 by driving the real viewer, then prove the files are valid.

No screen recorder: Playwright takes a frame every ``FRAME_MS`` while a scripted interaction runs
(rotate → pick two objects → answer a task → switch language), Pillow assembles the GIF and PyAV
(FFmpeg's libav* bound into Python, the same library behind ffprobe) assembles the MP4.

    python tools/make_demo.py

Gates: GIF ≥ 30 frames and < 8 MB; MP4 duration > 8 s.
"""

from __future__ import annotations

import functools
import http.server
import json
import shutil
import socketserver
import tempfile
import threading
import time
from fractions import Fraction
from pathlib import Path

import av
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
FRAME_MS = 160
FRAMES = 64
VIEWPORT = {"width": 960, "height": 600}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(root: Path) -> tuple[socketserver.TCPServer, int]:
    handler = functools.partial(QuietHandler, directory=str(root))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def record(frames_dir: Path) -> list[Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    httpd, port = serve(ROOT)
    frames: list[Path] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel="msedge",
                headless=True,
                args=["--enable-unsafe-swiftshader", "--use-angle=swiftshader"],
            )
            page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
            page.goto(f"http://127.0.0.1:{port}/web/?scene=zh-09-tcp.pptx.json", wait_until="load")
            page.wait_for_function("() => window.__lessonlens && window.__lessonlens.ready === true", timeout=20000)
            page.wait_for_timeout(400)

            scene = page.evaluate("() => window.__lessonlens.scene")
            first = scene["objects"][2]["id"]
            second = scene["objects"][6]["id"]
            position = page.evaluate("(id) => window.__lessonlens.screenPosition(id)", first)

            for index in range(FRAMES):
                if index == 8:
                    page.mouse.move(480, 300)
                    page.mouse.down()
                    for step in range(1, 9):
                        page.mouse.move(480 + step * 9, 300 - step * 2)
                        page.wait_for_timeout(30)
                    page.mouse.up()
                elif index == 20:
                    page.mouse.click(position["x"], position["y"])
                elif index == 34:
                    target = page.evaluate("(id) => window.__lessonlens.screenPosition(id)", second)
                    if target and target["visible"]:
                        page.mouse.click(target["x"], target["y"])
                elif index == 44:
                    task = scene["tasks"][0]
                    page.evaluate(
                        "([task, id]) => window.__lessonlens.answerTask(task, id)",
                        [task["id"], task["answers"][0]],
                    )
                elif index == 54:
                    page.click("#lang-toggle")

                page.wait_for_timeout(FRAME_MS)
                shot = frames_dir / f"frame_{index:04d}.png"
                page.screenshot(path=str(shot))
                frames.append(shot)

            browser.close()
    finally:
        httpd.shutdown()
    return frames


def build_gif(frames: list[Path], target: Path) -> dict:
    images = [Image.open(frame).convert("P", palette=Image.ADAPTIVE, colors=128) for frame in frames]
    images[0].save(
        target,
        save_all=True,
        append_images=images[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=True,
        disposal=2,
    )
    return {"path": str(target.relative_to(ROOT)), "captured": len(frames), "bytes": target.stat().st_size}


def inspect_gif(path: Path) -> dict:
    """PIL merges identical consecutive frames, so count what the file actually stores."""
    gif = Image.open(path)
    total_ms = 0
    for index in range(gif.n_frames):
        gif.seek(index)
        total_ms += int(gif.info.get("duration", 0))
    return {"frames": gif.n_frames, "duration_s": round(total_ms / 1000, 2)}


def build_mp4(frames: list[Path], target: Path) -> dict:
    """Encode with PyAV so no external ffmpeg binary is needed (and none can be blocked)."""
    first = Image.open(frames[0])
    width, height = first.size
    container = av.open(str(target), mode="w")
    stream = container.add_stream("libx264", rate=Fraction(1000, FRAME_MS))
    stream.width, stream.height = width, height
    stream.pix_fmt = "yuv420p"
    for frame_path in frames:
        image = Image.open(frame_path).convert("RGB")
        frame = av.VideoFrame.from_image(image)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    return {"path": str(target.relative_to(ROOT)), "bytes": target.stat().st_size}


def probe_mp4(path: Path) -> dict:
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        duration = float(container.duration / av.time_base) if container.duration else 0.0
        return {
            "duration_s": round(duration, 2),
            "frames": int(stream.frames),
            "codec": stream.codec_context.name,
            "size": f"{stream.codec_context.width}x{stream.codec_context.height}",
        }


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="ll-demo-"))
    started = time.time()
    frames = record(work)
    print(f"captured {len(frames)} frames in {time.time() - started:.1f}s -> {work}")

    gif = build_gif(frames, DOCS / "demo.gif")
    gif.update(inspect_gif(DOCS / "demo.gif"))
    print(
        f"gif  {gif['path']}  {gif['captured']} captured / {gif['frames']} encoded frames  "
        f"{gif['duration_s']:.1f}s  {gif['bytes'] / 1e6:.2f} MB"
    )

    results: dict = {"gif": gif, "mp4": None, "checks": {}}
    ok = gif["frames"] >= 30 and gif["duration_s"] >= 8 and gif["bytes"] < 8_000_000

    mp4 = build_mp4(frames, DOCS / "demo.mp4")
    probe = probe_mp4(DOCS / "demo.mp4")
    mp4.update(probe)
    results["mp4"] = mp4
    print(f"mp4  {mp4['path']}  {mp4['bytes'] / 1e6:.2f} MB  {probe['duration_s']:.1f}s  {probe['codec']} {probe['size']}")
    ok = ok and probe["duration_s"] > 8

    report = {
        "frames": len(frames),
        "frame_ms": FRAME_MS,
        "gif": gif,
        "mp4": results["mp4"],
        "ok": ok,
    }
    (ROOT / "eval" / "media-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    shutil.rmtree(work, ignore_errors=True)
    print(f"\n{'PASS' if ok else 'FAIL'}: gif encoded frames>=30, duration>=8s, <8MB; mp4 duration>8s")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
