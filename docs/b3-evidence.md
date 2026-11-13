# B3 — Web runtime evidence

Executed: 2026-11-13 (Asia/Shanghai) · Repo: `E:\alsl项目\lessonlens`
Browser: Microsoft Edge (installed), driven headless by Playwright 1.65.1 — no browser download.

## 1. What exists now

| file | role |
|---|---|
| `web/index.html` | shell: canvas, deck picker, language toggle, detail card, task panel, legend |
| `web/main.js` | Three.js scene, orbit camera, raycast picking, sidebar reveal, task grading, `window.__lessonlens` test surface |
| `web/style.css` | dark UI, two-column layout, responsive fallback under 900 px |
| `web/i18n.js` | EN/ZH UI strings (`applyLang` rewrites every `[data-i18n]` node) |
| `web/vendor/three.module.js` + `three.core.js` | Three.js r187, vendored (**deviation from the plan's CDN choice**, see §5) |
| `tools/web_check.py` | Playwright gate: loads the page, clicks a real object at its projected position, asserts the quote |

Object shapes encode slide role — `box` = the deck's opening definition, `sphere` = concept,
`cylinder` = table/example page, `cone` = summary — and the legend in the UI says exactly that.

## 2. Gate output

```
> .venv\Scripts\python.exe -X utf8 tools\web_check.py
[PASS] scene loaded — zh-09-tcp
[PASS] objects rendered — 12 objects
[PASS] no console errors
[PASS] object projects on screen — {"x": 619.9, "y": 374.8, "visible": true}
[PASS] click selects the object — o03 vs o03
[PASS] sidebar shows the source quote
[PASS] meta shows page and kind — page 3 · concept · sphere
[PASS] wrong answer is rejected
[PASS] correct answer is accepted
[PASS] i18n toggle switches to zh — en -> zh-CN / 练习
[PASS] i18n toggles back
[PASS] first paint under 3000 ms — LCP=None first_frame=313 ms
[PASS] screenshot written — docs/demo-3d.png

13/13 checks passed
```

The click check is a genuine end-to-end raycast: the script asks the page for the object's projected
screen position, clicks those coordinates with `page.mouse.click`, and then compares the sidebar text
with the scene's own `claims[0].quote`.

`docs/demo-3d.png` (1440×900) is the screenshot from this run — inspected, not just written: the
selected object is ringed, the detail card shows page 3, and the task panel shows all three tasks.

## 3. First-paint number, stated precisely

`performance.getEntriesByType('largest-contentful-paint')` returns **no entries** for this page: the
main surface is a WebGL canvas, so Chromium has no LCP candidate in headless mode. The gate therefore
reports two numbers — LCP when present, otherwise the time from navigation start to the first rendered
frame (`performance.mark('lessonlens:first-frame')`), here **313 ms**. The plan's 3.0 s budget is met
by the first-frame proxy; the report must say "LCP unavailable on this page, first frame 313 ms", not
"LCP 313 ms".

## 4. Defects found and fixed

1. **A 404 console error** (missing favicon) failed the "no console errors" check; fixed with an
   inline empty icon — the check is strict on purpose.
2. **"Nothing selected yet." stayed visible** above a selected object: the empty-state paragraph was
   not part of the `.card.empty` hide rule. Fixed with `.card:not(.empty) .muted { display: none }`.
3. **The legend was unreadable** — flat `<span>` pairs in a two-column grid pushed labels to the far
   right. Rewritten as `legend-item` flex rows (visible in the screenshot).
4. **Two "definition" boxes per deck**: the page-1 convention was applied by block index, so the
   second object taken from page 1 also became a definition. Role is now assigned per *page*
   (first object of the page), verified by the kind histogram:

```
zh-09-tcp.pptx.json kinds: {'definition': 1, 'concept': 9, 'table': 1, 'summary': 1}
en-01-sorting.pptx.json kinds: {'definition': 1, 'concept': 9, 'table': 1, 'summary': 1}
```

## 5. Deviation from the plan: Three.js is vendored, not loaded from a CDN

The plan says "Three.js via CDN, no build". I download r187 into `web/vendor/` (2.1 MB raw, ~0.5 MB
gzipped by Pages) instead. Reasons:

- the demo then works offline and on `file://`-style static hosting with no third-party request;
- CI and screenshots are not affected by a CDN outage or version drift;
- the version is pinned by content, not by a floating URL.

Cost: 2.1 MB in the repository. If that is unacceptable, deleting the two files and pointing the
import at `https://unpkg.com/three@0.187.0/build/three.module.js` is a two-line change.

## 6. Limits of this batch

- **Interaction is mouse-first**: drag to orbit, wheel to zoom, click to pick. Pinch/touch zoom is not
  implemented; the responsive layout under 900 px has not been checked on a real phone.
- No shadows, post-processing or instancing; a 12-object scene does not need them.
- The viewer fetches `../eval/scenes/*` relative to `web/`, so GitHub Pages must serve the repository
  root (B6 adds a root redirect) — opening `web/index.html` from the filesystem will not load scenes.
- The Playwright gate is a script, not part of `pytest` (it needs an installed Edge). CI still runs
  the Python suite only; wiring the browser gate into CI is B6 work.

## 7. Reproduce

```powershell
.venv\Scripts\python.exe -m lessonlens build eval/slides --out eval/scenes --root . --llm mock
.venv\Scripts\python.exe -X utf8 tools\web_check.py          # 13 checks + docs/demo-3d.png
.venv\Scripts\python.exe -m http.server 8123                 # then open /web/ manually
```
