import json
import requests
import re
from tqdm import tqdm
from pathlib import Path
from datetime import datetime
from copy import deepcopy
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils.logger import logger
from utils.paths import AUDIO_DATA_DIR, OUTPUT_DIR, OLLAMA_URL

MODEL = "mistral"

def extract_timestamp_from_filename(filename: str) -> str:
    match = re.search(r'(\d{8}_\d{6})', filename)
    return match.group(1) if match else datetime.now().strftime("%Y%m%d_%H%M%S")

def get_classify_prompt(text: str, topics: list[str]) -> str:
    return f"""
You are a workplace text(speech) classifier.

Given this message:
"{text}"

And the following sensitive topics:
{topics}

Classify the message into one of the following:
- Safe: harmless, compliant
- Warning: possibly sensitive, questionable
- Critical: private, policy-violating, or high-risk

Return a JSON object ONLY in this format:
{{
  "sensitivity": "Safe" | "Warning" | "Critical",
  "reason": "short explanation"
}}
"""
def classify_segment(text: str, topics: list[str]) -> dict:
    prompt = get_classify_prompt(text, topics)
    try:
        response = requests.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
        output = response.json().get("response", "")
        json_start = output.find("{")
        json_end = output.rfind("}") + 1
        parsed = json.loads(output[json_start:json_end])
        return {
            "sensitivity": parsed.get("sensitivity", "Unknown"),
            "reason": parsed.get("reason", "No rationale provided.")
        }
    except Exception as e:
        logger.error(f"Classification failed: {text[:40]}... => {e}")
        return {"sensitivity": "Unknown", "reason": f"Parse failure: {e}"}


def get_rephrase_prompt(text: str) -> str:
    return f"""
Rephrase the following workplace sentence to be more neutral, professional, and compliant — without changing its meaning.

Original:
"{text}"

Return ONLY the rewritten sentence.
"""


def rephrase_warning_text(text: str) -> str:
    prompt = get_rephrase_prompt(text)
    try:
        response = requests.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
        return response.json().get("response", "").strip()
    except Exception as e:
        logger.error(f" Rephrase failed: {text[:40]}... => {e}")
        return "[[REDACTED]]"


def redact_or_rephrase_segments(segments: list[dict]) -> tuple[list[dict], list[str]]:
    redacted_lines = []
    counts = {"safe": 0, "warning": 0, "critical": 0}

    for seg in segments:
        label = seg.get("sensitivity", "").lower()

        if label == "critical":
            seg["text"] = "[[REDACTED]]"
            redacted_lines.append(seg["text"])
            counts["critical"] += 1
        elif label == "warning":
            new_text = rephrase_warning_text(seg["text"])
            seg["text"] = new_text
            redacted_lines.append(new_text)
            counts["warning"] += 1
        else:
            redacted_lines.append(seg["text"])
            counts["safe"] += 1

    logger.info(f" Redacted: {counts['critical']}, Rephrased: {counts['warning']}, Safe: {counts['safe']}")
    return segments, redacted_lines

def generate_privacy_report(redacted_segments: list[dict], topics: list[str], timestamp: str):
    total = len(redacted_segments)
    counts = {
        "Safe": sum(1 for s in redacted_segments if s.get("sensitivity") == "Safe"),
        "Warning": sum(1 for s in redacted_segments if s.get("sensitivity") == "Warning"),
        "Critical": sum(1 for s in redacted_segments if s.get("sensitivity") == "Critical")
    }

    rationale_summary = [
        f"- {s.get('rationale', '')}"
        for s in redacted_segments
        if s.get("sensitivity") in ("Warning", "Critical")
    ][:10]  # limit for brevity

    report_text = f""" Privacy Scan Summary — {timestamp}

    Total Segments: {total}
    Safe: {counts['Safe']}
    Rephrased (Warning): {counts['Warning']}
    Redacted (Critical): {counts['Critical']}

    Top Flagged Rationales:
    {chr(10).join(rationale_summary) if rationale_summary else 'None flagged.'}
    """

    out_path = OUTPUT_DIR / f"privacy_report_{timestamp}.txt"
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        logger.info(f" Privacy report saved to: {out_path}")
    except Exception as e:
        logger.error(f" Failed to write privacy report: {e}")

def write_redacted_text_file(lines: list[str], timestamp: str):
    out_path = OUTPUT_DIR / f"redacted_text_{timestamp}.txt"
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line.strip() + "\n")
        logger.info(f" Redacted text saved to: {out_path}")
    except Exception as e:
        logger.error(f" Failed to write redacted text: {e}")


def enrich_and_redact_segments(transcript_path: Path, topics: list[str]):
    logger.info(f" Loading transcript: {transcript_path}")
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f" Failed to load transcript: {e}")
        return

    segments = data.get("segments", [])
    logger.info(f"Classifying {len(segments)} segments with topics: {topics}")

    for seg in tqdm(segments, desc="Classifying"):
        result = classify_segment(seg["text"], topics)
        seg["sensitivity"] = result["sensitivity"]
        seg["rationale"] = result["reason"]

    timestamp = extract_timestamp_from_filename(transcript_path.name)

    full_json_path = OUTPUT_DIR / f"classified_transcript_{timestamp}.json"
    redacted_json_path = OUTPUT_DIR / f"redacted_transcript_{timestamp}.json"

    try:
        with open(full_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f" Full JSON saved to: {full_json_path}")
    except Exception as e:
        logger.error(f" Failed to save classified JSON: {e}")

    redacted_data = deepcopy(data)
    redacted_data["segments"], redacted_lines = redact_or_rephrase_segments(redacted_data["segments"])

    try:
        with open(redacted_json_path, "w", encoding="utf-8") as f:
            json.dump(redacted_data, f, indent=2)
        logger.info(f" Redacted JSON saved to: {redacted_json_path}")
    except Exception as e:
        logger.error(f" Failed to save redacted JSON: {e}")

    write_redacted_text_file(redacted_lines, timestamp)
    generate_privacy_report(redacted_data["segments"], topics, timestamp)
