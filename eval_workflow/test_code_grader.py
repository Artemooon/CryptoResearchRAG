import unittest

from eval_workflow.code_grader import grade_syntax, validate_json, validate_python, validate_regex


class CodeGraderTests(unittest.TestCase):
    def test_valid_and_invalid_python(self):
        self.assertEqual(validate_python("def count(nums):\n    return len(nums)"), 10)
        self.assertEqual(validate_python("def count("), 0)
        self.assertEqual(validate_python("   "), 0)

    def test_valid_and_invalid_json(self):
        self.assertEqual(validate_json('{"items": [1, 2]}'), 10)
        self.assertEqual(validate_json("{'items': [1, 2]}"), 0)
        self.assertEqual(validate_json(""), 0)

    def test_valid_and_invalid_regex(self):
        self.assertEqual(validate_regex(r"^\d+$"), 10)
        self.assertEqual(validate_regex("["), 0)
        self.assertEqual(validate_regex(""), 0)

    def test_prose_is_skipped_and_unknown_format_is_rejected(self):
        self.assertIsNone(grade_syntax("What would you try?", {"format": "text"}))
        self.assertIsNone(grade_syntax("What would you try?", {}))
        with self.assertRaises(ValueError):
            grade_syntax("content", {"format": "unknown"})

    def test_raw_format_rejects_markdown_and_extra_prose(self):
        self.assertEqual(grade_syntax('```python\nprint(1)\n```', {"format": "python"}), 0)
        self.assertEqual(grade_syntax('Here is JSON: {"x": 1}', {"format": "json"}), 0)


if __name__ == "__main__":
    unittest.main()
