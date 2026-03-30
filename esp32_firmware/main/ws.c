/* Ouroboros ESP32-S3-BOX-3 — WebSocket implementation
 * esp_websocket_client + Ouroboros binary protocol.
 */
#include <string.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_websocket_client.h"
#include "esp_log.h"
#include "esp_timer.h"

#include "ws.h"
#include "msg_protocol.h"

/* External queue for incoming WS data → playback task */
QueueHandle_t g_ws_out_queue = NULL;

static const char *TAG = "ws";

/* WebSocket client handle */
static esp_websocket_client_handle_t g_ws_client = NULL;

/* TTS receive queue (filled from WS events, drained by playback task) */
static QueueHandle_t g_tts_queue = NULL;

/* Connected flag */
static volatile bool g_connected = false;

/* Owner's voice_state_t* */
static void *g_owner_state = NULL;

/* --- Binary protocol helpers (see msg_protocol.c) --- */

/* --- WS event handler --- */
static void ws_event_handler(void *handler_args, esp_event_base_t base,
                              int32_t event_id, void *event_data)
{
    esp_websocket_event_data_t *data = (esp_websocket_event_data_t *)event_data;

    switch (event_id) {
    case WEBSOCKET_EVENT_CONNECTED:
        ESP_LOGI(TAG, "WS connected");
        g_connected = true;
        if (g_owner_state) {
            volatile bool *conn = (volatile bool *)((char *)g_owner_state + 0);
            *conn = true;
        }
        break;

    case WEBSOCKET_EVENT_DISCONNECTED:
    case WEBSOCKET_EVENT_ERROR:
        ESP_LOGW(TAG, "WS disconnected (event %ld)", event_id);
        g_connected = false;
        if (g_owner_state) {
            volatile bool *conn = (volatile bool *)((char *)g_owner_state + 0);
            *conn = false;
        }
        break;

    case WEBSOCKET_EVENT_DATA:
        /* data->data_ptr points to WebSocket frame payload */
        /* First byte = opcode. For binary frames: opcode=2.
         * Our protocol: [type 1B][len 4B BE][payload]
         */
        if (data->data_len >= 5 && data->op_code == 2) {
            uint8_t msg_type = ((uint8_t *)data->data_ptr)[0];
            uint32_t payload_len;
            memcpy(&payload_len, (uint8_t *)data->data_ptr + 1, 4);
            payload_len = __builtin_bswap32(payload_len);  /* big-endian */

            uint8_t *payload = (uint8_t *)data->data_ptr + 5;

            if (msg_type == MSG_TYPE_TTS_AUDIO) {
                /* Enqueue for playback */
                uint8_t *copy = malloc(payload_len);
                if (copy) {
                    memcpy(copy, payload, payload_len);
                    tts_chunk_t tts = { .data = copy, .len = payload_len };
                    BaseType_t ok = xQueueSend(g_tts_queue, &tts, pdMS_TO_TICKS(100));
                    if (!ok) {
                        ESP_LOGW(TAG, "TTS queue full, dropping chunk");
                        free(copy);
                    }
                }
            } else if (msg_type == MSG_TYPE_STT_RESULT) {
                ESP_LOGI(TAG, "STT result: %.*s",
                         (int)payload_len, (char *)payload);
            } else if (msg_type == MSG_TYPE_ERROR) {
                ESP_LOGE(TAG, "Server error: %.*s",
                         (int)payload_len, (char *)payload);
            } else if (msg_type == MSG_TYPE_PING) {
                /* Auto-pong */
                ws_send_ping();
            }
        }
        break;

    case WEBSOCKET_EVENT_MAX:
        break;
    }
}

/* --- Public API --- */

