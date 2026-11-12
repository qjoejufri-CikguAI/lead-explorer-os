import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Senarai model untuk cascading (cuba satu demi satu jika gagal)
MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-4-26b-a4b-it:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
]

_client_cache = {}


def get_client(model_name):
    """Dapatkan atau cipta OpenAI client untuk model tertentu."""
    if model_name not in _client_cache:
        _client_cache[model_name] = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )
    return _client_cache[model_name]


def generate_smart_search_queries(goal: str):
    """
    Hasilkan 5 keyword carian yang realistikal untuk pembeli di Malaysia
    menggunakan OpenRouter LLM dengan model cascading.
    """
    if not OPENROUTER_API_KEY:
        print("[ERROR] OPENROUTER_API_KEY tidak didapati dalam .env")
    # --- Coba setiap model dalam senarai (model cascading) ---
    for model in MODELS:
        print(f"[INFO] Cuba model: {model}")
        try:
            client = get_client(model)

            system_prompt = (
                "You are an expert Facebook Marketplace scraper. "
                "Generate 5 highly realistic search queries that a human buyer in Malaysia "
                "would type in Facebook groups to find [GOAL]. "
                "Use local Malay slang (e.g., 'nak cari', 'mencari', 'wanted', 'cari cash') "
                "and return ONLY a JSON list of strings."
            ).replace("[GOAL]", goal)

            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Goal: {goal}"},
                ],
                temperature=0.7,
                max_tokens=200,
            )

            content = completion.choices[0].message.content.strip()
            print(f"[DEBUG] Raw response dari {model}: {content}")

            # Coba parse JSON
            try:
                queries = json.loads(content)
                if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
                    print(f"[INFO] Model {model} berjaya. Dapat {len(queries)} keyword.")
                    return queries[:5]
            except json.JSONDecodeError:
                pass

            # Fallback: extract strings manually dari text
            import re
            strings = re.findall(r'"([^"]+)"', content)
            if strings:
                print(f"[INFO] Model {model} berjaya (via regex). Dapat {len(strings)} keyword.")
                return strings[:5]

        except Exception as e:
            print(f"[WARN] Model {model} gagal: {e}. Cuba model seterusnya...")
            continue

    # --- Jika SEMUA model gagal, guna fallback manual ---
    print("[WARN] Semua AI gagal. Menggunakan fallback manual.")
    return [
        f"nak beli {goal}",
        f"cari {goal}",
        f"wanted {goal}",
        f"survey {goal}",
        f"pm {goal}"
    ]


if __name__ == "__main__":
    goal = "Proton X50 di Johor"
    queries = generate_smart_search_queries(goal)
    print(f"\n[INFO] Goal: {goal}")
    print(f"[INFO] Hasil ({len(queries)} keyword):")
    for i, q in enumerate(queries, 1):
        print(f"  {i}. {q}")
