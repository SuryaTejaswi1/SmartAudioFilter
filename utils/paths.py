from pathlib import Path

# Project Root (adjust depending on actual location of this file)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Data directories
AUDIO_DATA_DIR = PROJECT_ROOT / "audio_data"
AUDIO_FILES_DIR = AUDIO_DATA_DIR / "audio_files"
TEMP_DIR = PROJECT_ROOT / "temp_uploads"
LOGS_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOGS_DIR / "sessions.txt"
OUTPUT_DIR = PROJECT_ROOT / "Outputs"
# Phrase generation and embeddings
PHRASE_DIR = AUDIO_DATA_DIR / "Embeddings"
PHRASE_BANK_PATH = PHRASE_DIR / "phrase_bank.json"
EMBED_CACHE_PATH = PHRASE_DIR / "phrase_embeddings.json"

# Ollama API URL
OLLAMA_URL = "http://localhost:11434/api/generate"
# Ensure all folders exist
for path in [AUDIO_DATA_DIR, AUDIO_FILES_DIR, TEMP_DIR, LOGS_DIR,PHRASE_DIR,OUTPUT_DIR]:
    path.mkdir(parents=True, exist_ok=True)
