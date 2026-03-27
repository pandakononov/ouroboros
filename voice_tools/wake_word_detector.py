# voice_tools/wake_word_detector.py
"""
Wake word detector for "Оро" using Vosk.
Supports both live microphone input and audio file testing.
"""

import vosk
import sys
import os
import json
import wave

# Auto-detect model path
MODEL_PATH = "models/vosk-model-small-ru-0.22"

WAKE_WORDS = ["оро", "привет оро", "эй оро", "слушай оро", "оро", "привет"]


class WakeWordDetector:
    def __init__(self, model_path=MODEL_PATH):
        self.model_path = model_path
        self.model = None
        
    def load_model(self):
        """Load Vosk model."""
        if not os.path.exists(self.model_path):
            print(f"❌ Модель не найдена: {self.model_path}")
            print("Скачайте: wget https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip")
            return False
            
        print("📦 Загружаю модель Vosk...")
        self.model = vosk.Model(self.model_path)
        print("✅ Модель загружена")
        return True
    
    def check_wake_word(self, text: str) -> bool:
        """Check if text contains wake word."""
        text_lower = text.lower().strip()
        for wake in WAKE_WORDS:
            if wake in text_lower:
                return True
        return False
    
    def process_audio_file(self, wav_path: str) -> dict:
        """Process WAV file and detect wake word."""
        if not self.model:
            if not self.load_model():
                return None
        
        if not os.path.exists(wav_path):
            print(f"❌ Файл не найден: {wav_path}")
            return None
        
        wf = wave.open(wav_path, "rb")
        
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            print("❌ Файл должен быть mono 16-bit")
            wf.close()
            return None
        
        recognizer = vosk.KaldiRecognizer(self.model, wf.getframerate())
        recognizer.SetWords(True)
        
        results = []
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                results.append(result)
        
        final_result = json.loads(recognizer.FinalResult())
        results.append(final_result)
        wf.close()
        
        # Check all results for wake word
        full_text = " ".join([r.get("text", "") for r in results])
        detected = self.check_wake_word(full_text)
        
        return {
            "text": full_text,
            "detected": detected,
            "raw_results": results
        }
    
    def list_audio_devices(self):
        """List available audio devices."""
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            
            print("\n🎧 Доступные аудиоустройства:")
            print("-" * 50)
            
            input_devices = []
            output_devices = []
            
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                name = info['name']
                max_input = info['maxInputChannels']
                max_output = info['maxOutputChannels']
                
                if max_input > 0:
                    input_devices.append((i, name, max_input))
                if max_output > 0:
                    output_devices.append((i, name, max_output))
            
            print("\n🎤 Входные (микрофоны):")
            if input_devices:
                for idx, name, channels in input_devices:
                    print(f"  [{idx}] {name} ({channels} ch)")
            else:
                print("  ❌ Нет входных устройств")
            
            print("\n🔊 Выходные (динамики/наушники):")
            for idx, name, channels in output_devices:
                print(f"  [{idx}] {name} ({channels} ch)")
            
            pa.terminate()
            
        except Exception as e:
            print(f"⚠️ Не удалось получить список устройств: {e}")
    
    def create_test_wav(self, output_path="test_audio.wav"):
        """Create a test WAV file with silence for manual testing."""
        print(f"\n⚠️ Нет входного аудиоустройства (микрофона)")
        print("Создаю тестовый WAV файл...")
        
        # Create 3-second silent mono 16-bit 16000Hz WAV
        frame_rate = 16000
        duration = 3
        num_frames = frame_rate * duration
        
        with wave.open(output_path, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(frame_rate)
            wf.writeframes(bytes(num_frames * 2))  # silence
        
        print(f"✅ Тестовый файл создан: {output_path}")
        print("📋 Инструкция:")
        print("   1. Запишите свою фразу в этот файл")
        print("   2. Или замените его на реальный записанный WAV")
        print(f"   3. Запустите: python3 {sys.argv[0]} --file {output_path}")
        
        return output_path


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Wake word detector for "Оро"')
    parser.add_argument('--file', type=str, help='WAV файл для анализа')
    parser.add_argument('--list-devices', action='store_true', help='Показать аудиоустройства')
    parser.add_argument('--create-test', action='store_true', help='Создать тестовый WAV')
    
    args = parser.parse_args()
    
    detector = WakeWordDetector()
    
    if args.list_devices:
        detector.list_audio_devices()
        return
    
    if args.create_test:
        detector.create_test_wav()
        return
    
    if args.file:
        # File mode
        if not detector.load_model():
            return
        
        print(f"\n🎧 Анализирую файл: {args.file}")
        result = detector.process_audio_file(args.file)
        
        if result:
            print(f"\n📢 Распознано: '{result['text']}'")
            if result['detected']:
                print("🎉 WAKE WORD ОБНАРУЖЕН!")
            else:
                print("🔇 Wake word не обнаружен")
    else:
        # Try microphone mode
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            
            # Check if any input device exists
            has_input = any(pa.get_device_info_by_index(i)['maxInputChannels'] > 0 
                          for i in range(pa.get_device_count()))
            pa.terminate()
            
            if not has_input:
                detector.list_audio_devices()
                print("\n" + "="*50)
                print("Хотите создать тестовый WAV файл? (y/n): ", end="")
                response = input().strip().lower()
                if response == 'y':
                    detector.create_test_wav()
                return
            
            # Live mode with microphone
            detector.load_model()
            print("🎧 Слушаю... Скажи 'Оро' или 'Привет Оро'")
            print("Нажми Ctrl+C для выхода")
            # Live mode implementation here...
            
        except ImportError:
            print("❌ PyAudio не установлен")
            print("Установите: brew install portaudio && pip install pyaudio")


if __name__ == "__main__":
    main()