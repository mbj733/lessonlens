# B4 — Verification and evaluation evidence

Executed: 2026-11-13 (Asia/Shanghai) · Repo: `E:\alsl项目\lessonlens`
Every number here comes from `python -m lessonlens eval`; the report is generated, not written.

## 1. What exists now

| file | role |
|---|---|
| `src/lessonlens/verify.py` | three gates per claim + `self_test` corruption harness |
| `src/lessonlens/eval.py` | metrics aggregation, report writer (`eval/report.md`, `eval/metrics.json`) |
| `src/lessonlens/cli.py` | `lessonlens eval [--scenes …] [--out …] [--cache-only]` |
| `eval/report.md` | the generated table the plan asks for |
| `tests/test_verify.py`, `tests/test_eval.py` | 14 + 12 cases |

### The three gates

1. **quote gate** — `normalize(quote)` must occur in `normalize(page.text)` of the page the claim
   names. Fails as `UNSUPPORTED` when the quote exists nowhere.
2. **page gate** — if the quote occurs, but on other pages, the verdict is `WRONG_PAGE` (a factual
   error, not a typo) and the report lists where it really occurs.
3. **grounding gate** — the claim sentence must be covered by its quote: token overlap (Latin words +
   CJK character bigrams) ≥ 0.5, otherwise `UNGROUNDED`. This is **lexical, not semantic** — no
   embedding model is installed, and the report says so.

## 2. Gate output

```
> .venv\Scripts\python.exe -m lessonlens eval
metric                    value   target
schema_pass_rate        100.0%   100%
grounding_coverage      100.0%   >=80%
quote_hit_rate          100.0%   >=85%
unsupported_rate          0.0%   <=10%
task_solvable_rate      100.0%   100%
verifier_self_test      100.0%   100%

14 scenes, 168 objects, 168 claims
report -> eval\report.md  (metrics -> eval\metrics.json)
```

| metric | value | plan target |
|---|---|---|
| schema_pass_rate | 100.0% (14/14) | 100% |
| grounding_coverage | 100.0% (168/168 objects) | ≥ 80% |
| quote_hit_rate | 100.0% (168/168 claims) | ≥ 85% |
| unsupported_rate | 0.0% (0/168) | ≤ 10% |
| task_solvable_rate | 100.0% (42/42 tasks) | 100% |
| verifier self-test | 126/126 corruptions detected | 100% |

The self-test is the part that makes the other five meaningful: 42 trials × 3 corruption types
(a quote word scrambled, a page shifted by one, a claim sentence replaced with an unrelated one) are
injected into copies of the real scenes, and **every one** is caught. Without it, "0 unsupported"
could just mean "the checker never looks".

## 3. Tests

```
> .venv\Scripts\python.exe -m pytest -q
.........................................................                [100%]
57 passed
```

`tests/test_verify.py` — the plan's five positives and five negatives, plus boundary cases:

| case | expected verdict |
|---|---|
| exact quote | SUPPORTED |
| quote with different whitespace/line breaks | SUPPORTED |
| Chinese sentence quote | SUPPORTED |
| quote is a substring of the page | SUPPORTED |
| claim is a prefix of the quote | SUPPORTED |
| quote belongs to another page | WRONG_PAGE + reported pages |
| invented quote | UNSUPPORTED |
| empty quote | UNSUPPORTED ("empty quote") |
| page number out of range | UNSUPPORTED ("page out of range") |
| claim sentence unrelated to its quote | UNGROUNDED |

`tests/test_eval.py` adds: metrics cover 14 scenes / 168 objects / 168 claims / 42 tasks; report is
byte-reproducible across two writes; a tampered quote **moves** `unsupported_rate` above zero (the
negative control for the pipeline itself); the committed report's headline rows match a fresh run;
web metrics are present and sane.

## 4. Defect found

**Short Chinese claims scored 0% overlap.** `_tokens` switched to CJK bigrams only when a text had
≥ 4 CJK characters, so a three-character claim like `二叉树` produced an empty token set and any
Chinese claim shorter than four characters would have been reported `UNGROUNDED` regardless of
support. Fixed by always emitting both Latin word tokens and CJK bigrams (plus the single character
case). Found by the hand-written test, not by the corpus — the mock planner's claims are long
sentences.

## 5. Limits of this batch

- **The perfect metrics are manufactured by the mock planner.** Its claim text is a prefix of the
  quote, so nothing can be unsupported. The report states this in "Honest notes"; the metrics only
  become evidence of model quality with `--llm deepseek`, which has never been called against the
  live API here.
- `unsupported_rate` counts every non-`SUPPORTED` verdict (`WRONG_PAGE`, `UNGROUNDED`,
  `UNSUPPORTED`) as unsupported. That is deliberate — the plan's wording ("verdict=UNSUPPORTED")
  would hide page errors — and it is written in the report's definitions.
- The grounding gate cannot tell a paraphrase from a fabrication if the paraphrase reuses enough
  tokens. A semantic model is the plan's optional third gate and is not installed.
- `usdz_ok` and the browser gates enter the report only through `eval/web-metrics.json` (present)
  and `out/usdz-report.json` (B5).

## 6. Reproduce

```powershell
.venv\Scripts\python.exe -m lessonlens eval
.venv\Scripts\python.exe -m pytest tests/test_verify.py tests/test_eval.py -q
.venv\Scripts\python.exe -X utf8 tools\web_check.py   # refreshes eval/web-metrics.json
```
