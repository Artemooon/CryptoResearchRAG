def add_user_message(messages, text):
    user_message = {"role": "user", "content": text}
    messages.append(user_message)

def add_assistant_message(messages, text):
    assistant_message = {"role": "assistant", "content": text}
    messages.append(assistant_message)

def add_system_message(messages, text):
    system_message = {"role": "system", "content": text}
    messages.append(system_message)

def chat(client, messages, model, max_output_tokens=1000, stream=False):
    request = {
        "model": model,
        "input": messages,
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": "none"},
        "temperature": 0,
        "store": False,
    }
    if stream:
        with client.responses.stream(**request) as events:
            for event in events:
                if event.type == "response.output_text.delta":
                    print(event.delta, end="", flush=True)
                elif event.type == "error":
                    raise RuntimeError(event.message)
            response = events.get_final_response()
        print()
    else:
        response = client.responses.create(**request)

    if response.status == "failed":
        raise RuntimeError(response.error.message if response.error else "Response failed.")

    text = response.output_text
    if text:
        add_assistant_message(messages, text)
    return text
