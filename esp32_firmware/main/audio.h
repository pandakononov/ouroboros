/* Ouroboros ESP32-S3-BOX-3 — Audio subsystem
 * PDM microphone capture via I2S, PCM 16kHz mono 16-bit.
 * Queues chunks for the recording task.
 */
#pragma once

#include <stdint.h>
#include <stddef.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Audio config */
#define AUDIO_SAMPLE_RATE     16000
#define AUDIO_CHUNK_MS        64
#define AUDIO_CHUNK_SAMPLES   ((AUDIO_SAMPLE_RATE * AUDIO_CHUNK_MS) / 1000)
#define AUDIO_CHUNK_BYTES     (AUDIO_CHUNK_SAMPLES * 2)  /* 16-bit = 2 bytes */

/* PDM → PCM conversion settings (internal) */
#define AUDIO_I2S_PORT        I2S_NUM_0
#define AUDIO_I2S_BCK_IO      4    /* GPIO4 — BCK  */
#define AUDIO_I2S_WS_IO       5    /* GPIO5 — WS   */
#define AUDIO_I2S_DIN_IO      6    /* GPIO6 — DIN  */
#define AUDIO_I2S_DOUT_IO     7    /* GPIO7 — DOUT (speaker) */

/* Queue handle — set by audio_init(), used by main.c */
extern QueueHandle_t g_audio_out_queue;

/* Audio chunk (managed — caller must free .data) */
typedef struct {
    uint8_t *data;
    size_t   len;    /* bytes, always AUDIO_CHUNK_BYTES */
    int64_t  ts_us;  /* timestamp */
} audio_chunk_t;

/* Initialise PDM mic + I2S, start capture task.
 * After this call, g_audio_out_queue fills with audio_chunk_t.
 */
esp_err_t audio_init(void);

/* Play PCM buffer through speaker (I2S DAC or PWM).
 * Called by playback task with TTS audio chunks.
 */
esp_err_t audio_play(const uint8_t *pcm_data, size_t pcm_len);

/* Stop capture and release resources. */
void audio_deinit(void);

/* Reconfigure mic gain (0–100) */
void audio_set_gain(uint8_t gain_pct);

#ifdef __cplusplus
}
#endif
