# WebSocket Relay Draft (Mac Studio)

## Goal
Minimal Python server that:
1. Accepts WebSocket connections from ESP32-S3-BOX-3
2. Receives PCM audio clips (16-bit, 16kHz, mono)
3. Runs STT (Whisper.cpp)
4. Generates LLM response
5. Runs TTS (Kokoro/Piper)
6. Sends audio back over WebSocket

## Tech stack
- `websockets` или `fastapi` + `uvicorn` (WebSocket support)
- `whisper-cpp` (Python bindings) или CLI
- `kokoro` или `piper` для TTS
- LLM — existing Ouroboros loop (already integrated)

## File structure (future)
```
voice_interface/
  relay.py           # WebSocket server
  stt.py             # Whisper wrapper
  tts.py             # Kokoro/Piper wrapper
  config.py          # Settings (model paths, latency targets)
```

## Latency budget
- WebSocket recv: <10ms
- STT: 30-50ms (Whisper.cpp tiny-ru)
- LLM: 200-400ms
- TTS: 50-150ms (Piper faster, Kokoro more natural)
- WebSocket send: <10ms
- **Total target: <2s**

## TODO
- Test Whisper.cpp on Mac Studio
- Test Kokoro/Piper installation
- Write relay.py skeleton
- Add metrics logging (per-step latency)
