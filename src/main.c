/*
 * Copyright (c) 2024 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/device.h>
#include <zephyr/pm/device.h>
#include <zephyr/devicetree.h>

#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/addr.h>
#include <zephyr/bluetooth/gap.h>
#include <bluetooth/scan.h>

LOG_MODULE_REGISTER(app, LOG_LEVEL_DBG);


static void scan_filter_match(struct bt_scan_device_info *device_info,
			      			  struct bt_scan_filter_match *filter_match,
			      			  bool connectable)
{

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
	LOG_INF("START%02X",filter_match->addr.addr->a.val[0]);
	// for(int i = 4; i < ad_len; i++)
	// {
	// 	LOG_INF("%02X", device_info->adv_data->data[i]);
	// } 
	LOG_HEXDUMP_INF(&device_info->adv_data->data[4],
                ad_len - 4,
                "DATA");
	LOG_INF("END");
	// LOG_INF("%02X%02X ", device_info->adv_data->data[14],device_info->adv_data->data[13]);
}

BT_SCAN_CB_INIT(scan_cb, scan_filter_match, NULL, NULL, NULL);


static void scan_init(void)
{
	int err;

	/* Use active scanning and disable duplicate filtering to handle any
	 * devices that might update their advertising data at runtime. */
	struct bt_le_scan_param scan_param = {
		.type     = BT_LE_SCAN_TYPE_PASSIVE,
		.interval = BT_GAP_SCAN_FAST_INTERVAL, // 5ms
		.window   = 0x0055, // 2.5ms
		.options  = BT_LE_SCAN_OPT_NONE
	};

	struct bt_scan_init_param scan_init = {
		.connect_if_match = 0,
		.scan_param = &scan_param,
		.conn_param = NULL
	};

	bt_scan_init(&scan_init);
	bt_scan_cb_register(&scan_cb);

	bt_addr_le_t addr;
    err = bt_addr_le_from_str("FF:EE:DD:CC:BB:AA", "random", &addr);
	err = bt_scan_filter_add(BT_SCAN_FILTER_TYPE_ADDR, &addr);
	if (err) {
		LOG_INF("Scanning filters cannot be set (err %d)\n", err);
		return;
	}

	// set a second filter
	err = bt_addr_le_from_str("FF:EE:DD:CC:BB:AB", "random", &addr);
	err = bt_scan_filter_add(BT_SCAN_FILTER_TYPE_ADDR, &addr);
	if (err) {
		LOG_INF("Scanning filters cannot be set (err %d)\n", err);
		return;
	}

	err = bt_addr_le_from_str("FF:EE:DD:CC:BB:AC", "random", &addr);
	err = bt_scan_filter_add(BT_SCAN_FILTER_TYPE_ADDR, &addr);
	if (err) {
		LOG_INF("Scanning filters cannot be set (err %d)\n", err);
		return;
	}

	err = bt_addr_le_from_str("FF:EE:DD:CC:BB:AD", "random", &addr);
	err = bt_scan_filter_add(BT_SCAN_FILTER_TYPE_ADDR, &addr);
	if (err) {
		LOG_INF("Scanning filters cannot be set (err %d)\n", err);
		return;
	}

	err = bt_addr_le_from_str("FF:EE:DD:CC:BB:AE", "random", &addr);
	err = bt_scan_filter_add(BT_SCAN_FILTER_TYPE_ADDR, &addr);
	if (err) {
		LOG_INF("Scanning filters cannot be set (err %d)\n", err);
		return;
	}

	err = bt_scan_filter_enable(BT_SCAN_ADDR_FILTER, false);
	if (err) {
		LOG_INF("Filters cannot be turned on (err %d)\n", err);
	}

	bt_scan_start(BT_LE_SCAN_TYPE_PASSIVE);
}



int main(void)
{
	LOG_INF("Application Started ====================");
	int err;

	err = bt_enable(NULL);
	if (err) {
		LOG_ERR("Bluetooth init failed (err %d)\n", err);
		return -1;
	}
	LOG_INF("==================== BT INITIALIZED");
	

	scan_init();

	while(1){
		k_sleep(K_FOREVER);
	}

	return 0;
}