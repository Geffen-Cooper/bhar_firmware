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
#include <zephyr/bluetooth/hci_types.h>
#include <zephyr/bluetooth/hci.h>


LOG_MODULE_REGISTER(peripheral_test, LOG_LEVEL_DBG);

/* 1. Define and initialize a binary semaphore with initial count 0 and max count 1 */
K_SEM_DEFINE(work_sem, 0, 1);

/* 2. Timer expiry function callback */
void timer_expiry_function(struct k_timer *timer_id)
{
    /* Give the semaphore to unblock the worker thread */
    k_sem_give(&work_sem);
}

/* 3. Define the timer and attach the callback function */
K_TIMER_DEFINE(sec_timer, timer_expiry_function, NULL);

/* 4. Worker thread definition */
#define STACK_SIZE 1024
#define PRIORITY 7

static const uint8_t central_irk[16] = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F
}; /* same IRK the central uses */


#define CENTRAL_ID_ADDR_STR "FF:EE:DD:CC:BB:EE" /* placeholder identity, same as before */

static int hci_add_dev_to_resolving_list(const bt_addr_le_t *peer_id_addr,
                                          const uint8_t *peer_irk)
{
    struct bt_hci_cp_le_add_dev_to_rl cp = {0};
    bt_addr_le_copy(&cp.peer_id_addr, peer_id_addr);
    memcpy(cp.peer_irk, peer_irk, 16);

    struct net_buf *buf = bt_hci_cmd_create(BT_HCI_OP_LE_ADD_DEV_TO_RL, sizeof(cp));
    if (!buf) return -ENOBUFS;
    net_buf_add_mem(buf, &cp, sizeof(cp));
    return bt_hci_cmd_send_sync(BT_HCI_OP_LE_ADD_DEV_TO_RL, buf, NULL);
}

static int hci_set_addr_resolution_enable(bool enable)
{
    struct bt_hci_cp_le_set_addr_res_enable cp = { .enable = enable };
    struct net_buf *buf = bt_hci_cmd_create(BT_HCI_OP_LE_SET_ADDR_RES_ENABLE, sizeof(cp));
    if (!buf) return -ENOBUFS;
    net_buf_add_mem(buf, &cp, sizeof(cp));
    return bt_hci_cmd_send_sync(BT_HCI_OP_LE_SET_ADDR_RES_ENABLE, buf, NULL);
}


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


void worker_thread_entry(void *p1, void *p2, void *p3)
{
    while (1) {
        /* Wait indefinitely for the semaphore */
        if (k_sem_take(&work_sem, K_FOREVER) == 0) {
            bt_le_ext_adv_set_data(adv_set, ad_batteryless, ARRAY_SIZE(ad_batteryless),scan_response_data, ARRAY_SIZE(scan_response_data));
            bt_le_ext_adv_start(adv_set, NULL);
            k_sleep(K_MSEC(18));
            bt_le_ext_adv_stop(adv_set);
        }
    }
}

K_THREAD_DEFINE(worker_thread_id, STACK_SIZE, worker_thread_entry, 
                NULL, NULL, NULL, PRIORITY, 0, 0);


/* Declare external variables defined in Link Layer */
// extern volatile uint8_t g_raw_scan_req_mac[6];
// extern volatile uint32_t g_raw_scan_req_counter;

static void adv_scanned_cb(struct bt_le_ext_adv *adv, 
                           struct bt_le_ext_adv_scanned_info *info)
{
	// LOG_INF("--- Scan Request Verified by HW Accept List! ---");
    
    // /* info->addr will be the translated Identity MAC */
    // LOG_INF("Resolved Identity MAC: %02X:%02X:%02X:%02X:%02X:%02X", 
    //         info->addr->a.val[5], info->addr->a.val[4], info->addr->a.val[3],
    //         info->addr->a.val[2], info->addr->a.val[1], info->addr->a.val[0]);

    // /* g_raw_scan_req_mac holds the raw over-the-air MAC stashed directly in the ISR */
    // LOG_INF("Raw OTA MAC: %02X:%02X:%02X:%02X:%02X:%02X", 
    //         g_raw_scan_req_mac[5], g_raw_scan_req_mac[4], g_raw_scan_req_mac[3],
    //         g_raw_scan_req_mac[2], g_raw_scan_req_mac[1], g_raw_scan_req_mac[0]);

	// LOG_INF("Count: %d", g_raw_scan_req_counter);

    // /* Extract 24-bit prand from g_raw_scan_req_mac[3..5] */
    // uint32_t prand = ((uint32_t)g_raw_scan_req_mac[3]) | 
    //                  ((uint32_t)g_raw_scan_req_mac[4] << 8) | 
    //                  ((uint32_t)g_raw_scan_req_mac[5] << 16);

