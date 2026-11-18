# Tutor prompt comparison

One live run on the exact 12 cases embedded in `tutoring_results.json`.
The original results were preserved. No dataset regeneration or grader changes were made.

| Metric | Baseline | Tutor v2 |
| --- | ---: | ---: |
| Mean model score | 6.33 | 6.67 |
| Mean combined score | 7.08 | 6.38 |
| Syntax passes | 6/6 | 3/6 |

## Prompt changes

Tutor v2 adds explicit system instructions to the original task template. It asks for one
small next step, a concrete explanation of the learner's sticking point, and progressively
less guidance. It checks attempt, tutor guidance, continued difficulty, and an explicit
request before providing a full solution. It also preserves raw artifact output when appropriate.

## Per-case scores

| Case | Model before | Model after | Combined before | Combined after |
| --- | ---: | ---: | ---: | ---: |
| tutor-001 | 2 | 9 | 2 | 9 |
| tutor-002 | 2 | 7 | 2 | 7 |
| tutor-003 | 9 | 9 | 9 | 9 |
| tutor-004 | 10 | 4 | 10 | 4 |
| tutor-005 | 9 | 6 | 9 | 6 |
| tutor-006 | 2 | 8 | 2 | 8 |
| tutor-007 | 10 | 4 | 10 | 2 |
| tutor-008 | 10 | 10 | 10 | 10 |
| tutor-009 | 2 | 9 | 6 | 4.5 |
| tutor-010 | 2 | 2 | 6 | 1 |
| tutor-011 | 8 | 2 | 9 | 6 |
| tutor-012 | 10 | 10 | 10 | 10 |

## Findings

- Cases 001, 002, and 006 improved when the tutor gave guidance instead of a full implementation.
- Case 009 improved from model score 2 to 9 by withholding premature code, but failed its Python syntax check. Its combined score dropped from 6 to 4.5 despite better tutoring.
- Case 007 regressed: the tutor withheld a complete solution even though the grader judged the exception satisfied.
- Case 010 still revealed a complete function and mixed it with prose, failing both the teaching rule and raw Python format.
- Case 011 returned a regex with spaces inside character classes and no whole-string constraint. It compiled, but was incorrect.
- The grader rewarded the old complete palindrome implementation with 10 but penalized the new conceptual algorithm with 4. Human calibration is needed before treating these scores as a reliable optimization target.

## Interpretation

This is a mixed candidate, not a demonstrated overall improvement. The model-grade mean
rose slightly, while the combined score and syntax pass rate fell. Review the component
scores and replies before choosing a prompt. A syntax failure must be interpreted in light
of whether the teaching policy permits the requested artifact; do not change the scoring
rules mid-comparison to make this candidate look better.

This was one run on cases used to revise the prompt, not a held-out evaluation. Original
grader settings and prompt snapshots were not recorded, so the baseline comparison has
reproducibility limits. The v2 prompt, dataset hash, and grader hash are recorded in
`tutor_v2_prompt.txt` and `tutor_v2_run_metadata.json`.
