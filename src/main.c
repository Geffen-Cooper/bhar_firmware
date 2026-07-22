/*
 * Copyright (c) 2026 Geffen Cooper
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/hci.h>

LOG_MODULE_REGISTER(peripheral_test, LOG_LEVEL_DBG);

/* Cache configuration for deduplicating MAC addresses */
#define MAC_CACHE_SIZE 16

static bt_addr_le_t mac_cache[MAC_CACHE_SIZE];
static uint8_t mac_cache_count = 0;
static uint8_t mac_cache_head = 0;

/* Helper function to check and insert new MAC addresses */
static bool is_unique_mac(const bt_addr_le_t *addr)
{
    /* Check if the address is already in the cache */
    for (uint8_t i = 0; i < mac_cache_count; i++) {
        if (bt_addr_le_cmp(&mac_cache[i], addr) == 0) {
            return false; /* Already logged */
        }
    }

    /* Store the new MAC address in a ring-buffer fashion */
    bt_addr_le_copy(&mac_cache[mac_cache_head], addr);
    mac_cache_head = (mac_cache_head + 1) % MAC_CACHE_SIZE;

    if (mac_cache_count < MAC_CACHE_SIZE) {
        mac_cache_count++;
    }

    return true; /* New address! */
}

/* Scan Response Data payload */
static const struct bt_data sd[] = {
    BT_DATA_BYTES(BT_DATA_NAME_COMPLETE, 'T', 'e', 's', 't', 'P', 'e', 'r', 'i', 'p', 'h'),
};

/* Advertising set reference pointer */
static struct bt_le_ext_adv *adv_set;

/* Callback triggered whenever a Central sends a SCAN_REQ */
static void scan_req_cb(struct bt_le_ext_adv *adv, const struct bt_le_ext_adv_scanned_info *info)
{
    // /* Only log if this address hasn't been seen recently */
    // if (is_unique_mac(info->addr)) {
    //     char addr_str[BT_ADDR_LE_STR_LEN];
    //     bt_addr_le_to_str(info->addr, addr_str, sizeof(addr_str));

    //     LOG_INF(">>> RECEIVED NEW SCAN_REQ from Central MAC: %s", addr_str);
    // }
	const uint8_t *mac = info->addr->a.val;
	LOG_INF("MAC: %02X:%02X:%02X:%02X:%02X:%02X",
        mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

/* Extended advertising callbacks */
static const struct bt_le_ext_adv_cb adv_callbacks = {
    .scanned   = scan_req_cb,
    .sent      = NULL,
    .connected = NULL,
};

/* Extended Advertising Parameters with SCAN_REQ notification enabled */
static struct bt_le_adv_param adv_param_ = BT_LE_ADV_PARAM_INIT(
    BT_LE_ADV_OPT_SCANNABLE | 
    BT_LE_ADV_OPT_USE_IDENTITY | 
    BT_LE_ADV_OPT_NOTIFY_SCAN_REQ,
    32,   /* ~20ms interval */
    33,   /* ~20.625ms interval */
    NULL
);

int main(void)
{
    int err;

    LOG_INF("=== Starting Minimal Test Peripheral ===");

    /* Set custom identity address before bt_enable */
    bt_addr_le_t addr;
    err = bt_addr_le_from_str("FF:EE:DD:CC:BB:FF", "random", &addr);
    if (err) {
        LOG_ERR("Failed to parse static address (err %d)", err);
        return -1;
    }

    err = bt_id_create(&addr, NULL);
    if (err < 0) {
        LOG_ERR("Failed to create identity address (err %d)", err);
        return -1;
    }

    err = bt_enable(NULL);
    if (err) {
        LOG_ERR("Bluetooth init failed (err %d)", err);
        return -1;
    }

    /* 1. Create extended advertising set with callbacks */
    err = bt_le_ext_adv_create(&adv_param_, &adv_callbacks, &adv_set);
    if (err) {
        LOG_ERR("Failed to create extended adv set (err %d)", err);
        return -1;
    }

    /* 2. Set Scan Response Data */
    err = bt_le_ext_adv_set_data(adv_set, NULL, 0, sd, ARRAY_SIZE(sd));
    if (err) {
        LOG_ERR("Failed to set adv/scan response data (err %d)", err);
        return -1;
    }

    /* 3. Start Extended Advertising */
    err = bt_le_ext_adv_start(adv_set, NULL);
    if (err) {
        LOG_ERR("Failed to start extended advertising (err %d)", err);
        return -1;
    }

    LOG_INF("Peripheral set FF:EE:DD:CC:BB:FF advertising and listening for SCAN_REQ...");

    while (1) {
        k_sleep(K_FOREVER);
    }

    return 0;
}