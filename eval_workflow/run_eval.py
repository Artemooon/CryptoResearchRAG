import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from eval_workflow.generate_dataset import EvaluationCase
from eval_workflow.code_grader import grade_syntax
from eval_workflow.grader import grade_by_model
from eval_workflow.prompts import PROMPT_INSTRUCTIONS, build_prompt
from my_agent.utils import add_system_message, add_user_message, chat

MODEL = "gpt-6-luna"
DEFAULT_DATASET = Path(__file__).parent / "data" / "tutoring_dataset.json"
DEFAULT_OUTPUT = Path(__file__).parent / "data" / "tutoring_results.json"


def create_client() -> OpenAI:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    return OpenAI(timeout=120.0, max_retries=0)


def run_prompt(
    test_case: dict, *, client: OpenAI | None = None, model: str = MODEL,
    prompt_version: str = "tutor_v3",
) -> str:
    """Answer the latest learner turn without exposing the grader's notes."""
    case = EvaluationCase.model_validate(test_case)
    if prompt_version not in PROMPT_INSTRUCTIONS:
        raise ValueError(f"Unknown prompt version: {prompt_version}")
    if client is None:
        client = create_client()

    prompt = build_prompt(case.task)
    messages = []
    instructions = PROMPT_INSTRUCTIONS[prompt_version]
    if instructions:
        add_system_message(messages, instructions)
    if case.history:
        add_user_message(messages, prompt)
        messages.extend(message.model_dump() for message in case.history)
        add_user_message(messages, case.learner_message)
    else:
        add_user_message(messages, f"{prompt}\n{case.learner_message}")
    if case.format != "text":
        messages[-1]["content"] += (
            f"\n\nReturn only {case.format}, without explanation or Markdown code fences."
        )
    return chat(client, messages, model, max_output_tokens=4000)


def run_test_case(
    test_case: dict, *, client: OpenAI | None = None, model: str = MODEL,
    prompt_version: str = "tutor_v3",
) -> dict:
    """Run one tutoring case and grade the response."""
    if client is None:
        client = create_client()
    output = run_prompt(test_case, client=client, model=model, prompt_version=prompt_version)
    grade = grade_by_model(test_case, output, client=client)
    code_score = grade_syntax(output, test_case)
    model_score = grade["score"]
    score = model_score if code_score is None else (model_score + code_score) / 2
    return {
        "output": output,
        "test_case": test_case,
        "score": score,
        "model_score": model_score,
        "code_score": code_score,
        "grade": grade,
        "prompt_version": prompt_version,
    }


def run_eval(
    dataset: list[dict], *, client: OpenAI | None = None, model: str = MODEL,
    prompt_version: str = "tutor_v3",
) -> list[dict]:
    """Process every test case with a fresh conversation and collect the results."""
    if not dataset:
        return []
    if client is None:
        client = create_client()

    results = []
    for index, test_case in enumerate(dataset, start=1):
        print(f"Running case {index}/{len(dataset)}...", flush=True)
        result = run_test_case(test_case, client=client, model=model, prompt_version=prompt_version)
        results.append(result)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the tutoring prompt and grade each response.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, help="Run only the first N cases.")
    parser.add_argument("--prompt", choices=tuple(PROMPT_INSTRUCTIONS), default="tutor_v3")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive.")
    if args.output.exists():
        parser.error(f"{args.output} already exists. Choose another --output to keep previous results.")

    with args.dataset.open(encoding="utf-8") as file:
        saved_dataset = json.load(file)
    # Our generator saves metadata around the list; a plain list also works.
    dataset = saved_dataset["cases"] if isinstance(saved_dataset, dict) else saved_dataset
    if not isinstance(dataset, list) or not all(
        isinstance(case, dict) and isinstance(case.get("task"), str) and case["task"].strip()
        for case in dataset
    ):
        parser.error("Dataset must contain a list of cases with non-empty 'task' strings.")
    if args.limit is not None:
        dataset = dataset[:args.limit]
    try:
        for case in dataset:
            EvaluationCase.model_validate(case)
    except ValidationError as error:
        parser.error(f"Expected tutoring cases. Generate a new tutoring dataset.\n{error}")

    print("Each case makes two API requests: one tutor response and one model grade.")
    results = run_eval(dataset, prompt_version=args.prompt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"Saved {len(results)} results to {args.output}")


if __name__ == "__main__":
    main()
