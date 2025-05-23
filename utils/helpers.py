from fpdf import FPDF
import ffmpeg
import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.logger import logger
from utils.paths import AUDIO_FILES_DIR, TEMP_DIR, LOG_FILE

def format_time(seconds):
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{minutes:02}:{secs:02}.{millis:03}"

#Utility to generate PDF from text
def generate_pdf(text: str, output_path: Path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    for line in text.splitlines():
        pdf.multi_cell(0, 10, line)
    pdf.output(str(output_path))

# Utility to convert mp4 to mp3
def convert_mp4_to_mp3(input_path: Path, output_path: Path):
    try:
        ffmpeg.input(str(input_path)).output(str(output_path), format='mp3', acodec='libmp3lame').run(overwrite_output=True, quiet=True)
        return output_path
    except Exception as e:
        logger.error(f"FFmpeg conversion failed: {e}")
        return None

# Generate audit PDF from classified JSON
def generate_segment_audit_pdf(json_path: Path, output_pdf: Path):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        segments = data.get("segments", [])

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=11)
        pdf.set_text_color(0)

        pdf.multi_cell(0, 10, f"Transcript File: {data.get('file', 'N/A')}\n\n")
        for seg in segments:
            start = seg.get("start", "")
            end = seg.get("end", "")
            text = seg.get("text", "")
            conf = seg.get("confidence", 0)
            sens = seg.get("sensitivity", "Unlabeled")
            rationale = seg.get("rationale", "")

            flag = {"Safe": "✅", "Warning": "⚠️", "Critical": "❗"}.get(sens, "")
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 10, f"[{start} - {end}] {flag} {sens} (Confidence: {conf:.2f})", ln=True)
            pdf.set_font("Arial", size=11)
            pdf.multi_cell(0, 10, f"Text: {text}")
            if rationale:
                pdf.set_text_color(100, 0, 0)
                pdf.multi_cell(0, 10, f"Reason: {rationale}\n")
                pdf.set_text_color(0)
            pdf.ln(1)

        pdf.output(str(output_pdf))
    except Exception as e:
        logger.error(f"Failed to generate segment audit PDF: {e}")
