/* Ouroboros ESP32-S3-BOX-3 — WebSocket client wrapper
 * Wraps esp_websocket_client, implements Ouroboros binary protocol.
 */
#pragma once

#include <stdint.h>
#include <stddef.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#ifdef __cplusplus
extern "C" {
#endif

/* WebSocket queue for outgoing raw audio (filled by recording task) */
extern QueueHandle_t g_ws_out_queue;

/* Connect to voice server.
 * url format: ws://HOST:PORT/voice/stream
 * state: pointer to app's voice_state_t (updated on connect/disconnect)
 */
esp_err_t ws_connect(const char *url, void *state);

/* Disconnect */
void ws_disconnect(void);

/* Send AUDIO chunk (PCM 16k mono 16-bit) */
esp_err_t ws_send_audio(const uint8_t *pcm_data, size_t pcm_len);

/* Send WAKE message (voice activity start) */
esp_err_t ws_send_wake(void);

/* Send PING keepalive */
esp_err_t ws_send_ping(void);

/* Receive TTS audio chunk (blocks up to timeout_ms).
 * Returns ESP_OK with chunk (caller must free) or ESP_ERR_TIMEOUT.
 */
esp_err_t ws_receive_tts(uint8_t **out_data, size_t *out_len,
                          TickType_t timeout_ticks);

/* Check if connected */
bool ws_is_connected(void);

#ifdef __cplusplus
}
#endif
