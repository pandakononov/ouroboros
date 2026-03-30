/* Ouroboros ESP32-S3-BOX-3 Voice Client
 * app_main() — entry point, orchestrates all subsystems
 */
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_lpa.h"
#include "nvs_flash.h"
#include "esp_wifi.h"
#include "esp_netif.h"

#include "audio.h"
#include "ws.h"
#include "wake.h"
#include "msg_protocol.h"

static const char *TAG = "ouroboros_main";

/* Global voice state shared across tasks */
typedef struct {
    volatile bool ws_connected;
    volatile bool recording;
    volatile bool playing;
    volatile bool shutdown_requested;
} voice_state_t;

static voice_state_t g_state = {
    .ws_connected = false,
    .recording = false,
    .playing = false,
    .shutdown_requested = false,
};

static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                                int32_t event_id, void *event_data)
{
    if (event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "WiFi disconnected, reconnecting...");
        esp_wifi_connect();
    } else if (event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "Got IP: " IPSTR, IP2STR(&event->ip_info.ip));
    }
}

static esp_err_t init_wifi(void)
{
    ESP_LOGI(TAG, "WiFi init...");

    ESP_ERROR_CHECK(esp_netif_init());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                                &wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                                &wifi_event_handler, NULL));

    wifi_config_t wifi_config = {0};
    strncpy((char *)wifi_config.sta.ssid, CONFIG_OUROBOROS_WIFI_SSID, sizeof(wifi_config.sta.ssid));
    strncpy((char *)wifi_config.sta.password, CONFIG_OUROBOROS_WIFI_PASSWORD, sizeof(wifi_config.sta.password));
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "WiFi started as station, SSID: %s", CONFIG_OUROBOROS_WIFI_SSID);
    return ESP_OK;
}

/* --- Audio pipeline tasks --- */

static void recording_task(void *arg)
{
    voice_state_t *state = (voice_state_t *)arg;
    audio_chunk_t chunk;
    uint32_t silence_count = 0;
    uint32_t total_chunks = 0;

    ESP_LOGI(TAG, "Recording task started (SR=%d, chunk=%dms)",
             AUDIO_SAMPLE_RATE, AUDIO_CHUNK_MS);

    while (!state->shutdown_requested) {
        /* Block until chunk is ready */
        if (xQueueReceive(g_audio_out_queue, &chunk, portMAX_DELAY) != pdTRUE) {
            continue;
        }

        if (!state->ws_connected) {
            /* Drop audio if not connected */
            if (chunk.data != NULL) free(chunk.data);
            continue;
        }

        /* Energy VAD — check if chunk has voice */
        bool has_voice = wake_check_audio(chunk.data, chunk.len);

        if (has_voice) {
            silence_count = 0;
            state->recording = true;
            total_chunks++;

            /* Send AUDIO message */
            if (ws_send_audio(chunk.data, chunk.len) != ESP_OK) {
                ESP_LOGW(TAG, "Failed to send audio chunk");
            }

            /* Send WAKE on first voice chunk */
            if (total_chunks == 1) {
                ws_send_wake();
                ESP_LOGI(TAG, "Voice start detected, streaming...");
            }
        } else {
            silence_count++;
            /* After 5 consecutive silence chunks, stop */
            if (silence_count >= 5 && state->recording) {
                ESP_LOGI(TAG, "Silence, stopping stream (%u chunks sent)", total_chunks);
                state->recording = false;
                total_chunks = 0;
                silence_count = 0;
            }
        }

        if (chunk.data != NULL) free(chunk.data);
    }

    ESP_LOGI(TAG, "Recording task exit");
    vTaskDelete(NULL);
}

