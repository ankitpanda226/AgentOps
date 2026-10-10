# Evaluation Report

## Benchmark Design

The evaluation suite is intentionally deterministic. It uses 10 JSONL tasks in `evals/tasks.jsonl`, each with:

- `id`
- `user_request`
- `expected_keywords`
- `expected_tools`
- `expected_output_fields`

`python evals/run_eval.py` runs each task through `run_agent_workflow` with a deterministic fake vector store. Results are saved to `evals/results.json` and printed as a compact table.

The benchmark covers:

- Repo understanding.
- Implementation planning.
- Test generation.
- Bug analysis.
- GitHub issue drafting.
- API integration planning.
- Documentation generation.
- RAG-based file lookup.
- Safety/risk critique.
- Memory-aware task summary.

## Metrics

### Keyword Coverage

`keyword_coverage(output_text, expected_keywords)` measures whether expected words or phrases appear in the serialized output.

Score:

```text
matched expected keywords / total expected keywords
```

If no keywords are expected, the score is `1.0`.

### Required Field Score

`required_fields_score(output, expected_fields)` checks whether structured fields are present. It supports nested dot paths such as:

- `plan.steps`
- `issue_draft.body`
- `context.0.file_path`

Score:

```text
present required fields / total required fields
```

If no fields are expected, the score is `1.0`.

### Tool Coverage

`tool_coverage(actual_tools, expected_tools)` checks whether the workflow used expected tools such as:

- `retriever`
- `run_pytest`
- `create_issue_draft`

Matching is case-insensitive.

Score:

```text
matched expected tools / total expected tools
```

If no tools are expected, the score is `1.0`.

### Aggregate Score

`aggregate_score(scores)` averages all numeric metric values. If the score dictionary is empty, it returns `0.0`.

## Sample Results

Current deterministic eval run:

| Task ID | Scenario | Aggregate |
| --- | --- | ---: |
| task_001 | Repo understanding | 1.00 |
| task_002 | Implementation planning | 1.00 |
| task_003 | Test generation | 1.00 |
| task_004 | Bug analysis | 1.00 |
| task_005 | GitHub issue drafting | 1.00 |
| task_006 | API integration planning | 1.00 |
| task_007 | Documentation generation | 1.00 |
| task_008 | RAG-based file lookup | 1.00 |
| task_009 | Safety/risk critique | 1.00 |
| task_010 | Memory-aware task summary | 1.00 |

## Why Deterministic Evals Are Useful

Deterministic evals are valuable early in the project because they provide a stable regression signal:

- No paid API calls.
- No network dependence.
- Repeatable results on local machines and CI.
- Clear coverage of output shape and tool routing.
- Fast feedback when refactoring agents, graph orchestration, or schemas.

They are not a replacement for semantic quality evaluation, but they protect the contract between user requests, agent workflow, tools, and structured output.

## Limitations

- Keyword checks can be gamed by superficial text matches.
- Required field checks verify structure, not answer quality.
- Tool coverage checks whether a tool was used, not whether it was used well.
- The fake vector store does not measure real retrieval quality.
- The benchmark does not yet measure latency, hallucination risk, or code-change correctness.

## Future Improvements

- Add retrieval precision/recall checks against known source files.
- Add latency metrics by task and workflow node.
- Add hallucination checks using source-grounding assertions.
- Add golden-answer comparisons for selected tasks.
- Add evals for live ChromaDB indexing over fixture repositories.
- Add LLM-backed qualitative grading as an optional, non-default mode.
