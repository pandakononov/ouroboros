# SPDX-License-Identifier: Apache-2.0

idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
    REQUIRES driver esp_websocket_client esp_lpa esp_timer nvs_flash esp_wifi esp_netif
)
