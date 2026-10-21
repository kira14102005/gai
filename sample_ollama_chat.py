import time
import ollama

MODEL = "gemma3:1b"

messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant that answers questions in concise and accurate manner.",
    },
    {
        "role": "user",
        "content": "why sky is blue?",
    },
]

start = time.perf_counter()

response = ollama.chat(
    model=MODEL,
    messages=messages,
    stream=False,
    keep_alive="30m",
    options={
        "temperature": 0.1,
        "num_predict": 40,
    },
)

elapsed = time.perf_counter() - start
print(response.message.content)
print(f"\nTotal generation time: {elapsed:.2f}s")