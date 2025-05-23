import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from datetime import datetime
import shutil
import threading
import os
import re
import json
import subprocess
import platform

from app.audio_input.Audio_Recording import AudioInputManager
from app.audio_input.Transcriber import AudioTranscriber
from utils.helpers import convert_mp4_to_mp3
from app.text_input.llm_handler import enrich_and_redact_segments
from utils.paths import AUDIO_FILES_DIR, OUTPUT_DIR
from utils.logger import logger

class SmartRedactorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Audio Privacy Filter")
        self.recorder = AudioInputManager(base_directory=AUDIO_FILES_DIR)
        self.transcriber = AudioTranscriber()
        self.audio_path = None
        self.is_recording = False

        self.build_ui()

    def build_ui(self):
        self.file_label = tk.Label(self.root, text="1. Choose Audio File (.mp3, .wav, .mp4)")
        self.file_label.pack()
        tk.Button(self.root, text="Browse File", command=self.browse_file).pack()

        self.topic_label = tk.Label(self.root, text="2. Enter Sensitive Topics (comma-separated)")
        self.topic_label.pack()
        self.topic_entry = tk.Entry(self.root, width=60)
        self.topic_entry.insert(0, "salary, nda, mental health")
        self.topic_entry.pack(pady=5)

        self.record_button = tk.Button(self.root, text="🎙️ Start Recording", command=self.start_recording)
        self.record_button.pack(pady=5)

        self.stop_button = tk.Button(self.root, text="🛑 Stop Recording", command=self.stop_recording, state=tk.DISABLED)
        self.stop_button.pack(pady=2)

        tk.Button(self.root, text="🔍 Analyze and Redact", command=self.run_pipeline).pack(pady=10)

        self.output = ScrolledText(self.root, height=20, width=100)
        self.output.pack()

    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav *.mp4")])
        if file_path:
            self.audio_path = Path(file_path)
            self.output.insert(tk.END, f"Selected file: {self.audio_path.name}\n")

    def start_recording(self):
        def _record():
            try:
                self.output.insert(tk.END, "Recording... Speak now.\n")
                self.recorder.start_recording()
                self.is_recording = True
                self.record_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.NORMAL)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to start recording: {e}")
        threading.Thread(target=_record).start()

    def stop_recording(self):
        if not self.is_recording:
            return

        raw_path = self.recorder.stop_recording()
        self.is_recording = False
        self.record_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

        if raw_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            saved_path = AUDIO_FILES_DIR / f"recorded_{timestamp}.wav"
            shutil.copy(raw_path, saved_path)
            self.audio_path = saved_path
            self.output.insert(tk.END, f"Recording saved: {saved_path.name}\n")
        else:
            self.output.insert(tk.END, "No audio recorded.\n")

    def open_file(self, path):
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.call(["open", path])
            else:
                subprocess.call(["xdg-open", path])
        except Exception as e:
            self.output.insert(tk.END, f"Failed to open file {path}: {e}\n")

    def run_pipeline(self):
        if not self.audio_path:
            messagebox.showerror("No File", "Please upload or record an audio file first.")
            return

        topics = [t.strip() for t in self.topic_entry.get().split(",") if t.strip()]
        file_ext = self.audio_path.suffix.lower()

        if file_ext == ".mp4":
            mp3_path = self.audio_path.with_suffix(".mp3")
            self.audio_path = convert_mp4_to_mp3(self.audio_path, mp3_path)

        self.output.insert(tk.END, "\nTranscribing...\n")
        transcript_path = self.transcriber.transcribe_audio(str(self.audio_path), save_directory=AUDIO_FILES_DIR)

        if not transcript_path or not Path(transcript_path).exists():
            self.output.insert(tk.END, "Transcription failed.\n")
            return

        self.output.insert(tk.END, "LLM Model is Running...\n")
        enrich_and_redact_segments(transcript_path, topics)

        match = re.search(r'(\d{8}_\d{6})', str(transcript_path))
        timestamp = match.group(1) if match else datetime.now().strftime('%Y%m%d_%H%M%S')

        self.output.insert(tk.END, "Generating output...\n")
        full_json = OUTPUT_DIR / f"classified_transcript_{timestamp}.json"
        redacted_txt = OUTPUT_DIR / f"redacted_text_{timestamp}.txt"
        summary_txt = OUTPUT_DIR / f"privacy_report_{timestamp}.txt"

        self.output.insert(tk.END, f"\n✅ Analysis complete. Files saved in: {OUTPUT_DIR}\n")
        found_any = False
        for file in [full_json, redacted_txt, summary_txt]:
            if file.exists():
                self.output.insert(tk.END, f"- {file.name}\n")
                btn = tk.Button(self.root, text=f"Open {file.name}", command=lambda f=file: self.open_file(f))
                btn.pack()
                found_any = True

        if not found_any:
            self.output.insert(tk.END, "No output files found. Check processing steps.\n")

if __name__ == "__main__":
    root = tk.Tk()
    app = SmartRedactorApp(root)
    root.mainloop()