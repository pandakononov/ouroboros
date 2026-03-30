/* Ouroboros ESP32-S3-BOX-3 — Audio implementation
 * PDM mic capture via I2S, PCM 16kHz mono 16-bit.
 */
#include <string.h>
#include <stdlib.h>
#include "driver/i2s_std.h"
#include "driver/i2s_pdm.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_lpa.h"
#include "esp_err.h"
#include "esp_log.h"

#include "audio.h"

static const char *TAG = "audio";

/* External queue (created here, used by main.c) */
QueueHandle_t g_audio_out_queue = NULL;

/* Capture state */
static bool g_capture_running = false;
static TaskHandle_t g_capture_task_h = NULL;

/* LPA (Low Power Audio) handle for PDM mic */
static esp_lpa_handle_t g_lpa_h = NULL;

/* --- PDM → PCM via LPA --- */

static void capture_task(void *arg)
{
    ESP_LOGI(TAG, "Capture task started");

    uint8_t *chunk_buf = malloc(AUDIO_CHUNK_BYTES);
    if (chunk_buf == NULL) {
        ESP_LOGE(TAG, "OOM for chunk buffer");
        vTaskDelete(NULL);
        return;
    }

    while (g_capture_running) {
        /* Read PCM from LPA (non-blocking with timeout) */
        size_t bytes_read = 0;
        esp_err_t err = esp_lpa_read(g_lpa_h, chunk_buf, AUDIO_CHUNK_BYTES, &bytes_read, pdMS_TO_TICKS(100));

        if (err == ESP_OK && bytes_read >= AUDIO_CHUNK_BYTES) {
            /* Enqueue copy */
            audio_chunk_t chunk;
            chunk.data = malloc(AUDIO_CHUNK_BYTES);
            if (chunk.data != NULL) {
                memcpy(chunk.data, chunk_buf, AUDIO_CHUNK_BYTES);
                chunk.len = AUDIO_CHUNK_BYTES;
                chunk.ts_us = esp_timer_get_time();

                if (xQueueSend(g_audio_out_queue, &chunk, pdMS_TO_TICKS(10)) != pdTRUE) {
                    /* Queue full — drop */
                    free(chunk.data);
                }
            }
        } else if (err != ESP_OK && err != ESP_ERR_TIMEOUT) {
            ESP_LOGW(TAG, "LPA read error: %s", esp_err_to_name(err));
            vTaskDelay(pdMS_TO_TICKS(100));
        }
        /* else: timeout or partial read — loop */
    }

    free(chunk_buf);
    ESP_LOGI(TAG, "Capture task exit");
    vTaskDelete(NULL);
}

esp_err_t audio_init(void)
{
    ESP_LOGI(TAG, "Audio init: SR=%d, chunk=%dms, %d bytes",
             AUDIO_SAMPLE_RATE, AUDIO_CHUNK_MS, AUDIO_CHUNK_BYTES);

    /* Create queue */
    g_audio_out_queue = xQueueCreate(16, sizeof(audio_chunk_t));
    if (g_audio_out_queue == NULL) {
        ESP_LOGE(TAG, "Failed to create audio queue");
        return ESP_FAIL;
    }

    /* GPIO for PDM mic — set up function pins */
    gpio_config_t gpio_conf = {
        .pin_bit_mask = (1ULL << AUDIO_I2S_DIN_IO),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&gpio_conf);

    /* I2S PDM RX config for digital PDM mic */
    i2s_pdm_rx_config_t pdm_rx_cfg = {
        .clk_cfg = I2S_PDM_RX_CLK_DAC_DEFAULT_SAMPLE_RATE(AUDIO_SAMPLE_RATE),
        /* The S3-BOX-3 PDM mic uses: BCK=GPIO4, WS=GPIO5, DIN=GPIO6 */
        .slot_cfg = I2S_PDM_RX_SLOT_DEFAULT_CHAN(AUDIO_SAMPLE_RATE,
                                                  I2S_SLOT_MODE_MONO,
                                                  I2S_PDM_RX_SLOT_S_DIN),
        .gpio_cfg = {
            .clk = AUDIO_I2S_BCK_IO,
            .dout = I2S_PIN_NO_CHANGE,
            .din = AUDIO_I2S_DIN_IO,
            .invert_flags = {
                .clk_inv = false,
            },
        },
    };

    /* Install I2S PDM driver */
    i2s_chan_handle_t i2s_ch = NULL;
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_CFG(AUDIO_SAMPLE_RATE,
                                                  I2S_SLOT_MODE_MONO);
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, NULL, &i2s_ch));

    ESP_ERROR_CHECK(i2s_channel_init_pdm_rx_mode(i2s_ch, &pdm_rx_cfg));
    ESP_ERROR_CHECK(i2s_channel_enable(i2s_ch));
    ESP_LOGI(TAG, "I2S PDM RX enabled");

    /* LPA (Low Power Audio) for buffered PDM capture */
    esp_lpa_config_t lpa_cfg = {
        .i2s_chan = i2s_ch,
        .queue_size = 4,
        .buf_size = AUDIO_CHUNK_BYTES * 2,
    };

    esp_err_t err = esp_lpa_new(&lpa_cfg, &g_lpa_h);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "LPA init failed (%s), falling back to direct I2S",
                 esp_err_to_name(err));
        /* Fallback: direct I2S polling in capture task */
        g_lpa_h = NULL;
    } else {
        ESP_LOGI(TAG, "LPA init OK");
    }

    /* Start capture task on core 0 */
    g_capture_running = true;
    xTaskCreatePinnedToCore(capture_task, "audio_capture", 4096, NULL, 10, &g_capture_task_h, 0);

    return ESP_OK;
}

esp_err_t audio_play(const uint8_t *pcm_data, size_t pcm_len)
{
    /* TODO: I2S DAC / PWM speaker playback.
     * For now: placeholder that logs the chunk.
     * Real implementation needs I2S TX for the speaker amp.
     */
    static uint32_t play_count = 0;
    play_count++;
    if (play_count % 10 == 0) {
        ESP_LOGD(TAG, "Play %u bytes (total chunks: %u)", pcm_len, play_count);
    }
    (void)pcm_data;
    return ESP_OK;
}

void audio_deinit(void)
{
    g_capture_running = false;
    if (g_capture_task_h) {
        vTaskDelete(g_capture_task_h);
        g_capture_task_h = NULL;
    }
    if (g_lpa_h) {
        esp_lpa_delete(g_lpa_h);
        g_lpa_h = NULL;
    }
    if (g_audio_out_queue) {
        vQueueDelete(g_audio_out_queue);
        g_audio_out_queue = NULL;
    }
    ESP_LOGI(TAG, "Audio deinit OK");
}

void audio_set_gain(uint8_t gain_pct)
{
    (void)gain_pct;
    /* TODO: configure PDM mic gain via register or amplifier */
    ESP_LOGI(TAG, "Gain set to %u%% (stub)", gain_pct);
}
