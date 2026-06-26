from transformers import pipeline

pipe = pipeline(
    "image-text-to-text",
    model="Qwen/Qwen3.5-4B"
)

messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "Explain what machine learning is."}
        ]
    }
]

output = pipe(text=messages, max_new_tokens=200)

print(output[0]["generated_text"][-1]["content"])