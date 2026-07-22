/*
 * Copyright (c) 2026 Geffen Cooper
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/bluetooth/addr.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/gap.h>

LOG_MODULE_REGISTER(peripheral_test, LOG_LEVEL_DBG);


/* STEP 2.2 - Declare the structure for your custom data  */
typedef struct adv_mfg_data {
    uint16_t company_code; /* Company Identifier Code. */
    uint8_t samples[24];
} adv_mfg_data_type;

/* STEP 2.3 - Define and initialize a variable of type adv_mfg_data_type */
#define COMPANY_ID_CODE 0x0059
static adv_mfg_data_type adv_mfg_data = {
    .company_code = COMPANY_ID_CODE,
    .samples = { 0x01, 0x02, 0x03, 0x04, 0x05, 0x06,
                 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C,
                 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12,
                 0x13, 0x14, 0x15, 0x16, 0x17, 0x18 }
};

static unsigned char url_data[] ={0x17,'/','/','a','c','a','d','e','m','y','.',
                                 'n','o','r','d','i','c','1','2','3','4','5','6','.','.',
                                 'c','o','m'};
static const struct bt_data scan_response_data[] = {
        /* 4.2.3 Include the URL data in the scan response packet*/
		BT_DATA(BT_DATA_URI, url_data,sizeof(url_data))
};

// TODO: I think this payload is too big, need to maybe remove or shorten the name
static const struct bt_data ad_batteryless[] = {
    // BT_DATA_BYTES(BT_DATA_FLAGS, BT_LE_AD_NO_BREDR),
    // BT_DATA(BT_DATA_NAME_COMPLETE, DEVICE_NAME, DEVICE_NAME_LEN),
    /* STEP 3 - Include the Manufacturer Specific Data in the advertising packet. */
    BT_DATA(BT_DATA_MANUFACTURER_DATA, (unsigned char *)&adv_mfg_data, sizeof(adv_mfg_data)),
};

struct bt_le_ext_adv *adv_set;

static void adv_scanned_cb(struct bt_le_ext_adv *adv, 
                           struct bt_le_ext_adv_scanned_info *info)
{
    // Extract the raw MAC address bytes (6 bytes)
    const uint8_t *mac = info->addr->a.val;
    
    // Extract the address type (Public vs Random)
    uint8_t type = info->addr->type;

    LOG_INF("--- Scan Request Detected! ---");
    LOG_INF("Central MAC Address: %02x:%02x:%02x:%02x:%02x:%02x", 
            mac[5], mac[4], mac[3], mac[2], mac[1], mac[0]);
    LOG_INF("Address Type: %s", type == BT_ADDR_LE_PUBLIC ? "Public" : "Random");
    
    // Process your connectionless address data trick here
    // uint8_t feedback_cmd = mac[5]; 
    // LOG_INF("Extracted Feedback Byte: 0x%02x", feedback_cmd);
	// for(int i = 0; i < 6; i++)
	// {
	// 	url_data[i+3] = mac[i];
	// }
	url_data[17] = mac[0];
	url_data[18] = mac[1];
	url_data[19] = mac[2];
	url_data[20] = mac[3];
	url_data[21] = mac[4];
	url_data[22] = mac[5];

	url_data[24] = 0x62;
	url_data[25] = 0x65;
	url_data[26] = 0x65;
	url_data[27] = 0x66;
	// message is 28 bytes long (last idx is 28)

	// bt_le_ext_adv_stop(adv_set);
	// bt_le_ext_adv_set_data(adv_set, ad_batteryless, ARRAY_SIZE(ad_batteryless),scan_response_data, ARRAY_SIZE(scan_response_data));
	// bt_le_ext_adv_start(adv_set, NULL);

	bt_le_ext_adv_stop(adv_set);
	k_sleep(K_MSEC(18));

	bt_le_ext_adv_set_data(adv_set, ad_batteryless, ARRAY_SIZE(ad_batteryless),scan_response_data, ARRAY_SIZE(scan_response_data));
	bt_le_ext_adv_start(adv_set, NULL);
	
}


static const struct bt_le_ext_adv_cb adv_callbacks = {
    .scanned = adv_scanned_cb, // <-- Bound here
	.sent = NULL,
	.connected = NULL
};

/* Extended advertising callbacks */
// static const struct bt_le_ext_adv_cb adv_callbacks = {
//     .scanned   = scan_req_cb,
//     .sent      = NULL,
//     .connected = NULL,
// };

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

    struct bt_le_adv_param adv_param_ = BT_LE_ADV_PARAM_INIT(
        BT_LE_ADV_OPT_SCANNABLE | 
		BT_LE_ADV_OPT_USE_IDENTITY |
		BT_LE_ADV_OPT_NOTIFY_SCAN_REQ,
        32,
        33,
        NULL
    );

	// bt_le_ext_adv_create(&adv_param, &adv_callbacks, &adv_set);
	err = bt_le_ext_adv_create(&adv_param_, &adv_callbacks, &adv_set);
	if (err) {
        LOG_ERR("adv create failed (err %d)", err);
        return -1;
    }

    bt_le_ext_adv_set_data(adv_set, ad_batteryless, ARRAY_SIZE(ad_batteryless),scan_response_data, ARRAY_SIZE(scan_response_data));
	bt_le_ext_adv_start(adv_set, NULL);

    LOG_INF("Peripheral set FF:EE:DD:CC:BB:FF advertising and listening for SCAN_REQ...");

    while (1) {
        k_sleep(K_FOREVER);
    }

    return 0;
}