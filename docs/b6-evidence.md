# B6 — Publishing evidence (local artifacts done, push blocked)

Executed: 2026-11-13 (Asia/Shanghai) · Repo: `E:\alsl项目\lessonlens`

## 1. Landing page

`index.html` at the repository root forwards to `web/` (`meta refresh` plus a visible link), because
GitHub Pages serves the repository root while the viewer lives in `web/`.

Served locally with `python -m http.server 8907` from the repository root:

| request | status | content-type | bytes |
|---|---|---|---|
| `GET /` | 200 | `text/html` | 1,686 |
| `GET /web/` | 200 | `text/html` | 2,270 |
| `GET /web/main.js` | 200 | `text/javascript` | 15,021 |
| `GET /eval/scenes/index.json` | 200 | `application/json` | 2,468 |
| `GET /out/zh-09-tcp.pptx.usdz` | 200 | `application/octet-stream` | 12,357 |
| `GET /docs/demo.gif` | 200 | `image/gif` | 1,870,541 |
| `GET /docs/demo.mp4` | 200 | `video/mp4` | 156,929 |

`GET /` contains `http-equiv="refresh" content="0; url=web/"` → true.

Two measurement traps worth recording:

- `python -m http.server` answers `HEAD` with **501 Unsupported method**, so the plan's `curl -I`
  shape cannot be used against it; GET was used instead. GitHub Pages does implement HEAD, so the
  criterion is checkable there once deployed.
- The first attempt used port 8899 and every path returned `200 application/json` with exactly 44
  bytes — an unrelated service already owned that port. "200" alone proved nothing; the second run on
  a free port returns real HTML and real file sizes. Any future smoke test should assert the body,
  not just the status.

## 2. Demo media

```
> .venv\Scripts\python.exe -X utf8 tools\make_demo.py
captured 64 frames in 16.9s
gif  docs\demo.gif  64 captured / 32 encoded frames  10.2s  1.87 MB
mp4  docs\demo.mp4  0.15 MB  10.2s  h264 960x600

PASS: gif encoded frames>=30, duration>=8s, <8MB; mp4 duration>8s
```

| file | frames | duration | size | how |
|---|---|---|---|---|
| `docs/demo.gif` | 32 encoded (64 captured) | 10.24 s | 1.87 MB | Playwright frames every 160 ms → Pillow |
| `docs/demo.mp4` | 64 | 10.24 s | 0.15 MB | same frames → PyAV (libx264, 960×600) |

The script performs the real interaction: drag to orbit → click object A (page 3) → click object B
(page 7) → answer a task → switch the UI to Chinese. A mid-recording frame was opened and inspected:
the sidebar shows “慢启动阶段拥塞窗口按指数增长，每个 RTT 翻倍。” with `page 7 · concept · sphere`.

**Two honest notes.**

1. PIL merges identical consecutive frames, so the GIF stores 32 frames with stretched per-frame
   delays (160/1280/4160 ms) rather than 64; total duration is unchanged. The gate now reports the
   encoded count, not the capture count.
2. `ffmpeg.exe` on this machine **cannot open any output file** — every path returns
   `Permission denied` (exit -13), including `%TEMP%`, while PowerShell writes to the same directory
   fine and `ffmpeg -f null -` works. Rather than debug a host-level restriction, the MP4 is encoded
   through **PyAV**, which binds the same libav* libraries into Python and writes from this process.
   The duration probe therefore uses `libavformat` through PyAV instead of the `ffprobe` binary — same
   library, different front end.

## 3. Repository state

```
> git log --oneline
fb8c521 B6: landing page, demo GIF/MP4, publishing evidence
4dbe395 B5: USDZ export + ARKit compliance gate
946f7eb B4: three verification gates + generated evaluation report
2691f69 B3: Three.js viewer with pick-to-quote, tasks and EN/ZH UI
2925b95 B2: scene schema + mock planner, 32 tests green
f6fffec B1: self-generated 10-deck corpus + pptx/pdf ingest
37d1aa7 B0: python 3.12 venv, deps, CI skeleton, USDZ validator probe
```

111 tracked files, 3.62 MB (2.04 MB of it is vendored Three.js), branch `main`. `origin` is set to
`https://github.com/mbj733/lessonlens.git`; the repository was created through the GitHub API as
**mbj733** and still has **0 commits** (verified after the failed push).

## 4. The blocker: no push credential

```
> git push -u origin main
fatal: Cannot prompt because user interactivity has been disabled.
fatal: could not read Username for 'https://github.com': terminal prompts disabled
```

Evidence gathered, not guessed:

| check | result |
|---|---|
| `git config --show-origin --get-all credential.helper` | `manager-core` configured, but… |
| `cmdkey /list` | no GitHub entry stored |
| `~/.ssh` | directory absent → no key |
| `ssh -T git@github.com` | `Permission denied (publickey)` |
| `GITHUB_TOKEN` / `GH_TOKEN` | not set |
| `gh` CLI | not installed |

So the remaining work needs one interactive action by the owner:

```powershell
cd E:\alsl项目\lessonlens
git push -u origin main          # credential manager prompts once
```

Then Settings → Pages → *Deploy from a branch* → `main` / `/`. The viewer URL becomes
`https://mbj733.github.io/lessonlens/`, which satisfies the plan's `curl -I` 200 criterion.

I deliberately did not read or reuse the token held inside the GitHub MCP server: using it would mean
extracting a credential from a config file, and this session's rules put reading user credentials out
of bounds.

## 5. What is still unverified

- **GitHub Actions has never run.** The workflow parses (checked with PyYAML) and every command it
  runs was executed locally, but "CI green" is not a verified fact until the first push.
- Pages hosting, the public URL and the `curl -I` 200 are untested for the same reason.
- The GitHub Release and the repository topics/metadata were not created.