    // /* Strip off top 2 RPA bits (0b01) */
    // uint32_t extracted_payload = prand & 0x3FFFFF;

    // LOG_INF("Extracted 22-bit Payload: 0x%06X (%u)", extracted_payload, extracted_payload);

    // /* Put extracted payload into scan response payload */
    // url_data[17] = (uint8_t)(extracted_payload & 0xFF);         
    // url_data[18] = (uint8_t)((extracted_payload >> 8) & 0xFF);  
    // url_data[19] = (uint8_t)((extracted_payload >> 16) & 0x3F); 

    // url_data[24] = 'b';
    // url_data[25] = 'e';
    // url_data[26] = 'e';
    // url_data[27] = 'f';

    // /* Update advertising set */
    // bt_le_ext_adv_stop(adv_set);
    // k_sleep(K_MSEC(18));

    // bt_le_ext_adv_set_data(adv_set, ad_batteryless, ARRAY_SIZE(ad_batteryless), 
    //                        scan_response_data, ARRAY_SIZE(scan_response_data));
    // bt_le_ext_adv_start(adv_set, NULL);





    // Extract the raw MAC address bytes (6 bytes)
    const uint8_t *mac = info->addr->a.val;
    
    // Extract the address type (Public vs Random)
    uint8_t type = info->addr->type;

	// if((mac[0] == 0xBB) && (mac[5] == 0x40))
	// {
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

	// bt_le_ext_adv_stop(adv_set);
	// k_sleep(K_MSEC(18));

	// bt_le_ext_adv_set_data(adv_set, ad_batteryless, ARRAY_SIZE(ad_batteryless),scan_response_data, ARRAY_SIZE(scan_response_data));
	// bt_le_ext_adv_start(adv_set, NULL);
	// }
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

	/* --- new: teach controller to resolve the central's RPA, and
     * restrict scan responses to it --- */
    bt_addr_le_t central_id;
    err = bt_addr_le_from_str(CENTRAL_ID_ADDR_STR, "random", &central_id);
    if (err) {
        LOG_ERR("Failed to parse central identity address (err %d)", err);
        return -1;
    }

    err = hci_add_dev_to_resolving_list(&central_id, central_irk);
    if (err) {
        LOG_ERR("add to resolving list failed (err %d)", err);
        return -1;
    }

    err = hci_set_addr_resolution_enable(true);
    if (err) {
        LOG_ERR("addr resolution enable failed (err %d)", err);
        return -1;
    }

    err = bt_le_filter_accept_list_add(&central_id);
    if (err) {
        LOG_ERR("add to accept list failed (err %d)", err);
        return -1;
    }

    struct bt_le_adv_param adv_param_ = BT_LE_ADV_PARAM_INIT(
        BT_LE_ADV_OPT_SCANNABLE |
        BT_LE_ADV_OPT_USE_IDENTITY |
        BT_LE_ADV_OPT_NOTIFY_SCAN_REQ |
        BT_LE_ADV_OPT_FILTER_SCAN_REQ,   /* <-- added */
        200,
        200,
        NULL
    );

    // struct bt_le_adv_param adv_param_ = BT_LE_ADV_PARAM_INIT(
    //     BT_LE_ADV_OPT_SCANNABLE | 
	// 	BT_LE_ADV_OPT_USE_IDENTITY |
	// 	BT_LE_ADV_OPT_NOTIFY_SCAN_REQ,
    //     32,
    //     33,
    //     NULL
    // );

	// bt_le_ext_adv_create(&adv_param, &adv_callbacks, &adv_set);
	err = bt_le_ext_adv_create(&adv_param_, &adv_callbacks, &adv_set);
	if (err) {
        LOG_ERR("adv create failed (err %d)", err);
        return -1;
    }

    err = bt_le_ext_adv_set_data(adv_set, ad_batteryless, ARRAY_SIZE(ad_batteryless),scan_response_data, ARRAY_SIZE(scan_response_data));
	if (err) {
        LOG_ERR("adv set failed (err %d)", err);
        return -1;
    }
	// err = bt_le_ext_adv_start(adv_set, NULL);
	// if (err) {
    //     LOG_ERR("adv start failed (err %d)", err);
    //     return -1;
    // }
    k_timer_start(&sec_timer, K_SECONDS(1), K_SECONDS(1));

    LOG_INF("Peripheral set FF:EE:DD:CC:BB:FF advertising and listening for SCAN_REQ...");

    while (1) {
        k_sleep(K_FOREVER);
    }

    return 0;
}