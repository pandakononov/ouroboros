/* Ouroboros ESP32-S3-BOX-3 — Wake word / VAD
 * Simple energy-based voice activity detection (RMS threshold).
 * Future: tinyML wake word "Оро" via TensorFlow Lite Micro.
 */
#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Initialise VAD with RMS energy threshold.
 * threshold: RMS level 0–32767 (16-bit audio).
 * Higher = less sensitive. ~2000 for quiet room, ~4000 for noisy.
 */
void wake_init(int32_t threshold);

/* Check if audio chunk contains voice.
 * Returns true if RMS energy > threshold.
 * pcm: 16-bit mono PCM samples (native endian)
 * len: number of bytes (must be even)
 */
bool wake_check_audio(const int16_t *pcm, size_t byte_len);

/* Get current RMS level (for tuning / diagnostics) */
int32_t wake_get_rms(void);

/* Update threshold at runtime */
void wake_set_threshold(int32_t threshold);

#ifdef __cplusplus
}
#endif
