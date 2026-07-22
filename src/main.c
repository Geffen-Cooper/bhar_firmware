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
#include <zephyr/bluetooth/crypto.h>

/* Nordic's Scan Module Header */
#include <bluetooth/scan.h>

LOG_MODULE_REGISTER(app, LOG_LEVEL_DBG);

/* Secret Key shared with the peripheral */
static const uint8_t irk[16] = { 
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F 
};

#define TEST_DATA_PAYLOAD 0xF0F0

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

/* ---------- Nordic Scan Module Filter Callback ---------- */
// static void scan_filter_match(struct bt_scan_device_info *device_info,
//                               struct bt_scan_filter_match *filter_match,
//                               bool connectable)
// {
//     char addr_str[BT_ADDR_LE_STR_LEN];
//     bt_addr_le_to_str(device_info->recv_info->addr, addr_str, sizeof(addr_str));

//     if (device_info->recv_info->adv_props & BT_GAP_ADV_PROP_SCAN_RESPONSE) {
//         LOG_INF(">>> FILTER MATCH: SCAN_RSP from: %s (RSSI: %d dBm)", 
//                 addr_str, device_info->recv_info->rssi);
//     } else {
//         LOG_INF(">>> FILTER MATCH: Adv Packet from: %s (RSSI: %d dBm)", 
//                 addr_str, device_info->recv_info->rssi);
//     }
// }
static bool parse_data_cb(struct bt_data *data, void *user_data)
{
    // data->type will tell you the BLE AD Data type (e.g., Manufacturer Data)
    // data->data holds the payload bytes, data->data_len holds its length
    
    LOG_HEXDUMP_INF(data->data, data->data_len, "PARSED_FIELD_DATA");
    
    return true; // Keep parsing subsequent fields if there are multiple
}

static void scan_filter_match(struct bt_scan_device_info *device_info,
			      			  struct bt_scan_filter_match *filter_match,
			      			  bool connectable)
{

	// first check the adv type
	uint8_t adv_type = device_info->recv_info->adv_type;
	uint8_t adv_len = device_info->adv_data->len;
	LOG_INF("Adv Type: %02X, Length: %02X", adv_type, adv_len);

	bt_data_parse(device_info->adv_data, parse_data_cb, NULL);

	return;

	// char addr_str[BT_ADDR_LE_STR_LEN];
	// LOG_INF("%02X",filter_match->addr.addr->a.val[0]);
	// LOG_INF("%02X",filter_match->addr.addr->a.val[1]);
	// LOG_INF("%02X",filter_match->addr.addr->a.val[2]);
	// bt_addr_le_to_str(&filter_match->addr.addr, addr_str, sizeof(addr_str));

	// LOG_INF("Matched filtered address: %s", addr_str);

    struct bt_data *ad;
    int ad_len = device_info->adv_data->len;

    // LOG_INF("Advertising data (%d bytes): ", ad_len);
	// 28 bytes total
	// first byte is length (says 27)
	// second byte is type
	// 2 bytes nordic id
	// 24 bytes acceleromter data
	LOG_INF("START: %02X",filter_match->addr.addr->a.val[0]);
	// for(int i = 4; i < ad_len; i++)
	// {
	// 	LOG_INF("%02X", device_info->adv_data->data[i]);
	// } 
	LOG_HEXDUMP_INF(&device_info->adv_data->data,
                ad_len,
                "DATA");
	LOG_INF("END");
	// LOG_INF("%02X%02X ", device_info->adv_data->data[14],device_info->adv_data->data[13]);
}

/* Register the Nordic scan callback */
BT_SCAN_CB_INIT(scan_cb, scan_filter_match, NULL, NULL, NULL);

/* ---------- Start Nordic Filtered Scan ---------- */
static int start_filtered_scan(void)
{
    int err;

    struct bt_le_scan_param scan_param = {
        .type     = BT_LE_SCAN_TYPE_ACTIVE,
        .interval = BT_GAP_SCAN_FAST_INTERVAL,
        .window   = BT_GAP_SCAN_FAST_WINDOW,
        .options  = BT_LE_SCAN_OPT_NONE, /* Don't filter duplicates */
    };

    struct bt_scan_init_param scan_init_params = {
        .connect_if_match = 0,
        .scan_param       = &scan_param,
        .conn_param       = NULL
    };

    /* 1. Initialize Nordic's scan module */
    bt_scan_init(&scan_init_params);
    bt_scan_cb_register(&scan_cb);

    /* 2. Add Target Address Filter */
    bt_addr_le_t addr;
    err = bt_addr_le_from_str("FF:EE:DD:CC:BB:FF", "random", &addr);
    if (err) {
        LOG_ERR("Failed to parse filter address (err %d)", err);
        return err;
    }

    err = bt_scan_filter_add(BT_SCAN_FILTER_TYPE_ADDR, &addr);
    if (err) {
        LOG_ERR("Failed to add address filter (err %d)", err);
        return err;
    }

    /* 3. Enable Address Filtering */
    err = bt_scan_filter_enable(BT_SCAN_ADDR_FILTER, false);
    if (err) {
        LOG_ERR("Failed to enable address filter (err %d)", err);
        return err;
    }

    /* 4. Start Nordic Scanner (Do NOT use bt_le_scan_start here!) */
    err = bt_scan_start(BT_LE_SCAN_TYPE_ACTIVE);
    if (err) {
        LOG_ERR("Failed to start Nordic scanner (err %d)", err);
        return err;
    }

    return 0;
}

/* ---------- Main ---------- */
int main(void)
{
    LOG_INF("=== Central Test App Started ===");
    bt_addr_t rpa;
    int err;

	bt_addr_le_t addr;
    err = bt_addr_le_from_str("FF:11:11:11:11:FF", "random", &addr);
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

    build_rpa(TEST_DATA_PAYLOAD, &rpa);
    LOG_INF("Generated Test MAC: %02X:%02X:%02X:%02X:%02X:%02X", 
            rpa.val[5], rpa.val[4], rpa.val[3], rpa.val[2], rpa.val[1], rpa.val[0]);

    // err = hci_set_random_address(&rpa);
    // if (err) {
    //     LOG_ERR("Failed to set random MAC address (err %d)", err);
    //     return -1;
    // }
	

    err = start_filtered_scan();
    if (err) {
        LOG_ERR("Failed to start active scanning (err %d)", err);
        return -1;
    }
    LOG_INF("Nordic Filtered Active Scanning live for FF:EE:DD:CC:BB:FF...");

    while (1) {
        k_sleep(K_FOREVER);
    }

    return 0;
}