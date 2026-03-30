/* Ouroboros ESP32-S3-BOX-3 — Energy-based VAD
 * Computes RMS energy of 16-bit mono PCM chunks.
 * Threshold crossing = voice activity detected.
 */
#include <math.h>
#include "wake.h"
#include "esp_log.h"

static const char *TAG = "wake";

/* State */
static volatile int32_t g_threshold = 2000;
static volatile int32_t g_current_rms = 0;

/* Ring buffer for RMS smoothing (5 chunks) */
#define RMS_WINDOW 5
static int32_t g_rms_history[RMS_WINDOW] = {0};
static uint8_t g_rms_idx = 0;

/* RMS → likely voice or silence.
 * Uses smoothing window to avoid flapping.
 */
static bool rms_above_threshold(int32_t rms)
{
    /* Write to history */
    g_rms_history[g_rms_idx % RMS_WINDOW] = rms;
    g_rms_idx++;
    g_current_rms = rms;

    /* Average over window */
    int64_t sum = 0;
    for (int i = 0; i < RMS_WINDOW; i++) {
        sum += g_rms_history[i];
    }
    int32_t avg = (int32_t)(sum / RMS_WINDOW);

    return avg > g_threshold;
}

void wake_init(int32_t threshold)
{
    g_threshold = threshold;
    g_current_rms = 0;
    for (int i = 0; i < RMS_WINDOW; i++) g_rms_history[i] = 0;
    g_rms_idx = 0;
    ESP_LOGI(TAG, "VAD init: threshold=%ld", (long)threshold);
}

bool wake_check_audio(const int16_t *pcm, size_t byte_len)
{
    if (pcm == NULL || byte_len == 0) return false;

    size_t num_samples = byte_len / 2;  /* 16-bit = 2 bytes */
    if (num_samples == 0) return false;

    /* Compute RMS */
    int64_t sum_squares = 0;
    for (size_t i = 0; i < num_samples; i++) {
        int32_t s = (int32_t)pcm[i];
        sum_squares += (int64_t)s * (int64_t)s;
    }
    int64_t mean_squares = sum_squares / (int64_t)num_samples;
    /* Clamp to avoid sqrt of negative (can happen with int overflow) */
    if (mean_squares < 0) mean_squares = 0;
    int32_t rms = (int32_t)sqrt((double)mean_squares);

    return rms_above_threshold(rms);
}

int32_t wake_get_rms(void)
{
    return g_current_rms;
}

void wake_set_threshold(int32_t threshold)
{
    g_threshold = threshold;
    ESP_LOGI(TAG, "VAD threshold updated: %ld", (long)threshold);
}
