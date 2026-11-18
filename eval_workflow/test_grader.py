import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import ValidationError

from eval_workflow.grader import ModelGrade, grade_by_model
from eval_workflow.run_eval import run_prompt, run_test_case


class GraderTests(unittest.TestCase):
    def setUp(self):
        self.case = {
            "task": "Count pairs of indices with a given sum.",
            "history": [{"role": "assistant", "content": "What would a simple approach check?"}],
            "learner_message": "I could try every pair, but that seems slow.",
            "format": "text",
        }
        self.grade = ModelGrade(
            strengths=["Builds on the learner's brute-force idea."],
            weaknesses=[],
            reasoning="One appropriate next question without revealing the implementation.",
            score=9,
        )
        self.responses = SimpleNamespace(
            create=Mock(return_value=SimpleNamespace(
                status="completed", output_text="How many pairs would you check for n numbers?"
            )),
            parse=Mock(return_value=SimpleNamespace(status="completed", output_parsed=self.grade)),
        )
        self.client = SimpleNamespace(responses=self.responses)

    def test_grader_receives_learner_context_and_returns_serializable_feedback(self):
        output = "How many pairs would you check for n numbers?"
        result = grade_by_model(self.case, output, client=self.client)
        request = self.responses.parse.call_args.kwargs
        self.assertEqual(json.loads(request["input"]), {
            "test_case": self.case, "tutor_response": output,
        })
        self.assertIs(request["text_format"], ModelGrade)
        self.assertEqual(json.loads(json.dumps(result)), self.grade.model_dump())

    def test_prompt_versions_preserve_baseline_and_enable_tutor_instructions(self):
        run_prompt(self.case, client=self.client, prompt_version="baseline")
        baseline = self.responses.create.call_args.kwargs["input"]
        self.assertEqual(baseline[0]["role"], "user")
        run_prompt(self.case, client=self.client, prompt_version="tutor_v3")
        improved = self.responses.create.call_args.kwargs["input"]
        self.assertEqual(improved[0]["role"], "system")
        self.assertEqual(improved[1:], baseline)

    def test_pipeline_uses_real_grade_instead_of_placeholder(self):
        result = run_test_case(self.case, client=self.client)
        self.assertEqual(result["score"], 9)
        self.assertEqual(result["model_score"], 9)
        self.assertIsNone(result["code_score"])
        self.assertEqual(result["grade"], self.grade.model_dump())
        self.assertEqual(result["test_case"], self.case)
        self.responses.create.assert_called_once()
        self.responses.parse.assert_called_once()
        tutor_input = self.responses.create.call_args.kwargs["input"]
        self.assertNotIn("strengths", str(tutor_input))

    def test_pipeline_averages_syntax_and_model_scores(self):
        case = {**self.case, "format": "python", "learner_message": "Show only a loop skeleton."}
        for output, syntax_score, combined in [("for x in nums:\n    pass", 10, 9.5), ("def broken(", 0, 4.5)]:
            with self.subTest(output=output):
                self.responses.create.return_value.output_text = output
                result = run_test_case(case, client=self.client)
                self.assertEqual(result["code_score"], syntax_score)
                self.assertEqual(result["model_score"], 9)
                self.assertEqual(result["score"], combined)
                request = self.responses.create.call_args.kwargs
                self.assertIn("without explanation or Markdown code fences", request["input"][-2]["content"])

    def test_incomplete_or_refused_grade_does_not_get_a_score(self):
        for status, parsed in [("incomplete", self.grade), ("failed", None), ("completed", None)]:
            with self.subTest(status=status, parsed=parsed):
                self.responses.parse.return_value = SimpleNamespace(status=status, output_parsed=parsed)
                with self.assertRaises(RuntimeError):
                    grade_by_model(self.case, "Candidate reply", client=self.client)

    def test_grade_rejects_invalid_scores_and_excess_feedback(self):
        for update in ({"score": 0}, {"score": 11}, {"strengths": ["x"] * 4}, {"reasoning": ""}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ModelGrade.model_validate({**self.grade.model_dump(), **update})


if __name__ == "__main__":
    unittest.main()
