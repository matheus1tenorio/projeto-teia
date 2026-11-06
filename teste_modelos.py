import time

from openai import OpenAI

import config

CANDIDATOS = [
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-nano-3-30b-a3b",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/llama-3.1-nemotron-51b-instruct",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "nvidia/nemotron-4-340b-instruct",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-70b-instruct",
]

client = OpenAI(base_url=config.NVIDIA_BASE_URL, api_key=config.NVIDIA_API_KEY, timeout=60)

print(f"{'modelo':50} resultado")
for modelo in CANDIDATOS:
    t = time.time()
    try:
        r = client.chat.completions.create(
            model=modelo,
            messages=[{"role": "user", "content": "Responda apenas: ok"}],
            max_tokens=200,
            temperature=0,
        )
        texto = (r.choices[0].message.content or "").strip()
        status = f"OK ({time.time() - t:.1f}s) resposta={texto[:30]!r}"
        if not texto:
            status += " [VAZIA: provável modelo de raciocínio]"
    except Exception as e:
        status = f"FALHOU ({type(e).__name__}: {str(e)[:60]})"
    print(f"{modelo:50} {status}")