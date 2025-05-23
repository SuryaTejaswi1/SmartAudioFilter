from app.audio_input.Audio_Recording import AudioInputManager
from app.audio_input.Transcriber import AudioTranscriber
from utils.helpers import convert_mp4_to_mp3
from app.text_input.llm_handler import enrich_and_redact_segments,extract_timestamp_from_filename
from utils.paths import AUDIO_FILES_DIR, OUTPUT_DIR
from utils.logger import logger
from utils.helpers import generate_segment_audit_pdf
from utils.helpers import generate_pdf
import json
import re
from pathlib import Path
import argparse

def main(args):
    audio_manager = AudioInputManager()

    # Step 1: Get Audio
    if args.use_file:
        audio_path = audio_manager.accept_pre_recorded_file(args.use_file)
    else:
        audio_manager.start_recording()
        input("Recording... Press Enter to stop.\n")
        audio_path = audio_manager.stop_recording()

    if not audio_path:
        logger.error("No audio file to process.")
        return

    # Step 2: Transcribe
    transcriber = AudioTranscriber(args.model_size)
    transcription_text = transcriber.transcribe_audio(str(audio_path))
    transcript_path = Path(transcriber.transcription_file)
    if not transcript_path.exists():
        logger.error("Transcription failed or file not created.")
        return

    # Step 3: Classify + Redact
    enrich_and_redact_segments(transcript_path, args.topics)

    # Step 4: Optional PDF
    if args.audit_pdf:
        timestamp = extract_timestamp_from_filename(transcript_path.name)
        redacted_json = OUTPUT_DIR / f"redacted_transcript_{timestamp}.json"
        audit_pdf = OUTPUT_DIR / f"audit_report_{timestamp}.pdf"
        generate_segment_audit_pdf(redacted_json, audit_pdf)

    logger.info("Pipeline completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio Privacy Pipeline")
    parser.add_argument("--use-file", type=str, help="Path to a pre-recorded audio file")
    parser.add_argument("--topics", nargs="+", default=["harassment", "confidential", "salary", "mental health"], help="Sensitive topics to scan for")
    parser.add_argument("--model-size", type=str, default="base", help="Whisper model size")
    parser.add_argument("--audit-pdf", action="store_true", help="Generate audit PDF report")

    args = parser.parse_args()
    main(args)