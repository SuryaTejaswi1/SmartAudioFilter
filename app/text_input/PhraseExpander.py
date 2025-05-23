import requests
import json
from sentence_transformers import SentenceTransformer
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils.logger import logger
from utils.paths import PHRASE_DIR,PHRASE_BANK_PATH, EMBED_CACHE_PATH, OLLAMA_URL
from utils.json_io import load_json, save_json

# Ensure Embeddings directory exists
PHRASE_DIR.parent.mkdir(parents=True, exist_ok=True)

model = SentenceTransformer("all-MiniLM-L6-v2")

def load_phrase_bank():
    return load_json(PHRASE_BANK_PATH, default={})

import json
import requests
from utils.logger import logger
from utils.paths import OLLAMA_URL


def make_prompt(topic: str) -> str:
    return f"""
You are assisting with workplace conversation monitoring.

The goal is to generate realistic example sentences related to the sensitive topic: "{topic}". These sentences will help identify and flag speech in real conversations.

Each sentence should reflect how this topic might naturally arise in a workplace.

Categorize them like this:
- Safe: Professional, compliant mentions
- Warning: Mildly sensitive, questionable
- Critical: Confidential, risky, or violating policy

You MUST respond with ONLY a valid JSON object — no explanations, markdown, or formatting.

Format:
{{
  "Safe": ["sentence 1", "sentence 2", "sentence 3"],
  "Warning": ["sentence 4", "sentence 5", "sentence 6"],
  "Critical": ["sentence 7", "sentence 8", "sentence 9"]
}}
"""


def call_ollama(topic: str, retries: int = 2):
    prompt = make_prompt(topic)

    for attempt in range(retries + 1):
        try:
            response = requests.post(OLLAMA_URL, json={"model": "phi", "prompt": prompt, "stream": False})
            if response.status_code != 200:
                logger.error(f" Ollama returned status {response.status_code}: {response.text}")
                continue

            raw = response.json().get("response", "")
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            json_data = raw[json_start:json_end]

            parsed = json.loads(json_data)

            # Validate keys exist
            if all(k in parsed for k in ("Safe", "Warning", "Critical")):
                return parsed
            else:
                raise ValueError("Missing expected keys in response.")

        except Exception as e:
            logger.error(f" Attempt {attempt + 1}: Failed to parse Ollama response for topic '{topic}': {e}")

    # Fallback if all attempts fail
    logger.warning(f"⚠️ Returning empty structure for topic '{topic}' after {retries + 1} attempts.")
    return {"Safe": [], "Warning": [], "Critical": []}


def build_embedding_index(phrase_bank):
    index = {"Safe": [], "Warning": [], "Critical": []}
    for topic, categories in phrase_bank.items():
        for category, phrases in categories.items():
            for phrase in phrases:
                emb = model.encode(phrase, normalize_embeddings=True)
                index[category].append({
                    "phrase": phrase,
                    "embedding": emb.tolist(),
                    "topic": topic,
                    "category": category,
                    "match_score": 0.0
                })
    logger.info(" Built embedding index from phrase bank.")
    return index

def generate_and_embed(user_topics):
    phrase_bank = load_phrase_bank()

    for topic in user_topics:
        if topic not in phrase_bank:
            logger.info(f" Generating phrases for topic: '{topic}'")
            phrase_bank[topic] = call_ollama(topic)
        else:
            logger.info(f" Topic '{topic}' already cached. Skipping generation.")

    save_json(PHRASE_BANK_PATH, phrase_bank)

    embed_index = build_embedding_index(phrase_bank)
    save_json(EMBED_CACHE_PATH, embed_index)

    logger.info(f"Completed generation and embedding for topics: {list(phrase_bank.keys())}")
