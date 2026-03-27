# voice_tools/vosk_test.py
import vosk
import sys
import os

MODEL_PATH = "models/vosk-model-small-ru-0.22"

def main():
    print("--- Тест Vosk на Mac Studio ---")
    
    if not os.path.exists(MODEL_PATH):
        print(f"❌ Модель не найдена: {MODEL_PATH}")
        print("Скачай: wget https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip")
        print("Распакуй в папку models/")
        return 1
    
    print(f"✅ Модель найдена: {MODEL_PATH}")
    print("Загружаю...")
    
    try:
        model = vosk.Model(MODEL_PATH)
        print("✅ Модель загружена успешно!")
        
        # Тест распознавания с микрофона или файла
        rec = vosk.KaldiRecognizer(model, 16000)
        print("✅ Распознаватель создан")
        print("\nVosk работает! Можно интегрировать wake-word.")
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())