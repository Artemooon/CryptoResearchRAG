import argparse
import json
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, model_validator

MODEL = "gpt-6-luna"
DEFAULT_OUTPUT = Path(__file__).parent / "data" / "tutoring_dataset.json"


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class EvaluationCase(BaseModel):
    task: str = Field(min_length=1)
    history: list[ConversationMessage]
    learner_message: str = Field(min_length=1)
    format: Literal["text", "python", "json", "regex"] = "text"

    @model_validator(mode="after")
    def check_history(self):
        # The task is the opening user turn; the latest user turn follows history.
        expected_roles = ["assistant" if index % 2 == 0 else "user" for index in range(len(self.history))]
        if [message.role for message in self.history] != expected_roles or (
            self.history and self.history[-1].role != "assistant"
        ):
            raise ValueError("History must alternate assistant/user, starting and ending with assistant.")
        return self


class EvaluationDataset(BaseModel):
    cases: list[EvaluationCase]


def generate_dataset(num_cases: int = 12, *, client: OpenAI | None = None) -> EvaluationDataset:
    """Generate learner situations for evaluating the tutor's next response."""
    if not 1 <= num_cases <= 20:
        raise ValueError("num_cases must be between 1 and 20.")

    if client is None:
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        client = OpenAI(timeout=120.0, max_retries=0)

    response = client.responses.parse(
        model=MODEL,
        input=f"""Generate an evaluation dataset for a prompt evaluation.
The dataset will evaluate prompts that help learners work through LeetCode-style
algorithmic tasks with hints by default. Complete solutions are allowed only when
the learner explicitly asks after trying and remaining stuck despite guidance.

Generate cases in this format:
{{
  "cases": [
    {{
      "task": "A self-contained coding problem with constraints and examples",
      "history": [],
      "learner_message": "I don't know where to start.",
      "format": "text"
    }}
  ]
}}

* Focus on short Python problems with varied topics and difficulty.
* Include learners who are starting, trying a simple approach, mistaken,
  confused, or making progress.
* For follow-ups, include short prior dialogue in history as role/content objects,
  alternating assistant/user and starting and ending with assistant.
* Keep history empty for first turns. learner_message is the latest user turn.
* Generate test inputs, not candidate tutor responses or grading instructions.
* Use format "text" for guidance or answers with explanations. For raw Python,
  JSON, or regex, have the learner request only that artifact without prose or
  code fences. Brief Python comments are allowed; explanations outside code are not.
* Generate {num_cases // 2} cases with format "text" and
  {num_cases - num_cases // 2} with artifact formats, mixing python/json/regex
  when the count allows. For odd totals, the artifact group gets the extra case.
* Include at least one learner_message explicitly asking for a complete Python
  solution with no explanation, using format "python". Its history must show a
  concrete student attempt, tutor guidance, and continued difficulty with the
  reasoning. A request or an unsupported claim of having tried is not enough.
* When the count allows, also include an immediate full-answer request with no
  attempt, using format "text": the appropriate reply is guidance, not full code.
  Small examples and partial snippets do not require this full-solution exception.
* A format request never overrides this teaching rule. Any complete artifact,
  including a regex that solves the whole task, needs the same attempt history.
  Do not write the candidate full solution into the dataset.
* Avoid duplicate situations and check the correctness of problem examples.

Please generate {num_cases} objects.
""",
        text_format=EvaluationDataset,
        reasoning={"effort": "low"},
        max_output_tokens=16000,
        store=False,
    )

    if response.status != "completed" or response.output_parsed is None:
        raise RuntimeError("Dataset generation did not complete or was refused; no dataset was saved.")

    dataset = response.output_parsed
    if len(dataset.cases) != num_cases:
        raise ValueError(f"Requested {num_cases} cases, received {len(dataset.cases)}.")
    if sum(case.format == "text" for case in dataset.cases) != num_cases // 2:
        raise ValueError("Expected half text cases (rounded down), with the rest using artifact formats.")
    situations = {
        (case.task.strip().casefold(), tuple((m.role, m.content.strip()) for m in case.history),
         case.learner_message.strip().casefold())
        for case in dataset.cases
    }
    if len(situations) != num_cases:
        raise ValueError("The generated dataset contains duplicate learner situations.")
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate realistic algorithm tutoring evaluation cases.")
    parser.add_argument("--count", type=int, default=12, help="Number of cases, from 1 to 20 (default: 12).")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"{args.output} already exists. Choose another --output to keep the dataset fixed.")

    print(f"Generating {args.count} evaluation cases with {MODEL}...", flush=True)
    dataset = generate_dataset(args.count)
    payload = {
        "generator_model": MODEL,
        "evaluation_goal": "adaptive_algorithm_tutoring",
        "schema_version": 4,
        "review_status": "unreviewed",
        "cases": [
            {"id": f"tutor-{index:03d}", **case.model_dump()}
            for index, case in enumerate(dataset.cases, start=1)
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"Saved {len(dataset.cases)} cases to {args.output}")
    print("Review the generated tasks and learner conversations before evaluation.")


if __name__ == "__main__":
    main()
