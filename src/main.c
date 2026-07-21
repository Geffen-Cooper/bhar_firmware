/*
 * Copyright (c) 2026 Geffen Cooper
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/hci.h>

LOG_MODULE_REGISTER(peripheral_test, LOG_LEVEL_DBG);

/* Scan Response Data payload */
static const struct bt_data sd[] = {
    BT_DATA_BYTES(BT_DATA_NAME_COMPLETE, 'T', 'e', 's', 't', 'P', 'e', 'r', 'i', 'p', 'h'),
};

/* Advertising set reference pointer */
static struct bt_le_ext_adv *adv_set;

/* Callback triggered whenever a Central sends a SCAN_REQ */
static void scan_req_cb(struct bt_le_ext_adv *adv, const struct bt_le_ext_adv_scanned_info *info)
{
    char addr_str[BT_ADDR_LE_STR_LEN];
    bt_addr_le_to_str(info->addr, addr_str, sizeof(addr_str));

    LOG_INF(">>> RECEIVED SCAN_REQ from Central MAC: %s", addr_str);
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
    err = bt_le_ext_adv_start(adv_set, BT_LE_EXT_ADV_START_PARAM_DEFAULT);
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