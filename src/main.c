/*
 * Copyright (c) 2026 Geffen Cooper
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/hci.h>

LOG_MODULE_REGISTER(peripheral_test, LOG_LEVEL_DBG);

/* Scan Response Data payload so the Central receives an actual SCAN_RSP packet */
static const struct bt_data sd[] = {
    BT_DATA_BYTES(BT_DATA_NAME_COMPLETE, 'T', 'e', 's', 't', 'P', 'e', 'r', 'i', 'p', 'h'),
};

/* Advertising parameters: Scannable, Non-Connectable, Fast Interval */
static struct bt_le_adv_param adv_params = BT_LE_ADV_PARAM_INIT(
    BT_LE_ADV_OPT_SCANNABLE | BT_LE_ADV_OPT_USE_IDENTITY, 
    BT_LE_ADV_INTERVAL_MIN, 
    BT_LE_ADV_INTERVAL_MAX, 
    NULL
);

/* Callback triggered whenever the peripheral receives a SCAN_REQ from a Central */
static void scan_req_cb(const struct bt_le_ext_adv_scanned_info *info)
{
    char addr_str[BT_ADDR_LE_STR_LEN];
    bt_addr_le_to_str(info->addr, addr_str, sizeof(addr_str));

    LOG_INF(">>> RECEIVED SCAN_REQ from Central MAC: %s", 
            addr_str);
}

static struct bt_le_ext_adv_cb adv_callbacks = {
    .scanned = scan_req_cb,
};

int main(void)
{
    int err;

    LOG_INF("=== Starting Minimal Test Peripheral ===");

	// Fix the BLE address
	bt_addr_le_t addr;
    err = bt_addr_le_from_str("FF:EE:DD:CC:BB:FF", "random", &addr);
    err = bt_id_create(&addr, NULL);

    err = bt_enable(NULL);
    if (err) {
        LOG_ERR("Bluetooth init failed (err %d)", err);
        return -1;
    }

    /* Start advertising with scan response payload */
    err = bt_le_adv_start(&adv_params, NULL, 0, sd, ARRAY_SIZE(sd));
    if (err) {
        LOG_ERR("Advertising failed to start (err %d)", err);
        return -1;
    }

    LOG_INF("Peripheral is advertising and actively listening for SCAN_REQ...");

    while (1) {
        k_sleep(K_FOREVER);
    }

    return 0;
}