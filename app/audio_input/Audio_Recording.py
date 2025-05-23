import pyaudio
import wave
import threading
import shutil
from datetime import datetime

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))  # Adds project root to sys.path

from utils.logger import logger
from utils.paths import AUDIO_FILES_DIR, TEMP_DIR, LOG_FILE

class AudioInputManager:
    def __init__(self, base_directory: Path = None):
        self.base_directory = base_directory or AUDIO_FILES_DIR
        self.base_directory.mkdir(parents=True, exist_ok=True)

        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.recording = False
        self.filepath = None
        logger.info(f"AudioInputManager initialized at: {self.base_directory}")

    def _get_timestamped_filename(self, prefix="audio", ext=".wav"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.base_directory / f"{prefix}_{timestamp}{ext}"

    def start_recording(self):
        self.frames = []
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                input=True,

                frames_per_buffer=1024,
            )
            self.recording = True
            self.thread = threading.Thread(target=self._record)
            self.thread.start()
            logger.info("Recording started.")
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            raise

    def _record(self):
        while self.recording:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                if data:
                    self.frames.append(data)
            except Exception as e:
                logger.error(f"Error during recording: {e}")
                break

    def stop_recording(self):
        self.recording = False
        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        if not self.frames:
            logger.warning("No audio frames captured.")
            return None

        self.filepath = self._get_timestamped_filename()
        self._save_wav(self.filepath)
        logger.info(f"Recording saved: {self.filepath.name}")
        return self.filepath

    def _save_wav(self, path):
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(44100)
            wf.writeframes(b"".join(self.frames))

    def accept_pre_recorded_file(self, input_path):
        input_path = Path(input_path)
        if not input_path.exists():
            logger.error(f"File not found: {input_path}")
            return None

        dest_path = self._get_timestamped_filename(prefix="prerecorded")
        shutil.copy(input_path, dest_path)
        logger.info(f"Pre-recorded file copied: {dest_path.name}")
        return dest_path

    def cleanup(self):
        self.audio.terminate()
        logger.info("Audio interface terminated.")
