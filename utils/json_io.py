import json
from pathlib import Path
from utils.logger import logger

def load_json(path: Path, default=None):
    default = default if default is not None else {}

    if not path.exists():
        logger.info(f" File not found: {path}")
        return default

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f" Corrupt JSON in {path}: {e}. Returning default.")
        return default
    except Exception as e:
        logger.error(f" Error reading {path}: {e}")
        return default


def save_json(path: Path, data):
    try:
        with open(path, "w", encoding="utf-8", errors="replace") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f" Saved JSON to: {path}")
    except Exception as e:
        logger.error(f" Failed to write {path}: {e}")
