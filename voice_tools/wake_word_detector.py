#!/usr/bin/env python3
"""
Wake word detector for "Оро" using Vosk.
Listens to microphone and triggers when wake word is detected.
"""

import vosk
import sys
import os
import json
import queue
import threading
import time

# Audio settings
SAMPLE_RATE = 16000
CHUNK_SIZE = 4096

# Model path
MODEL_PATH = "models/vosk-model-small-ru-0.22"

# Wake word variants (lowercase for comparison)
WAKE_WORDS = ["оро", "привет оро", "эй оро", "слушай оро"]


class WakeWordDetector:
    def __init__(self):
        self.model = None
        self.recognizer = None
        self.audio_queue = queue.Queue()
        self.is_listening = False
        self.trigger_count = 0
        
    def load_model(self):
        """Load Vosk model."""
        if not os.path.exists(MODEL_PATH):
            print(f"❌ Модель не найдена: {MODEL_PATH}")
            print("Скачайте с: https://alphacephei.com/vosk/models")
            return False
        
        print("📦 Загружаю модель Vosk...")
        self.model = vosk.Model(MODEL_PATH)
        self.recognizer = vosk.KaldiRecognizer(self.model, SAMPLE_RATE)
        self.recognizer.SetWords(True)
        print("✅ Модель загружена")
        return True
    
    def audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio stream."""
        self.audio_queue.put(in_data)
        return (None, 0)
    
    def process_audio(self):
        """Process audio from queue."""
        while self.is_listening:
            try:
                data = self.audio_queue.get(timeout=1)
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "").lower().strip()
                    if text:
                        self.check_wake_word(text)
                else:
                    # Partial result
                    partial = json.loads(self.recognizer.PartialResult())
                    partial_text = partial.get("partial", "").lower()
                    if partial_text:
                        self.check_wake_word(partial_text, partial=True)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ Ошибка обработки: {e}")
    
    def check_wake_word(self, text, partial=False):
        """Check if text contains wake word."""
        prefix = "🎤" if partial else "📝"
        print(f"{prefix} Слышу: '{text}'")
        
        for wake_word in WAKE_WORDS:
            if wake_word in text:
                self.trigger(wake_word, text)
                return True
        return False
    
    def trigger(self, wake_word, full_text):
        """Handle wake word detection."""
        self.trigger_count += 1
        timestamp = time.strftime("%H:%M:%S")
        print(f"\n{'='*50}")
        print(f"🔔 WAKE WORD DETECTED! (#{self.trigger_count})")
        print(f"   Слово: '{wake_word}'")
        print(f"   Текст: '{full_text}'")
        print(f"   Время: {timestamp}")
        print(f"{'='*50}\n")
        
        # Here we can trigger callback, send WebSocket message, etc.
        self.on_wake_word_detected(wake_word, full_text)
    
    def on_wake_word_detected(self, wake_word, full_text):
        """Override this method or pass callback for custom action."""
        pass
    
    def start(self, device_index=None):
        """Start listening for wake word."""
        if not self.load_model():
            return False
        
        try:
            import pyaudio
        except ImportError:
            print("❌ Нужно установить pyaudio:")
            print("   brew install portaudio")
            print("   pip install pyaudio")
            return False
        
        self.is_listening = True
        
        # Start audio processing thread
        processing_thread = threading.Thread(target=self.process_audio)
        processing_thread.daemon = True
        processing_thread.start()
        
        # Open audio stream
        pa = pyaudio.PyAudio()
        
        print(f"\n🎧 Слушаю... Скажи '{' или '.join(WAKE_WORDS)}'")
        print("Нажми Ctrl+C для выхода\n")
        
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
            input_device_index=device_index,
            stream_callback=self.audio_callback
        )
        
        stream.start_stream()
        
        try:
            while self.is_listening:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n👋 Останавливаюсь...")
        finally:
            self.is_listening = False
            stream.stop_stream()
            stream.close()
            pa.terminate()
            processing_thread.join(timeout=2)
        
        return True


def main():
    """CLI entry point."""
    detector = WakeWordDetector()
    detector.start()


if __name__ == "__main__":
    main()
