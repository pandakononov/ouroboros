/* Ouroboros Binary Protocol — message types & helpers
 * Header format: [type 1 byte][payload_len 4 bytes BE][payload N bytes]
 */
#pragma once

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Message types — mirror voice_server/protocol.py */
typedef enum {
    MSG_TYPE_AUDIO     = 0x01,
    MSG_TYPE_STT_RESULT= 0x02,
    MSG_TYPE_TTS_AUDIO = 0x03,
    MSG_TYPE_WAKE      = 0x04,
    MSG_TYPE_PING      = 0x05,
    MSG_TYPE_ERROR     = 0xFF,
} msg_type_t;

/* TTS chunk for playback queue (ws.c) */
typedef struct {
    uint8_t *data;
    size_t   len;
} tts_chunk_t;

/* Parse header from raw buffer.
 * Returns pointer to payload start and fills *out_len.
 * Returns NULL if buffer < 5 bytes.
 */
static inline const uint8_t *msg_parse_header(const uint8_t *buf, size_t buf_len,
                                               uint8_t *out_type, uint32_t *out_len)
{
    if (buf_len < 5) return NULL;
    *out_type = buf[0];
    uint32_t len_be;
    memcpy(&len_be, buf + 1, 4);
    *out_len = __builtin_bswap32(len_be);
    return buf + 5;
}

/* Build header into buf (must be at least 5 bytes).
 * Returns number of header bytes written (always 5).
 */
static inline size_t msg_build_header(uint8_t *buf, uint8_t type, uint32_t payload_len)
{
    buf[0] = type;
    uint32_t len_be = __builtin_bswap32(payload_len);
    memcpy(buf + 1, &len_be, 4);
    return 5;
}

#ifdef __cplusplus
}
#endif
