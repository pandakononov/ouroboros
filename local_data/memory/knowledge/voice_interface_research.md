# Voice Interface Research (Research Notes)

## Russian (RU)
**Цель:** Создать полностью автономный голосовой интерфейс на ESP32‑S3‑BOX‑3 с конечной задержкой < 2 секунд, используя только локальные ресурсы (без облака).

**Ключевые компоненты**
1. **Detecting wake‑word** – кастомное слово «Оро» на ESP32‑S3 (Porcupine / Vosk‑keyword).
2. **Захват аудио** – запись короткого фрагмента (≈ 1 сек) через I²S‑модуль.
3. **STT (Speech‑to‑Text)** – локальный ASR:
   - Whisper‑cpp (tiny‑ru) ≈ 30‑50 мс/фрагмент.
   - Vosk‑model‑small‑ru‑0.22 ≈ 40‑60 мс.
4. **LLM‑генерация ответа** – локальный inference (например, llama.cpp / gpt‑4‑all‑q5\_0) → текстовый ответ.
5. **TTS (Text‑to‑Speech)** – синтез речи:
   - Kokoro ≈ 150 мс на 2‑секундный фрагмент.
   - Piper ≈ 50‑80 мс, ультрабыстрый.
6. **Отправка аудио обратно** – WebSocket over LAN к ESP32, воспроизведение через динамик.

**Метрики**
- Общая задержка: 1 – 1.5 с (цель ≤ 2 с).
- Потребление RAM/CPU на ESP32: < 150 КБ RAM, < 30 % CPU.
- Лицензии: Porcupine – Apache 2.0, Whisper‑cpp – MIT, Kokoro – Apache 2.0, Piper – MIT.

**План реализации**
1. Настроить Porcupine с кастомным модельным файлом «Оро».
2. РеализоватьCapture → WebSocket → Mac‑relay.
3. На Mac‑relay развернуть aiohttp/FastAPI сервер, вызывающий Whisper‑cpp → LLM → Kokoro/TTS → обратно по WebSocket.
4. Тестировать latency, false‑negative rate, error‑recovery.
5. Закрепить в `identity.md` цель «офлайн голосовой диалог с <2 с задержкой».

---

## English (EN)
**Goal:** Build a fully offline voice interaction loop on ESP32‑S3‑BOX‑3 with end‑to‑end latency < 2 seconds, using only local resources (no cloud).

**Key components**
1. **Wake‑word detection** – custom keyword “Oro” on ESP32‑S3 (Picovoice Porcupine or Vosk keyword spotting).
2. **Audio capture** – record a short clip (~1 s) via I²S.
3. **STT (Speech‑to‑Text)** – local ASR:
   - Whisper‑cpp (tiny‑ru) ≈ 30‑50 ms per clip.
   - Vosk‑model‑small‑ru‑0.22 ≈ 40‑60 ms.
4. **LLM response generation** – local inference (e.g., llama.cpp / gpt‑4‑all‑q5\_0) → text answer.
5. **TTS (Text‑to‑Speech)** – synthesis:
   - Kokoro ≈ 150 ms for a 2‑second utterance.
   - Piper ≈ 50‑80 ms, ultra‑low latency.
6. **Send audio back** – WebSocket over LAN to ESP32, playback through speaker.

**Metrics**
- Total latency: 1 – 1.5 s (target ≤ 2 s).
- RAM/CPU on ESP32: < 150 KB RAM, < 30 % CPU.
- Licenses: Porcupine – Apache 2.0, Whisper‑cpp – MIT, Kokoro – Apache 2.0, Piper – MIT.

**Implementation plan**
1. Configure Porcupine with a custom “Oro” keyword model.
2. Build Capture → WebSocket → Mac‑relay pipeline.
3. Deploy an aiohttp/FastAPI server on macOS that calls Whisper‑cpp → LLM → Kokoro/TTS → back over WebSocket.
4. Benchmark latency, false‑negative rate, error recovery.
5. Record the objective in `identity.md` as “offline voice conversation with <2 s latency”.

---