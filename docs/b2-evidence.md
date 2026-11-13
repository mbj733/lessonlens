# B2 — Planner evidence (schema + mock provider)

Executed: 2026-11-13 (Asia/Shanghai) · Repo: `E:\alsl项目\lessonlens`
Numbers below come from the commands in §6.

## 1. What B2 adds

| piece | file | what it guarantees |
|---|---|---|
| scene contract | `schema/scene.schema.json` | JSON Schema 2020-12; 8–24 objects, 8+ interactions, 1–8 tasks, per-object ≥1 claim with verbatim `quote` + `page` |
| validator | `src/lessonlens/planner.py` (`validate_scene`) | schema errors **plus** what a schema cannot express: duplicate ids, answers/targets pointing at missing objects, claim page out of range, triangle budget, `meta.triangle_estimate` recomputation |
| mock provider | `MockPlanner` | deterministic rules, no network, no key |
| cache provider | `CachePlanner` | replays a committed `cache/<deck>.json`, writes one on a miss |
| deepseek provider | `DeepSeekPlanner` | real HTTP call, response parsed then validated, cached on success |
| cli | `lessonlens build <paths> --out eval/scenes --llm mock` | writes one scene per input file |

## 2. Build run

```
> .venv\Scripts\python.exe -m lessonlens build eval/slides --out eval/scenes --root . --llm mock
deck                                      objects  clicks  tasks  tris    bytes
eval/slides/en-01-sorting.pdf                  12      12      3  10656    11515
eval/slides/en-01-sorting.pptx                 12      12      3  10656    12069
eval/slides/en-02-bst.pptx                     12      12      3  10656    12188
eval/slides/en-03-hashing.pptx                 12      12      3  10656    11936
eval/slides/en-04-shortest-paths.pdf           12      12      3  10656    11766
eval/slides/en-04-shortest-paths.pptx          12      12      3  10656    11767
eval/slides/en-05-processes-threads.pptx       12      12      3  10656    11959
eval/slides/zh-06-binary-tree.pdf              12      12      3   9708    11695
eval/slides/zh-06-binary-tree.pptx             12      12      3   9708    12140
eval/slides/zh-07-dp.pptx                      12      12      3   9708    12366
eval/slides/zh-08-db-normalization.pptx        12      12      3   8760    12599
eval/slides/zh-09-tcp.pdf                      12      12      3  10656    12020
eval/slides/zh-09-tcp.pptx                     12      12      3  10656    12607
eval/slides/zh-10-backprop.pptx                12      12      3  10656    11685

14 scenes -> eval\scenes  (provider: mock)
```

14 scenes, 168,312 bytes total, largest scene 12,607 bytes against the 200 KB budget.
Triangle estimates 8,760–10,656 against the 60,000 budget.

## 3. Gate results

```
> .venv\Scripts\python.exe -m ruff check .
All checks passed!

> .venv\Scripts\python.exe -m pytest -q
................................                                         [100%]
32 passed
```

`tests/test_schema.py` (16 cases) covers:

1. `test_every_scene_validates` — 14/14 schema-pass (the plan's criterion #1).
2. `test_object_and_interaction_budget` — 8–24 objects, one click interaction per object, ids sorted and unique.
3. `test_every_page_is_represented` — all ten pages of every deck appear in some object.
4. `test_claims_are_verbatim_grounded` — every claim's `quote` occurs, after whitespace normalisation, in the source page text; `claim.page == object.page`.
5. `test_planning_is_deterministic` / `test_committed_scenes_are_current` — same input ⇒ same digest, and the committed `eval/scenes/*.json` match a fresh build (stale artifacts fail CI).
6. `test_scene_size_under_200kb`, `test_triangle_budget`.
7. `test_invalid_scenes_are_rejected` — six mutations (empty claims, unknown answer, unknown target, duplicate id, wrong triangle meta, unsupported primitive) are all caught with a readable message.
8. `CachePlanner` write→replay; `DeepSeekPlanner` missing key / non-JSON / schema-invalid response; request shape (model, `temperature: 0`, `response_format: json_object`, slide text in the user message).
9. CLI smoke build.

Determinism checked outside pytest as well — a second build into a fresh directory produced byte-identical files:

```
> python -m lessonlens build eval/slides --out %TEMP%\ll_scenes_rebuild --llm mock
hash mismatches: 0 / 14
```

## 4. The mock provider, stated honestly

The mock planner maps **one object per slide** (first eligible block, plus detail objects up to 12),
arranges them on a 4-column grid, and builds a click interaction per object. Its claim `text` is a
prefix of the slide `quote`, so `unsupported_rate` is 0 **by construction** — a rule engine cannot
hallucinate. That number's discriminating power only appears with the `deepseek` provider, which is
why B4's verifier tests use hand-written positive/negative quote pairs rather than mock output.

`meta.notes` in every mock scene says exactly this, so the limitation travels with the artifact.

## 5. Defects found and fixed in this batch

**(a) Scene JSON collided by stem, again.** `en-01-sorting.pdf` and `.pptx` both wrote
`eval/scenes/en-01-sorting.json`; `test_committed_scenes_are_current` caught the inconsistency
(`df0b750…` vs `30aadfc…`). Output is now named by the full file name (`en-01-sorting.pptx.json`).
The same class of bug already bit `extract` in B1 — the lesson is now enforced by a test on both
sides.

**(b) The 24-character quote threshold silently dropped every Chinese deck.** `zh-06` produced
7 objects and the build failed with `only 7 usable blocks, need at least 8`: 24 characters is a
long English sentence but a whole Chinese one. Threshold is now 16 characters, and the schema still
requires ≥12.

**(c) Table-only pages vanished from the scene.** `zh-06`, `zh-07`, `zh-08`, `zh-09` have a table
slide; table blocks were excluded from planning, so page 9 of `zh-09` had no object at all. Tables
are now eligible (label = header row), and `test_every_page_is_represented` fails if any page is
missing.

**(d) The "order" task listed two objects from the same page**, which makes the question ambiguous.
It now picks one object per page.

## 6. Limits of this batch

- **The DeepSeek path has never been called with a real key.** No key exists in this environment;
  everything about it is unit-tested through an injected transport. README and the report must say
  "adapter implemented, not exercised against the live API" until a key is available.
- The mock planner does not paraphrase and does not use embeddings; it is a rule engine, and the
  report must not present its metrics as evidence of model quality.
- `CachePlanner` trusts the committed cache file after validation, so a stale cache silently wins
  over a changed deck — the cache key is the deck stem only. Acceptable while the corpus is frozen;
  B4 should hash the extract into the cache key.

## 7. Reproduce

```powershell
.venv\Scripts\python.exe -m lessonlens build eval/slides --out eval/scenes --root . --llm mock
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest tests/test_schema.py -q
```
