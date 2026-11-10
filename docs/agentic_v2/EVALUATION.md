# Agentic Evaluation

Phase 4 adds a versioned 150-question evaluation set while preserving the
original 60-question set and its metric definitions.

## Datasets

| File | Purpose |
|---|---|
| `eval/questions.jsonl` | Original frozen D3 set; unchanged |
| `eval/agentic_v2/questions.jsonl` | Phase 4 set with `q001`-`q150` |
| `eval/configs/phase4_b1_fast.yaml` | Full B1 Fast Phase 4 configuration |

The first 60 records in the Phase 4 file retain every original field. They add
an `agentic` annotation block for expected route, required tools, and expected
evidence sufficiency. The new `q061`-`q150` records are all
`review_status: draft`.

Current distribution:

| Dimension | Distribution |
|---|---|
| Question type | fact 70, multi_hop 60, refusal 20 |
| Expected route | simple_fact 68, high_risk 47, multi_hop 35 |
| Languages | Chinese and English from the original 60 plus Chinese expansion |

All answerable records reference existing chunks. Every `gold_evidence.quote`
must occur exactly in the referenced chunk text. Multi-hop records must cover
at least two distinct sources.

The deterministic route classifier currently matches 136 of 150 draft route
labels (`0.9067`). This value does not call a model or use the network.

## Human Review Status

Independent human review was not executed. The project owner explicitly
exempted this review for Phase 4.

No reviewer identity, review timestamp, `approved` status, or human pass rate
is fabricated. All newly created questions and all new agentic labels are
marked `draft`. Results therefore describe provisional evaluation labels, not
human-approved ground truth.

## Existing Metrics

The original `metrics` object and formulas remain unchanged:

- Hit@5
- Gold chunk recall@5
- Citation accuracy
- Citation coverage
- Answer correctness
- Refusal accuracy
- False refusal counts
- P50/P95 latency

Citation accuracy still uses the existing denominator: answerable cases with at
least one citation. Answer correctness still gives an existing manual label
precedence over the DeepSeek-assisted judge when a labels file is supplied.

## Agentic Metrics

Phase 4 adds a separate `agentic_metrics` object.

| Metric | Definition |
|---|---|
| Route accuracy | Cases where the actual route equals `expected_route`, divided by cases with that label |
| Tool selection accuracy | Cases where every tool in `required_tools` was invoked, divided by cases with tool labels |
| Tool success rate | Successful tool outcomes divided by all tool outcomes |
| Multi-step completion rate | Multi-hop cases that were not refused, cited every expected source, and had final correctness `true`, divided by multi-hop cases with a known final correctness label |
| Evidence sufficiency accuracy | Cases where actual and expected evidence sufficiency match, divided by cases with both values |

Additional rules:

- Extra tool calls do not reduce tool selection accuracy.
- Tool selection is measured separately from whether the selected tool
  succeeded.
- When `--judge none` and no manual labels exist, multi-step completion has
  zero evaluated cases rather than treating unknown correctness as success.
- The current one-snapshot source corpus can only return
  `insufficient_versions` from version comparison. This is recorded as a real
  tool failure and is not replaced with a fabricated success.

## Commands

Validate the original frozen set:

```powershell
.\.venv\Scripts\python.exe scripts/validate_eval.py
```

Validate the Phase 4 dataset, labels, and exact evidence quotes:

```powershell
.\.venv\Scripts\python.exe scripts/validate_agentic_eval.py
```

Regenerate the dataset from its checked build specification:

```powershell
.\.venv\Scripts\python.exe scripts/build_agentic_eval.py
```

Run a deterministic local smoke evaluation without DeepSeek:

```powershell
.\.venv\Scripts\python.exe -m src.evaluate `
  --config eval/configs/phase4_b1_fast.yaml `
  --questions eval/agentic_v2/questions.jsonl `
  --backend bm25 `
  --mode extractive `
  --judge none `
  --limit 10 `
  --run-name phase4_smoke
```

Run the smaller synthetic smoke used by CI from a clean checkout:

```powershell
.\.venv\Scripts\python.exe -m src.evaluate `
  --config eval/configs/phase4_b1_fast.yaml `
  --questions eval/fixtures/agentic_smoke_questions.jsonl `
  --chunks eval/fixtures/agentic_smoke_chunks.jsonl `
  --backend bm25 `
  --mode extractive `
  --judge none `
  --run-name ci_eval_smoke
.\.venv\Scripts\python.exe scripts/check_eval_smoke.py `
  --summary eval/results/ci_eval_smoke/summary.json
```

The CI fixture is synthetic and is not part of the 150-question benchmark
dataset. It validates the evaluation path, not model quality.

Run the full B1 Fast evaluation after confirming network and API cost:

```powershell
.\.venv\Scripts\python.exe -m src.evaluate `
  --config eval/configs/phase4_b1_fast.yaml `
  --questions eval/agentic_v2/questions.jsonl `
  --run-name phase4_b1_fast
```

Run the optional B3 comparison:

```powershell
.\.venv\Scripts\python.exe -m src.evaluate `
  --config eval/configs/b3_deepseek.yaml `
  --questions eval/agentic_v2/questions.jsonl `
  --run-name phase4_b3_deepseek
```

Phase 5 ran the full evaluation as `phase5_b1_fast_150` in a network-approved
environment.

| Metric | Result |
|---|---:|
| Successful / failed requests | 150 / 0 |
| Hit@5 | 0.9846 |
| Gold unit recall@5 | 0.8949 |
| Citation accuracy | 0.9868 |
| Answer correctness | 0.5385 |
| Fact / multi-hop / refusal accuracy | 0.7857 / 0.2500 / 1.0000 |
| Route accuracy | 0.9067 |
| Tool selection accuracy | 1.0000 |
| Tool success rate | 0.9915 |
| Multi-step completion | 0.2333 |
| Evidence sufficiency accuracy | 0.6733 |

The `deepseek_auto` correctness source covered all 130 answerable questions.
There is still no independent human review. At the recorded off-peak rates,
198,442 prompt tokens and 23,341 completion tokens correspond to an estimated
CNY 0.2918 model cost.

The primary quality gap is multi-hop evidence sufficiency and completion. The
result is recorded in `eval/results/phase5_b1_fast_150/summary.json`.

## Outputs

Each evaluation run writes:

| File | Content |
|---|---|
| `summary.json` | Existing metrics, agentic metrics, errors, and trace summary |
| `summary.csv` | Existing metric rows plus agentic metric rows |
| `per_question.jsonl` | Full local per-question output; ignored by Git |
| `review.csv` | Blank manual review template; ignored by Git |
| `traces.jsonl` | Sanitized local traces; ignored by Git |
| `errors.jsonl` | Sanitized failed requests; ignored by Git |
| `tool_failures.jsonl` | Failed tool outcomes; ignored by Git |

`eval/results/latest_run.json` continues to point at the latest run.
