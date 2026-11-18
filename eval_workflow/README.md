# Algorithm tutoring evaluation

Generate learner situations, then compare how prompts guide the learner through
an algorithmic problem. The workflow uses GPT-6 Luna and the OpenAI Responses API.
An independent request grades each tutor response using structured output.

Set `OPENAI_API_KEY` in the root `.env` and run from the repository root:

```bash
uv run python -m eval_workflow.generate_dataset
```

The default is 12 cases. Use `--count 15` for a larger set. Generation makes a paid
API request and saves `eval_workflow/data/tutoring_dataset.json`. To preserve
existing datasets, choose a new path with `--output`.

Each case has four fields:

- `task`: a self-contained algorithmic problem with constraints and examples.
- `history`: prior dialogue after the task, or an empty list for a first turn.
- `learner_message`: the latest user turn that the tutor should answer.
- `format`: `text` for guidance, or `python`, `json`, or `regex` for a raw artifact.
  Existing cases without this field default to `text`.

History uses `role` and `content` objects. It alternates assistant/user and starts
and ends with assistant; the task and latest learner message are added by the
runner. The generator checks case count, history order, and duplicate situations.
Review generated examples for correctness before evaluation.

Half the generated cases use `text` (rounded down for odd totals); the rest use
artifact formats. At least one learner explicitly requests a complete Python
solution. The generator produces the request, not the tutor's answer. Hints are
the default. A complete solution requires a visible student attempt, tutor
guidance, continued difficulty, and an explicit request. Asking immediately is
not enough. The dataset includes both kinds of requests. Small examples and
partial snippets remain allowed. Raw artifact cases allow no prose or code fences; use `text` when
the answer should include an explanation.

The dataset prompt generates situations. The separate tutor prompt in
`prompts.py` controls how the model teaches. `grader.py` separately defines how
to assess the next reply using the task, dialogue, and learner's latest message.

Try one case:

```bash
uv run python -m eval_workflow.run_eval --limit 1
```

Omit `--limit 1` to run all cases. Results save to
`eval_workflow/data/tutoring_results.json` as an array of `output`, `test_case`,
`score`, and `grade` objects. The grade contains `strengths`, `weaknesses`,
`reasoning`, and a score from 1 to 10. Strengths and weaknesses can be empty when
warranted, so the grader does not need to invent praise or criticism. Each case
makes two paid requests: one to the tutor and one to the grader, both using
GPT-6 Luna by default. Use a new `--output` for each run. Responses are limited to
4,000 output tokens, so check longer answers for truncation.

For artifact cases, the runner requests raw output without explanation or code
fences. `code_grader.py` checks Python with `ast.parse`, JSON with `json.loads`,
and regex with `re.compile`. Each returns 10 or 0. The final score averages the
model and code scores. For `text`, syntax grading is skipped and the final score
is the model score. Results retain `model_score` and `code_score` separately;
`code_score` is null when skipped.

These checks parse or compile syntax; they do not execute generated code, prove
correctness, or measure time/space complexity. A regex can compile while matching
the wrong strings. A failed syntax check can still produce a nonzero averaged
score, so inspect the component scores when comparing runs.

`run_prompt()` builds the conversation, `run_test_case()` calls `grade_by_model()`
after the tutor responds, and `run_eval()` collects the results. Each case gets
its own conversation. The grader does not execute code; its scores are judgments
to calibrate against human reviews, not proof of correctness. Failed, incomplete,
or refused grading requests stop the run instead of assigning a fallback score.
This tests one tutor reply to a fixed conversation, not whether the learner
actually internalized the material.

The runner defaults to `--prompt tutor_v3`, which uses concise instructions,
XML sections, and three examples in `prompts.py`. The examples show an immediate
answer request, a single-step explanation, and a justified full solution. They
illustrate the existing teaching policy rather than adding new requirements.
The XML organizes the instructions; replies still follow the requested format.

Use `--prompt baseline` for the simple task template without tutor instructions.
The selected version is saved with each result. For the comparison against the
first results, the exact test cases were
copied from `tutoring_results.json` to `tutoring_comparison_dataset.json`:

```bash
uv run python -m eval_workflow.run_eval --dataset eval_workflow/data/tutoring_comparison_dataset.json --prompt tutor_v3 --output eval_workflow/data/tutoring_results_v3.json
```

The historical v2 prompt snapshot and dataset/grader hashes are saved in
`data/tutor_v2_prompt.txt` and `data/tutor_v2_run_metadata.json`. Review model and
syntax scores separately: a correct decision to withhold a premature full
solution can fail the raw-artifact syntax check when a case requests code too
early. The average alone can obscure this conflict. Grader judgments can also
vary between runs.

Existing datasets are preserved. The original `data/dataset.json` is
solution-focused, and its `algo-003` second example incorrectly merges disjoint
intervals. Generate a fresh tutoring dataset rather than using it as ground truth.