static void playback_task(void *arg)
{
    voice_state_t *state = (voice_state_t *)arg;
    uint8_t *buf = NULL;
    size_t buf_len = 0;
    size_t consumed = 0;

    ESP_LOGI(TAG, "Playback task started");

    while (!state->shutdown_requested) {
        /* Wait for TTS audio from WebSocket */
        uint8_t *tts_chunk;
        size_t tts_len;

        if (ws_receive_tts(&tts_chunk, &tts_len, pdMS_TO_TICKS(100)) != ESP_OK) {
            continue;
        }

        if (tts_chunk == NULL || tts_len == 0) {
            /* Timeout or empty */
            continue;
        }

        state->playing = true;

        /* Accumulate chunks until we have enough for DMA */
        uint8_t *new_buf = realloc(buf, buf_len + tts_len);
        if (new_buf == NULL) {
            free(tts_chunk);
            continue;
        }
        buf = new_buf;
        memcpy(buf + buf_len, tts_chunk, tts_len);
        buf_len += tts_len;
        free(tts_chunk);

        /* Play when buffer has at least 64ms of audio */
        size_t min_play = (AUDIO_SAMPLE_RATE * 2 * 64) / 1000; /* 16-bit mono */
        if (buf_len >= min_play || consumed > 0) {
            size_t to_play = buf_len;
            esp_err_t err = audio_play(buf, to_play);
            if (err == ESP_OK) {
                consumed += to_play;
                buf_len = 0;
                free(buf);
                buf = NULL;
            }
        }
    }

    free(buf);
    ESP_LOGI(TAG, "Playback task exit");
    vTaskDelete(NULL);
}

static void heartbeat_task(void *arg)
{
    voice_state_t *state = (voice_state_t *)arg;
    while (!state->shutdown_requested) {
        vTaskDelay(pdMS_TO_TICKS(30000));
        if (state->ws_connected) {
            ws_send_ping();
        }
    }
    vTaskDelete(NULL);
}

void app_main(void)
{
    ESP_LOGI(TAG, "=== Ouroboros Voice Client v1.0 ===");
    ESP_LOGI(TAG, "Device: %s", CONFIG_OUROBOROS_DEVICE_NAME);
    ESP_LOGI(TAG, "Server: %s:%d", CONFIG_OUROBOROS_SERVER_HOST, CONFIG_OUROBOROS_SERVER_PORT);

    /* NVS */
    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_LOGI(TAG, "NVS init OK");

    /* WiFi */
    init_wifi();

    /* Wait for IP */
    ESP_LOGI(TAG, "Waiting for IP...");
    vTaskDelay(pdMS_TO_TICKS(2000));

    /* Audio init */
    ESP_ERROR_CHECK(audio_init());
    ESP_LOGI(TAG, "Audio init OK");

    /* Wake word / VAD init */
    wake_init(CONFIG_OUROBOROS_WAKE_THRESHOLD);
    ESP_LOGI(TAG, "Wake/VAD init OK (threshold=%d)", CONFIG_OUROBOROS_WAKE_THRESHOLD);

    /* WebSocket */
    char ws_url[128];
    snprintf(ws_url, sizeof(ws_url), "ws://%s:%d/voice/stream",
             CONFIG_OUROBOROS_SERVER_HOST, CONFIG_OUROBOROS_SERVER_PORT);

    if (ws_connect(ws_url, &g_state) != ESP_OK) {
        ESP_LOGE(TAG, "WebSocket connect failed!");
    } else {
        g_state.ws_connected = true;
        ESP_LOGI(TAG, "WebSocket connected to %s", ws_url);
    }

    /* Spawn tasks */
    xTaskCreatePinnedToCore(recording_task, "recording", 4096, &g_state, 5, NULL, 0);
    xTaskCreatePinnedToCore(playback_task,   "playback",   4096, &g_state, 4, NULL, 1);
    xTaskCreatePinnedToCore(heartbeat_task,   "heartbeat",  2048, &g_state, 1, NULL, 1);

    /* Main loop — monitor state */
    uint32_t loop = 0;
    while (!g_state.shutdown_requested) {
        vTaskDelay(pdMS_TO_TICKS(5000));
        loop++;
        ESP_LOGD(TAG, "[loop %u] connected=%d recording=%d playing=%d "
                   "audio_q=%u ws_q=%u",
                 loop, g_state.ws_connected, g_state.recording, g_state.playing,
                 uxQueueMessagesWaiting(g_audio_out_queue),
                 uxQueueMessagesWaiting(g_ws_out_queue));
    }

    ESP_LOGI(TAG, "Shutdown...");
    g_state.shutdown_requested = true;
    ws_disconnect();
    audio_deinit();
}
