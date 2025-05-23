import os
os.environ["STREAMLIT_WATCH_USE_POLLING"] = "true"

import streamlit as st
from pathlib import Path
import re
import json
import shutil
import json
from datetime import datetime
from audio_input.Audio_Recording import AudioInputManager
from audio_input.Transcriber import AudioTranscriber
from text_input.llm_handler import enrich_and_redact_segments
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.logger import logger
from utils.paths import AUDIO_FILES_DIR, LOG_FILE, OUTPUT_DIR,TEMP_DIR
from utils.helpers import generate_pdf, convert_mp4_to_mp3, generate_segment_audit_pdf

# ---------------------------
# App Setup
# ---------------------------
st.set_page_config(page_title="Smart Audio Redactor", layout="wide")
st.title("🔐 Smart Audio Privacy Filter")
st.markdown("Upload a conversation or meeting recording to detect and redact sensitive information based on your topics.")

# ---------------------------
# Session State Defaults
# ---------------------------
if "recorder" not in st.session_state:
    st.session_state.recorder = AudioInputManager(base_directory=AUDIO_FILES_DIR)
if "transcriber" not in st.session_state:
    st.session_state.transcriber = AudioTranscriber()

recorder = st.session_state.recorder
transcriber = st.session_state.transcriber

state = st.session_state
state.setdefault("is_recording", False)
state.setdefault("recorded_path", None)
state.setdefault("transcription_result", "")
state.setdefault("saved_uploaded_path", None)

logger.info("App loaded successfully.")
logger.info("Recorder and Transcriber instantiated.")

# ---------------------------
# Process Function (Reusable)
# ---------------------------

def process_audio_file(input_path, topics,label):
    with st.spinner("Transcribing audio..."):
        transcription_file = state.transcriber.transcribe_audio(input_path, save_directory=AUDIO_FILES_DIR)
    logger.info(f"Transcribing {label} file: {input_path.name}")
    state.transcription_result = transcription_file
    transcription_file = AUDIO_FILES_DIR / f"{input_path.stem}.json"
    if not transcription_file or not Path(transcription_file).exists():
        st.error("Failed to transcribe audio.")
        return

    json_output_path = Path(transcription_file)
    with json_output_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        lang = data.get("language", "unknown").upper()
        st.info(f"🈯 Detected Language: {lang}")
        if data.get("language_warning", {}).get("triggered"):
            st.warning(f"⚠️ {data['language_warning']['message']}")

    enrich_and_redact_segments(json_output_path, topics)

    match = re.search(r'(\d{8}_\d{6})', json_output_path.stem)
    timestamp = match.group(1) if match else "latest"

    redacted_txt = OUTPUT_DIR / f"redacted_text_{timestamp}.txt"
    redacted_pdf = OUTPUT_DIR / f"redacted_text_{timestamp}.pdf"
    report_txt = OUTPUT_DIR / f"privacy_report_{timestamp}.txt"
    report_pdf = OUTPUT_DIR / f"privacy_report_{timestamp}.pdf"
    classified_json = OUTPUT_DIR / f"classified_transcript_{timestamp}.json"
    segment_audit_pdf = OUTPUT_DIR / f"classified_transcript_{timestamp}.pdf"

    if redacted_txt.exists():
        try:
            with open(redacted_txt, "r", encoding="utf-8") as f:
                redacted_content = f.read()
            generate_pdf(redacted_content, redacted_pdf)
        except Exception as e:
            st.error(f"PDF generation failed: {e}")

    if report_txt.exists():
        try:
            with open(report_txt, "r", encoding="utf-8") as f:
                summary_text = f.read()
            generate_pdf(summary_text, report_pdf)
        except Exception as e:
            st.error(f"Report generation failed: {e}")

    if classified_json.exists():
        try:
            generate_segment_audit_pdf(classified_json, segment_audit_pdf)
        except Exception as e:
            st.error(f"Audit log generation failed: {e}")

    st.subheader("📊 Privacy Summary")
    if report_txt.exists():
        for line in summary_text.splitlines():
            if line.startswith("- Redacted"):
                st.error(line)
            elif line.startswith("- Rephrased"):
                st.warning(line)
            elif line.startswith("- Safe"):
                st.success(line)
            else:
                st.write(line)

    st.subheader("⬇️ Download Outputs")
    if redacted_pdf.exists():
        with open(redacted_pdf, "rb") as f:
            st.download_button("📄 Download Redacted Transcript (.pdf)", f, redacted_pdf.name)

    if report_pdf.exists():
        with open(report_pdf, "rb") as f:
            st.download_button("🧠 Download Privacy Summary (.pdf)", f, report_pdf.name)

    if segment_audit_pdf.exists():
        with open(segment_audit_pdf, "rb") as f:
            st.download_button("📋 Download Full Audit Log (.pdf)", f, segment_audit_pdf.name)

