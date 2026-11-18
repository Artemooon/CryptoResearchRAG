import os
from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, OpenAI

from my_agent.utils import add_system_message, add_user_message, chat

load_dotenv()

MODEL = "gpt-6-luna"

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise SystemExit("Set OPENAI_API_KEY in your .env file.")

client = OpenAI(
    api_key=api_key,
    timeout=30.0,
    max_retries=0,
)

# for model in client.models.list():
#     print(model.id)

prompt = input("Input prompt: ").strip()

try:
    messages = []
    # add_system_message(messages,
    #                    """You are a patient math tutor.
    #                    Do not directly answer a student's questions.
    #                    Guide them to a solution step by step..""")
    add_user_message(messages, prompt)

    print(f"Waiting for {MODEL} to respond...", flush=True)
    answer = chat(client, messages, MODEL, stream=True)

    # chat() already added the first assistant response to messages.
    add_user_message(messages, "Write another sentence")
    print(f"Waiting for {MODEL} to respond to the follow-up...", flush=True)
    final_answer = chat(client, messages, MODEL, stream=True)
except APITimeoutError:
    raise SystemExit("Api request timed out. Check your connection or try again.")
except APIConnectionError:
    raise SystemExit("Could not connect to OpenAI. Check your network or proxy settings.")