esp_err_t ws_connect(const char *url, void *state)
{
    g_owner_state = state;

    /* Create queues */
    g_tts_queue = xQueueCreate(8, sizeof(tts_chunk_t));
    if (g_tts_queue == NULL) {
        ESP_LOGE(TAG, "Failed to create TTS queue");
        return ESP_FAIL;
    }

    /* WebSocket config */
    esp_websocket_client_config_t cfg = {
        .uri = url,
        .task_stack = 4096,
        .task_prio = 5,
        .buffer_size = 4096,
        .disable_auto_reconnect = false,
        .reconnect_timeout_ms = 5000,
    };

    g_ws_client = esp_websocket_client_init(&cfg);
    if (g_ws_client == NULL) {
        ESP_LOGE(TAG, "WS client init failed");
        vQueueDelete(g_tts_queue);
        return ESP_FAIL;
    }

    ESP_ERROR_CHECK(esp_websocket_register_events(g_ws_client,
        WEBSOCKET_EVENT_ANY, ws_event_handler, NULL));

    ESP_LOGI(TAG, "Connecting to %s...", url);
    ESP_ERROR_CHECK(esp_websocket_client_start(g_ws_client));

    /* Wait for connection (with timeout) */
    int retries = 20;
    while (!g_connected && retries-- > 0) {
        vTaskDelay(pdMS_TO_TICKS(500));
    }

    if (!g_connected) {
        ESP_LOGE(TAG, "WS connection timeout");
        esp_websocket_client_destroy(g_ws_client);
        g_ws_client = NULL;
        vQueueDelete(g_tts_queue);
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "WS connected OK");
    return ESP_OK;
}

void ws_disconnect(void)
{
    if (g_ws_client) {
        esp_websocket_client_stop(g_ws_client);
        esp_websocket_client_destroy(g_ws_client);
        g_ws_client = NULL;
    }
    g_connected = false;
    if (g_tts_queue) {
        /* Drain */
        tts_chunk_t c;
        while (xQueueReceive(g_tts_queue, &c, 0) == pdTRUE) {
            free(c.data);
        }
        vQueueDelete(g_tts_queue);
        g_tts_queue = NULL;
    }
}

esp_err_t ws_send_audio(const uint8_t *pcm_data, size_t pcm_len)
{
    if (!g_connected || g_ws_client == NULL) return ESP_FAIL;

    uint8_t header[5];
    header[0] = MSG_TYPE_AUDIO;
    uint32_t len_be = __builtin_bswap32((uint32_t)pcm_len);
    memcpy(header + 1, &len_be, 4);

    /* Send header + payload in one WebSocket binary frame */
    size_t total = 5 + pcm_len;
    uint8_t *buf = malloc(total);
    if (buf == NULL) return ESP_ERR_NO_MEM;
    memcpy(buf, header, 5);
    memcpy(buf + 5, pcm_data, pcm_len);

    int ret = esp_websocket_client_send_bin(g_ws_client, (const char *)buf, total, pdMS_TO_TICKS(500));
    free(buf);

    return (ret >= 0) ? ESP_OK : ESP_FAIL;
}

esp_err_t ws_send_wake(void)
{
    if (!g_connected || g_ws_client == NULL) return ESP_FAIL;

    uint8_t header[5];
    header[0] = MSG_TYPE_WAKE;
    uint32_t zero = 0;
    memcpy(header + 1, &zero, 4);

    int ret = esp_websocket_client_send_bin(g_ws_client, (const char *)header, 5, pdMS_TO_TICKS(100));
    return (ret >= 0) ? ESP_OK : ESP_FAIL;
}

esp_err_t ws_send_ping(void)
{
    if (!g_connected || g_ws_client == NULL) return ESP_FAIL;

    uint8_t header[5];
    header[0] = MSG_TYPE_PING;
    uint32_t zero = 0;
    memcpy(header + 1, &zero, 4);

    int ret = esp_websocket_client_send_bin(g_ws_client, (const char *)header, 5, pdMS_TO_TICKS(100));
    return (ret >= 0) ? ESP_OK : ESP_FAIL;
}

esp_err_t ws_receive_tts(uint8_t **out_data, size_t *out_len, TickType_t timeout_ticks)
{
    *out_data = NULL;
    *out_len = 0;

    if (g_tts_queue == NULL) return ESP_ERR_INVALID_STATE;

    tts_chunk_t chunk;
    BaseType_t ok = xQueueReceive(g_tts_queue, &chunk, timeout_ticks);
    if (ok == pdTRUE) {
        *out_data = chunk.data;
        *out_len = chunk.len;
        return ESP_OK;
    }
    return ESP_ERR_TIMEOUT;
}

bool ws_is_connected(void)
{
    return g_connected;
}
