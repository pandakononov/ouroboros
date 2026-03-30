# Ouroboros Voice Client — ESP32-S3-BOX-3

Прошивка для ESP32-S3-BOX-3: голосовой клиент Ouroboros.
Подключается к `voice_server` на Mac Studio по WebSocket.

## Архитектура

```
ESP32-S3-BOX-3                    Mac Studio
┌──────────────────┐           ┌──────────────────┐
│  PDM Mic (×2)     │   WS     │  voice_server     │
│         ↓         │  binary   │         ↓         │
│  I2S → LPA → PCM  │──────────│→ STT (Whisper)   │
│                   │           │         ↓         │
│  WS client        │           │  LLM (Ouroboros) │
│  (esp_ws_client)  │           │         ↓         │
│         ↑         │  binary   │  Piper TTS → WAV  │
│  I2S DAC → Speaker│←─────────│         ↓         │
└──────────────────┘           └──────────────────┘
```

## Протокол

Binary: `[type 1B][len 4B BE][payload]`

| Type | Dir | Описание |
|------|-----|---------|
| 0x01 AUDIO | ESP→Server | PCM 16kHz mono 16-bit |
| 0x02 STT_RESULT | Server→ESP | JSON `{"text": "...", "conf": 0.95}` |
| 0x03 TTS_AUDIO | Server→ESP | PCM 16kHz mono 16-bit |
| 0x04 WAKE | ESP→Server | Voice activity start |
| 0x05 PING | both | Keepalive |
| 0xFF ERROR | Server→ESP | Error message |

## Структура проекта

```
esp32_firmware/
├── main/
│   ├── main.c           # app_main(), task orchestration
│   ├── audio.c/.h       # PDM capture, I2S playback
│   ├── ws.c/.h          # WebSocket client + binary protocol
│   ├── msg_protocol.h  # Protocol types + helpers
│   ├── wake.c/.h        # Energy VAD (RMS threshold)
│   ├── CMakeLists.txt
│   └── Kconfig.projbuild
└── sdkconfig.defaults
```

## Сборка

### 1. Установка ESP-IDF

```bash
# Linux / macOS
. "$HOME/esp/esp-idf/install.sh"
. "$HOME/esp/esp-idf/export.sh"
```

### 2. Конфигурация

```bash
cd esp32_firmware
idf.py set-target esp32s3
idf.py menuconfig
```

В `menuconfig` → `Ouroboros Voice` задать:
- **WiFi SSID** и **Password**
- **Server host** (IP Mac Studio)
- **VAD threshold** (по умолчанию 2000)

### 3. Сборка и прошивка

```bash
idf.py build
idf.py flash monitor
```

### 4. Подключение ESP32 по USB

```bash
idf.py -p /dev/ttyUSB0 flash monitor
```

Или через Wi-Fi (OTA):
```bash
idf.py app-flash monitor
```

## Конфигурация Kconfig

| Параметр | По умолчанию | Описание |
|----------|-------------|---------|
| `OUROBOROS_WIFI_SSID` | MyNetwork | WiFi SSID |
| `OUROBOROS_WIFI_PASSWORD` | password | WiFi пароль |
| `OUROBOROS_SERVER_HOST` | 192.168.1.100 | IP Mac Studio |
| `OUROBOROS_SERVER_PORT` | 8000 | Порт voice_server |
| `OUROBOROS_DEVICE_NAME` | Ouroboros-BOX | Имя в логах |
| `OUROBOROS_WAKE_THRESHOLD` | 2000 | Порог VAD (RMS, 0-32767) |
| `OUROBOROS_WAKE_TIMEOUT_MS` | 10000 | Макс. длительность записи |

## Статус реализации

| Компонент | Статус | Заметки |
|-----------|--------|---------|
| Audio capture (PDM) | ✅ | esp_lpa + I2S PDM |
| WebSocket binary | ✅ | esp_websocket_client |
| Energy VAD | ✅ | Simple RMS threshold |
| Speaker playback | ⚠️ | Stub — нужен I2S DAC код |
| Wake word "Оро" | 🔜 | tinyML / micro_speech |

## TODOs

- [ ] I2S DAC speaker playback (PCM → I2S TX → amplifier)
- [ ] Wake word detection ("Оро") via TensorFlow Lite Micro
- [ ] Button-based manual trigger fallback
- [ ] LED ring feedback (playing/recording state)
- [ ] Touch screen status display
- [ ] Automatic WiFi provisioning (esp-now или BLE)