# ---------------------------
# Upload Audio/Video
# ---------------------------
uploaded_file = st.file_uploader("Upload Audio/Video (.wav, .mp3, .mp4)", type=["wav", "mp3", "mp4"])
with st.form("topic_input_form"):
    user_topics = st.text_input("Enter comma-separated sensitive topics", "salary, nda, termination")
    submitted = st.form_submit_button("✅ Save Topics")

if submitted:
    st.success("Topics updated.")

if uploaded_file:
    temp_raw = TEMP_DIR / uploaded_file.name
    temp_raw.write_bytes(uploaded_file.getbuffer())
    logger.info(f"File uploaded: {uploaded_file.name}")
    file_ext = temp_raw.suffix.lower()

    st.audio(str(temp_raw))

    if file_ext == ".mp4":
        mp3_path = temp_raw.with_suffix(".mp3")
        converted_path = convert_mp4_to_mp3(temp_raw, mp3_path)
        if not converted_path:
            st.error("Failed to convert MP4 to MP3.")
            st.stop()
        st.success(f"Converted MP4 to MP3: {converted_path.name}")
        temp_path = converted_path
    else:
        temp_path = temp_raw

    st.audio(str(temp_raw))
    # 📥 Register using AudioInputManager
    saved_path = Path(recorder.accept_pre_recorded_file(temp_raw))
    state.saved_uploaded_path = saved_path
    st.success(f"File accepted and ready: {saved_path.name}")

    process_audio_file(saved_path, [t.strip() for t in user_topics.split(",") if t.strip()],label="Uploaded")
    with LOG_FILE.open("a") as log:
        log.write(f"{datetime.now()} - Uploaded : {uploaded_file.name} -> Processed\n")
    shutil.rmtree(TEMP_DIR)
# ---------------------------
# Live Microphone Recording
# ---------------------------
st.header("🎙️ Live Microphone Recording")
col1, col2 = st.columns(2)

with col1:
    if st.button("Start Recording", disabled=state.is_recording):
        try:
            state.recorder.start_recording()
            state.is_recording = True
            logger.info("Live recording started.")
            st.success("Recording started — speak now …")
        except Exception as e:
            st.error(f"Failed to start: {e}")

with col2:
    if st.button("Stop & Transcribe", disabled=not state.is_recording):
        try:
            raw_result = state.recorder.stop_recording()
            state.is_recording = False
            if not raw_result:
                st.warning("No audio recorded.")
                st.stop()
            temp_audio_path = Path(raw_result)
            persistent_path = AUDIO_FILES_DIR / f"recorded_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            shutil.copy(temp_audio_path, persistent_path)
            state.recorded_path = persistent_path
            st.audio(str(persistent_path))
            st.success(f"Recorded audio saved: {persistent_path.name}")

            if st.button("Transcribe & Redact Recording"):
                process_audio_file(persistent_path, [t.strip() for t in user_topics.split(",") if t.strip()])
        except Exception as e:
            st.error(f"Stop/Transcribe failed: {e}")
