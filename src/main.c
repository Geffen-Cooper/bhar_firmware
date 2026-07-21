/*
 * Copyright (c) 2026 Geffen Cooper
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/device.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/hci.h>
#include <zephyr/bluetooth/hci_types.h>
#include <zephyr/bluetooth/crypto.h>

LOG_MODULE_REGISTER(app, LOG_LEVEL_DBG);

/* Secret Key shared with the peripheral */
static const uint8_t irk[16] = { 
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F 
};

#define TEST_DATA_PAYLOAD 1234

/* ---------- Simplified RPA construction ---------- */
static void build_rpa(uint32_t data22, bt_addr_t *out_addr)
{
    uint8_t plaintext[16] = {0};
    uint8_t cipher[16];
    uint32_t prand_val = 0x400000 | (data22 & 0x3FFFFF);

    plaintext[0] = prand_val & 0xFF;          
    plaintext[1] = (prand_val >> 8) & 0xFF;
    plaintext[2] = (prand_val >> 16) & 0xFF; 

    bt_encrypt_le(irk, plaintext, cipher);

    out_addr->val[0] = cipher[0];
    out_addr->val[1] = cipher[1];
    out_addr->val[2] = cipher[2];
    out_addr->val[3] = plaintext[0];
    out_addr->val[4] = plaintext[1];
    out_addr->val[5] = plaintext[2]; 
}

/* ---------- Raw HCI set address helper ---------- */
static int hci_set_random_address(const bt_addr_t *addr)
{
    struct net_buf *buf = bt_hci_cmd_create(BT_HCI_OP_LE_SET_RANDOM_ADDRESS, 
                                            sizeof(struct bt_hci_cp_le_set_random_address));
    if (!buf) return -ENOBUFS;
    
    struct bt_hci_cp_le_set_random_address *cp = net_buf_add(buf, sizeof(*cp));
    bt_addr_copy(&cp->bdaddr, addr);
    return bt_hci_cmd_send_sync(BT_HCI_OP_LE_SET_RANDOM_ADDRESS, buf, NULL);
}

/* ---------- Scan Callback ---------- */
static void scan_recv_cb(const struct bt_le_scan_recv_info *info, struct net_buf_simple *buf)
{
    char addr_str[BT_ADDR_LE_STR_LEN];
    bt_addr_le_to_str(info->addr, addr_str, sizeof(addr_str));

    /* Check if packet is a Scan Response (0x04 or BT_GAP_ADV_TYPE_SCAN_RSP) */
    if (info->adv_props & BT_GAP_ADV_PROP_SCAN_RESPONSE) {
        LOG_INF(">>> Intercepted SCAN_RSP from: %s (RSSI: %d dBm)", addr_str, info->rssi);
    } else {
        LOG_DBG("Discovered Advertising Packet from: %s", addr_str);
    }
}

static struct bt_le_scan_cb scan_callbacks = {
    .recv = scan_recv_cb,
};

/* ---------- Start Active Scanning ---------- */
static int start_active_scan(void)
{
    struct bt_le_scan_param scan_param = {
        .type       = BT_LE_SCAN_TYPE_ACTIVE,
        .options    = BT_LE_SCAN_OPT_NONE, /* Don't filter duplicates */
        .interval   = BT_GAP_SCAN_FAST_INTERVAL,
        .window     = BT_GAP_SCAN_FAST_WINDOW,
    };

	bt_addr_le_t addr;
    int err = bt_addr_le_from_str("FF:EE:DD:CC:BB:AA", "random", &addr);
	err = bt_scan_filter_add(BT_SCAN_FILTER_TYPE_ADDR, &addr);
	err = bt_scan_filter_enable(BT_SCAN_ADDR_FILTER, false);
	if (err) {
		LOG_INF("Filters cannot be turned on (err %d)\n", err);
	}

    bt_le_scan_cb_register(&scan_callbacks);
    return bt_le_scan_start(&scan_param, NULL);
}

/* ---------- Main ---------- */
int main(void)
{
    LOG_INF("=== Central Test App Started ===");
    bt_addr_t rpa;
    int err;

    err = bt_enable(NULL);
    if (err) {
        LOG_ERR("Bluetooth init failed (err %d)", err);
        return -1;
    }

    build_rpa(TEST_DATA_PAYLOAD, &rpa);
    LOG_INF("Generated Test MAC: %02X:%02X:%02X:%02X:%02X:%02X", 
            rpa.val[5], rpa.val[4], rpa.val[3], rpa.val[2], rpa.val[1], rpa.val[0]);

    err = hci_set_random_address(&rpa);
    if (err) {
        LOG_ERR("Failed to set random MAC address (err %d)", err);
        return -1;
    }

    err = start_active_scan();
    if (err) {
        LOG_ERR("Failed to start active scanning (err %d)", err);
        return -1;
    }
    LOG_INF("Active scanning is live using generated RPA. Listening for responses...");

    while (1) {
        k_sleep(K_FOREVER);
    }

    return 0;
}