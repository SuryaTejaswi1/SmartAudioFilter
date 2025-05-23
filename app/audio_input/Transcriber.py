import os
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.logger import logger
from utils.paths import AUDIO_FILES_DIR, TEMP_DIR, LOG_FILE,AUDIO_DATA_DIR
from utils.helpers import format_time
import whisper

class AudioTranscriber:
    def __init__(self, model_size: str = "base"):
        try:
            self.model = whisper.load_model(model_size)
            logger.info(f"Whisper model '{model_size}' loaded.")
        except Exception as e:
            logger.error(f"Unable to load Whisper model: {e}")
            self.model = None

        self.segments_with_confidence: list[dict] = []
        self.transcription_file: str | None = None

    def transcribe_audio(self, filepath: str,
                         save_directory=AUDIO_DATA_DIR) -> Path | None:

        if not self.model:
            logger.error("ASR model not loaded.")
            return None
        if not os.path.exists(filepath):
            logger.error(f"Audio file not found: {filepath}")
            return None

        try:
            logger.info(f"Transcribing: {filepath}")
            result = self.model.transcribe(str(filepath), beam_size=5, word_timestamps=True, verbose=False)
            segments = result.get("segments", [])
            lang = result.get("language", "unknown")

            if not segments:
                logger.warning("No speech detected in audio.")
                return None

            self.segments_with_confidence.clear()
            for seg in segments:
                self.segments_with_confidence.append({
                    "start": format_time(seg["start"]),
                    "end": format_time(seg["end"]),
                    "text": seg["text"].strip(),
                    "confidence": round(self._segment_conf(seg), 4),
                })

            base = os.path.splitext(os.path.basename(filepath))[0]
            os.makedirs(save_directory, exist_ok=True)
            json_path = save_directory / f"{base}.json"
            self.transcription_file = str(json_path)

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump({
                    "file": str(filepath),
                    "language": lang,
                    "language_warning": {
                        "triggered": lang != "en",
                        "severity": "Warning" if lang != "en" else "None",
                        "message": f"Non-English language detected ({lang})" if lang != "en" else ""
                    },
                    "segments": self.segments_with_confidence,
                    "raw_text": " ".join(seg["text"].strip() for seg in segments)
                }, f, indent=4, ensure_ascii=False)

            logger.info(f"Transcription saved: {json_path}")
            return json_path

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None

    @staticmethod
    def _segment_conf(segment) -> float:
        if "words" in segment:
            probs = [w.get("probability", 0.75) for w in segment["words"] if isinstance(w, dict)]
            return sum(probs) / len(probs) if probs else 0.75
        return 0.75
