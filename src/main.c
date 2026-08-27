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
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/spi.h>
#include "bma400.h"
#include "bma400_defs.h"


#include <zephyr/bluetooth/addr.h>
#include <zephyr/drivers/adc.h>

//BLE STUFF
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/gap.h>

#include <zephyr/bluetooth/hci_types.h>
#include <zephyr/bluetooth/hci.h>

LOG_MODULE_REGISTER(app, LOG_LEVEL_DBG);

static const uint8_t central_irk[16] = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F
}; /* same IRK the central uses */

#define SENSOR_ID "FF:EE:DD:CC:BB:AA"
#define SHIFT_AMOUNT 12

// #define SENSOR_ID "FF:EE:DD:CC:BB:AB"
// #define SHIFT_AMOUNT 8

// #define SENSOR_ID "FF:EE:DD:CC:BB:AC"
// ##define SHIFT_AMOUNT 4

// #define SENSOR_ID "FF:EE:DD:CC:BB:AD"
// #define SHIFT_AMOUNT 0

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


// ============= Batteryless Mode =============
#define COMPANY_ID_CODE 0x0059
int16_t adc_buf;

bool last_tx_done = true;

/* STEP 2.2 - Declare the structure for your custom data  */
typedef struct adv_mfg_data {
    uint16_t company_code; /* Company Identifier Code. */
    uint8_t samples[24];
} adv_mfg_data_type;

struct adc_sequence sequence;

static const struct adc_dt_spec adc_channel = ADC_DT_SPEC_GET(DT_PATH(zephyr_user));

struct bt_le_ext_adv *adv_set;

/* Declare external variables defined in Link Layer */
extern volatile uint8_t g_raw_scan_req_mac[6];

static const struct bt_le_adv_param *adv_param =
    BT_LE_ADV_PARAM(BT_LE_ADV_OPT_SCANNABLE | BT_LE_ADV_OPT_USE_IDENTITY, /* No options specified */
            32, /* Min Advertising Interval 250ms (400*0.625ms) */
            33, /* Max Advertising Interval 250.625ms (401*0.625ms) */
            NULL); /* Set to NULL for undirected advertising */

static const struct bt_le_adv_param *adv_param_tx_rx =
    BT_LE_ADV_PARAM(BT_LE_ADV_OPT_CONN | BT_LE_ADV_OPT_USE_IDENTITY, /* No options specified */
            32, /* Min Advertising Interval 250ms (400*0.625ms) */
            33, /* Max Advertising Interval 250.625ms (401*0.625ms) */
            NULL); /* Set to NULL for undirected advertising */


/* STEP 2.3 - Define and initialize a variable of type adv_mfg_data_type */
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

static void timer0_handler(struct k_timer *dummy);
K_TIMER_DEFINE(timer0, timer0_handler, NULL);

static void adv_scanned_cb(struct bt_le_ext_adv *adv, 
                           struct bt_le_ext_adv_scanned_info *info)
{
    k_timer_stop(&timer0);
    // uint32_t prand = ((uint32_t)g_raw_scan_req_mac[3]) | 
    //                  ((uint32_t)g_raw_scan_req_mac[4] << 8) | 
    //                  ((uint32_t)g_raw_scan_req_mac[5] << 16);
    // uint32_t extracted_payload = prand & 0x3FFFFF;

    uint16_t prand = ((uint16_t)g_raw_scan_req_mac[3]) | 
                     ((uint16_t)g_raw_scan_req_mac[4] << 8);
    uint16_t extracted_payload = (prand >> SHIFT_AMOUNT) & 0x000F;

    if(extracted_payload == 0)
    {
        k_timer_start(&timer0, K_MSEC(500), K_MSEC(500));
    }
    else if(extracted_payload == 1)
    {
        k_timer_start(&timer0, K_MSEC(1000), K_MSEC(1000));
    }
    else if(extracted_payload == 2)
    {
        k_timer_start(&timer0, K_MSEC(2000), K_MSEC(2000));
    }
    else if(extracted_payload == 3)
    {
        k_timer_start(&timer0, K_MSEC(4000), K_MSEC(4000));
    }
    else
    {
        k_timer_start(&timer0, K_MSEC(500), K_MSEC(500));
    }


	// url_data[17] = mac[0];
	// url_data[18] = mac[1];
	// url_data[19] = mac[2];
	// url_data[20] = mac[3];
	// url_data[21] = mac[4];
	// url_data[22] = mac[5];
    
    // The central can read the scan response to see if feedback was received
    url_data[17] = g_raw_scan_req_mac[0];
    url_data[18] = g_raw_scan_req_mac[1];
    url_data[19] = g_raw_scan_req_mac[2];
    url_data[20] = g_raw_scan_req_mac[3];
    url_data[21] = g_raw_scan_req_mac[4];
    url_data[22] = g_raw_scan_req_mac[5];


	url_data[24] = 0x62;
	url_data[25] = 0x65;
	url_data[26] = 0x65;
	url_data[27] = 0x66;
	// message is 28 bytes long (last idx is 28)
}

static const struct bt_le_ext_adv_cb adv_callbacks = {
    .scanned = adv_scanned_cb, // <-- Bound here
	.sent = NULL,
	.connected = NULL
};


// threads
#define STACKSIZE 2048
#define THREAD_READ_BMA_PRIORITY 7
#define THREAD_RUN_POLICY_PRIORITY 8
K_SEM_DEFINE(bma400_ready, 0, 1);
K_SEM_DEFINE(run_policy, 0, 1);

// SPI
#define SPIOP	SPI_WORD_SET(8) | SPI_TRANSFER_MSB
struct spi_dt_spec spispec = SPI_DT_SPEC_GET(DT_NODELABEL(bma400), SPIOP, 0);
uint8_t rx_buffer[128] = {0};

// interrupt GPIO
#define int_NODE DT_ALIAS(int1)
static const struct gpio_dt_spec int_pin = GPIO_DT_SPEC_GET(int_NODE, gpios);
static struct gpio_callback int_cb_data;

// PMIC EN GPIO
#define hen_NODE DT_ALIAS(hen)
static const struct gpio_dt_spec hen_pin = GPIO_DT_SPEC_GET(hen_NODE, gpios);

// BMA400
#define BMA400_REG_FIFO_CONFIG_1                  UINT8_C(0x27)
#define FIFOINTER 3
#define FIFO_SAMPLES 8 // number of samples for fifo content
#define FIFO_WATERMARK_LEVEL    UINT16_C(FIFO_SAMPLES*4) // 4 bytes per frame (XYZ+header)
#define FIFO_FULL_SIZE          UINT16_C(1024)
#define FIFO_SIZE               (FIFO_FULL_SIZE + BMA400_FIFO_BYTES_OVERREAD)
#define FIFO_ACCEL_FRAME_COUNT  UINT8_C(FIFO_SAMPLES)

BMA400_INTF_RET_TYPE read_reg_spi(uint8_t reg_address, uint8_t* data, uint32_t len, void* intf_ptr);
BMA400_INTF_RET_TYPE write_reg_spi(uint8_t reg_address, const uint8_t* data, uint32_t len, void* intf_ptr);
void bma400_delay_us(uint32_t period, void *intf_ptr) {
	k_usleep(period);
}

static uint8_t              dev_addr    = 31;
struct bma400_dev           bma_sensor         = {
        .intf = BMA400_SPI_INTF,
        .intf_ptr = &dev_addr,
        .read = read_reg_spi,
        .write = write_reg_spi,
        .delay_us = bma400_delay_us,
        .read_write_len = 8
};

struct bma400_sensor_data acc_data;

struct bma400_int_enable int_en;
struct bma400_fifo_data fifo_frame;
struct bma400_device_conf fifo_conf;
struct bma400_sensor_conf conf;
uint8_t fifo_buff[FIFO_SIZE] = { 0 };

struct bma400_fifo_sensor_data accel_data[FIFO_ACCEL_FRAME_COUNT] = { { 0 } };
struct bma400_sensor_conf settings;


void bma_int_handler(const struct device *dev, struct gpio_callback *cb, uint32_t pins)
{
	// set the semaphore
	k_sem_give(&bma400_ready);
}


void thread_read_bma400(void)
{
	while(1){
		// LOG_INF("In the read thread");
		k_sem_take(&bma400_ready, K_FOREVER); // Sleep here if semaphore is at 0
			
        // Enable SPI
        const struct device *cons = DEVICE_DT_GET(DT_NODELABEL(spi1));
        pm_device_action_run(cons, PM_DEVICE_ACTION_RESUME);

        // read data from bma400 fifo
        bma400_get_fifo_data(&fifo_frame, &bma_sensor);
        uint16_t accel_frames_req = FIFO_SAMPLES;
        bma400_extract_accel(&fifo_frame, accel_data, &accel_frames_req, &bma_sensor);

        // after reading, disable the interrupt and put the bma400 to sleep
        int_en.type = BMA400_FIFO_WM_INT_EN;
        int_en.conf = BMA400_DISABLE;
        int8_t rslt = bma400_enable_interrupt(&int_en, 1, &bma_sensor);
        bma400_set_power_mode(BMA400_MODE_SLEEP,&bma_sensor);

        // Disable SPI
        pm_device_action_run(cons, PM_DEVICE_ACTION_SUSPEND);

        // Disable GPIO
        const struct device *cons1 = DEVICE_DT_GET(DT_NODELABEL(gpio0));
        pm_device_action_run(cons1, PM_DEVICE_ACTION_SUSPEND);


        // our accelerometer data is implicitly 8 bits but stored as 16 bits
        // we have 12 bit on the acceleometer 0000 1234 5678 ABCD
        // we grab the top 8 bit (1234 5678) -> 0000 1234 5678 0000, bottom 4 get zeroed out
        // then when we put convert into int16_t we have 0000 1234 5678 0000 (top 4 coulf be 1111 if negative)
        // even though we really only have 8 bits of resolution
        // so when we want to send 8 bits, we need to shift right 4 and grab bottom 8 bits
        // then when we receive, we will shift left back 4
        // Ex: 0x01F0 = 512 = 1G. Even though 512 cannot be stored in 8 bits, the implicit resolution is 8 bits since bottom 4 always 0
        // i.e. only the middle two hex digits will actually change for positive numbers
        // 0xFE00 = -512 = -1G
        // to transmit, we need to convert back to raw bytes
        // 0x0000 -> 0x07F0 (+), 0 -> 2032 by increments of 16
        // 0x0800 -> 0xFF0 (-), -2048 -> -16 by increments of 16
        for(int i = 0; i < 8; i++)
        {
            if(accel_data[i].x < 0)
            {
                adv_mfg_data.samples[i*3] = (accel_data[i].x + 4096) >> 4;
            }
            else
            {
                adv_mfg_data.samples[i*3] = accel_data[i].x  >> 4;
            }
            if(accel_data[i].y < 0)
            {
                adv_mfg_data.samples[i*3+1] = (accel_data[i].y + 4096) >> 4;
            }
            else
            {
                adv_mfg_data.samples[i*3+1] = accel_data[i].y  >> 4;
            }
            if(accel_data[i].z < 0)
            {
                adv_mfg_data.samples[i*3+2] = (accel_data[i].z + 4096) >> 4;
            }
            else
            {
                adv_mfg_data.samples[i*3+2] = accel_data[i].z  >> 4;
            }
        }
        // if(!got_feed)
        // {
        // 	bt_le_adv_update_data(ad_tx_rx, ARRAY_SIZE(ad_tx_rx), NULL, 0); // update adv data
        // }
        // bt_le_adv_update_data(ad_batteryless, ARRAY_SIZE(ad_batteryless), NULL, 0); // update adv data
        
        // gpio_pin_set_dt(&hen_pin, 1);
        // bt_le_adv_start(adv_param, ad_batteryless, ARRAY_SIZE(ad_batteryless), NULL, 0); // start advertising
        // bt_le_adv_start(adv_param, ad_batteryless, ARRAY_SIZE(ad_batteryless), scan_response_data, ARRAY_SIZE(scan_response_data)); // start advertising
        bt_le_ext_adv_set_data(adv_set, ad_batteryless, ARRAY_SIZE(ad_batteryless),scan_response_data, ARRAY_SIZE(scan_response_data));
        
        struct bt_le_ext_adv_start_param start_param = {
            .timeout = 0,
            .num_events = 1, // Transmit once again
        };
        bt_le_ext_adv_start(adv_set, &start_param);
        // bt_le_ext_adv_start(adv_set, NULL);
        // k_sleep(K_MSEC(18)); // wait at least one cycle
        // // bt_le_adv_stop(); // stop advertising
        // bt_le_ext_adv_stop(adv_set);
        last_tx_done = true;
	}
}

// Need to make sure stack is big enough to run NN code
K_THREAD_DEFINE(thread_read_bma400_id, STACKSIZE*4, thread_read_bma400, NULL, NULL, NULL, THREAD_READ_BMA_PRIORITY, 0, 0);



BMA400_INTF_RET_TYPE read_reg_spi(uint8_t reg_address, uint8_t* data, uint32_t len, void* intf_ptr)
{
	int err;

	/* STEP 4.1 - Set the transmit and receive buffers */
	// When reading the BMA400, the first byte read is a dummy, so we need to read two bytes and interpret the second one
	// For a transceive there are 3 steps:
	//		   |       step 1         | step 2 | step 3
	//	Master | 1[7 bit reg address] |  0x0   |   0x0
	//	Slave  |	     dummy        | dummy  | data from sensor	
	// therefore, if we want to read 1 byte from the sensor, we need to read 3 bytes from the sensor (1 during send, 2 during read)
	// Since the BMA400 API already adds the dummy byte, we only need to add one more byte
	// This extra byte is because the first read happens during the register write, so we need to read again	

	uint8_t tx_buffer = reg_address;
	struct spi_buf tx_spi_buf		= {.buf = (void *)&tx_buffer, .len = 1};
	struct spi_buf_set tx_spi_buf_set 	= {.buffers = &tx_spi_buf, .count = 1};
	struct spi_buf rx_spi_bufs 		= {.buf = rx_buffer, .len = len+1};
	struct spi_buf_set rx_spi_buf_set	= {.buffers = &rx_spi_bufs, .count = 1};
	

	/* STEP 4.2 - Call the transceive function */
	err = spi_transceive_dt(&spispec, &tx_spi_buf_set, &rx_spi_buf_set);
	if (err < 0) {
		LOG_ERR("spi_transceive_dt() failed, err: %d, 0x%02X", err,tx_buffer);
		// return err;
	}

	for(int i = 0; i < len; i++)
	{
		data[i] = rx_buffer[i+1]; // data[0] = dummy byte, data[1] = data
	}

	return 0;
}

BMA400_INTF_RET_TYPE write_reg_spi(uint8_t reg_address, const uint8_t* data, uint32_t len, void* intf_ptr)
{
	int err;

	/* STEP 5.1 - delcare a tx buffer having register address and data */
	// When writing to the BMA400, the first byte read is an adress, so we need to write two bytes
	// For a transceive there are 2 steps:
	//		   |       step 1         | step 2 |
	//	Master | 1[7 bit reg address] |  val   |
	//	Slave  |	     dummy        | dummy  |
	// therefore, if we want to write 1 byte to the sensor, we need to write 2 bytes from the sensor (1 adress, 1 data)
	uint8_t tx_buf[2] = {reg_address, data[0]}; // to write, set the MSB to 0
	struct spi_buf	tx_spi_buf 		= {.buf = tx_buf, .len = len+1};
	struct spi_buf_set tx_spi_buf_set	= {.buffers = &tx_spi_buf, .count = 1};

	/* STEP 5.2 - call the spi_write_dt function with SPISPEC to write buffers */
	err = spi_write_dt(&spispec, &tx_spi_buf_set);
	if (err < 0) {
		LOG_ERR("spi_write_dt() failed, err %d", err);
		return err;
	}

	return 0;
}

void init_fifo_watermark()
{
	conf.type = BMA400_ACCEL;
	int8_t rslt = bma400_get_sensor_conf(&conf, 1, &bma_sensor);

	conf.param.accel.odr = BMA400_ODR_25HZ;
	conf.param.accel.range = BMA400_RANGE_4G;
	conf.param.accel.data_src = BMA400_DATA_SRC_ACCEL_FILT_1;

	rslt = bma400_set_sensor_conf(&conf, 1, &bma_sensor);

	fifo_conf.type = BMA400_FIFO_CONF;

	rslt = bma400_get_device_conf(&fifo_conf, 1, &bma_sensor);

	fifo_conf.param.fifo_conf.conf_regs = BMA400_FIFO_8_BIT_EN | BMA400_FIFO_X_EN 
										| BMA400_FIFO_Y_EN 
										| BMA400_FIFO_Z_EN
										| BMA400_FIFO_AUTO_FLUSH;   // flush on power mode change
	fifo_conf.param.fifo_conf.conf_status = BMA400_ENABLE;
	fifo_conf.param.fifo_conf.fifo_watermark = FIFO_WATERMARK_LEVEL;
	fifo_conf.param.fifo_conf.fifo_wm_channel = BMA400_INT_CHANNEL_1;

	rslt = bma400_set_device_conf(&fifo_conf, 1, &bma_sensor);

	fifo_frame.data = fifo_buff;
	fifo_frame.length = FIFO_SIZE;

	int_en.type = BMA400_FIFO_WM_INT_EN;
	int_en.conf = BMA400_DISABLE;

	bma400_set_power_mode(BMA400_MODE_LOW_POWER,&bma_sensor);
	rslt = bma400_enable_interrupt(&int_en, 1, &bma_sensor);
}

void init_activity()
{
	settings.type = BMA400_GEN1_INT;
	bma400_get_sensor_conf(&settings, 1, &bma_sensor);

	settings.param.gen_int.int_chan = BMA400_INT_CHANNEL_1;
    settings.param.gen_int.axes_sel = BMA400_AXIS_XYZ_EN;
    settings.param.gen_int.data_src = BMA400_DATA_SRC_ACC_FILT2;
	settings.param.gen_int.criterion_sel = BMA400_ACTIVITY_INT;
	settings.param.gen_int.evaluate_axes = BMA400_ANY_AXES_INT;
    settings.param.gen_int.ref_update = BMA400_UPDATE_EVERY_TIME;
	settings.param.gen_int.hysteresis = BMA400_HYST_48_MG;
	settings.param.gen_int.gen_int_thres = 0x10;
	settings.param.gen_int.gen_int_dur = 15;

	bma400_set_sensor_conf(&settings, 1, &bma_sensor);

	int_en.type = BMA400_GEN1_INT_EN;
	int_en.conf = BMA400_ENABLE;

	bma400_set_power_mode(BMA400_MODE_NORMAL,&bma_sensor);
	bma400_enable_interrupt(&int_en, 1, &bma_sensor);
}

void init_read_lp()
{
	conf.type = BMA400_ACCEL;
	int8_t rslt = bma400_get_sensor_conf(&conf, 1, &bma_sensor);

	conf.param.accel.odr = BMA400_ODR_25HZ;
	conf.param.accel.range = BMA400_RANGE_4G;
	conf.param.accel.data_src = BMA400_DATA_SRC_ACCEL_FILT_1;
	conf.param.accel.osr_lp = BMA400_ACCEL_OSR_SETTING_0;
	conf.param.accel.int_chan = BMA400_INT_CHANNEL_1;

	rslt = bma400_set_sensor_conf(&conf, 1, &bma_sensor);

	int_en.type = BMA400_DRDY_INT_EN;
	int_en.conf = BMA400_ENABLE;

	bma400_set_power_mode(BMA400_MODE_LOW_POWER,&bma_sensor);
	bma400_enable_interrupt(&int_en, 1, &bma_sensor);
}



static void timer0_handler(struct k_timer *dummy)
{
    // set the semaphore
    k_sem_give(&run_policy);
}

void thread_run_policy(void)
{
    while(1)
    {
        k_sem_take(&run_policy, K_FOREVER); // Sleep here if semaphore is at 0
        static int val_mv;
        // 1. Read the ADC and convert to uJ
        // LOG_INF("---------- Time: %d ----------",current_time);
		const struct device *cons2 = adc_channel.dev;
        pm_device_action_run(cons2, PM_DEVICE_ACTION_RESUME);
        int8_t err = adc_read(adc_channel.dev, &sequence);
        if (err < 0) {
            LOG_ERR("Could not read (%d)", err);
        }
        val_mv = (int)adc_buf;
        err = adc_raw_to_millivolts_dt(&adc_channel, &val_mv);
        // val_mv = val_mv*4; // scale by voltage divider ratio
        // LOG_INF("1. Read ADC: %d mv, scaled: %d mv", val_mv, val_mv*15/10);

		// normal batteryless operation
		if(val_mv >= 1550)
		{
			const struct device *cons = DEVICE_DT_GET(DT_NODELABEL(spi1));
            pm_device_action_run(cons, PM_DEVICE_ACTION_RESUME);
			const struct device *cons1 = DEVICE_DT_GET(DT_NODELABEL(gpio0));
            pm_device_action_run(cons1, PM_DEVICE_ACTION_RESUME);

            int_en.type = BMA400_FIFO_WM_INT_EN;
            int_en.conf = BMA400_ENABLE;
            bma400_set_power_mode(BMA400_MODE_NORMAL,&bma_sensor);
            bma400_enable_interrupt(&int_en, 1, &bma_sensor);
            pm_device_action_run(cons, PM_DEVICE_ACTION_SUSPEND);
            last_tx_done = false;
		}
    }
}
K_THREAD_DEFINE(thread_run_policy_id, STACKSIZE, thread_run_policy, NULL, NULL, NULL, THREAD_RUN_POLICY_PRIORITY, 0, 0);



int main(void)
{
	// Sleep for a second to avoid dying on start
	k_sleep(K_MSEC(1000));

	int err;

	// =================== BLE
	// Fix the BLE address
	bt_addr_le_t addr;
    err = bt_addr_le_from_str(SENSOR_ID, "random", &addr);
    err = bt_id_create(&addr, NULL);

	// Enable BLE
    err = bt_enable(NULL);
    if (err) {
        LOG_ERR("Bluetooth init failed (err %d)\n", err);
        return -1;
    }

    bt_addr_le_t central_id;
    err = bt_addr_le_from_str(CENTRAL_ID_ADDR_STR, "random", &central_id);
    err = hci_add_dev_to_resolving_list(&central_id, central_irk);
    err = hci_set_addr_resolution_enable(true);
    err = bt_le_filter_accept_list_add(&central_id);


	// struct bt_le_adv_param adv_param_ = BT_LE_ADV_PARAM_INIT(
    //     BT_LE_ADV_OPT_SCANNABLE | 
	// 	BT_LE_ADV_OPT_USE_IDENTITY |
	// 	BT_LE_ADV_OPT_NOTIFY_SCAN_REQ,
    //     32,
    //     33,
    //     NULL
    // );

    struct bt_le_adv_param adv_param_ = BT_LE_ADV_PARAM_INIT(
        BT_LE_ADV_OPT_SCANNABLE |
        BT_LE_ADV_OPT_USE_IDENTITY |
        BT_LE_ADV_OPT_NOTIFY_SCAN_REQ |
        BT_LE_ADV_OPT_FILTER_SCAN_REQ,   /* <-- added */
        32,
        33,
        NULL
    );

	// bt_le_ext_adv_create(&adv_param, &adv_callbacks, &adv_set);
	bt_le_ext_adv_create(&adv_param_, &adv_callbacks, &adv_set);
	
	// =================== SPI
	/* STEP 10.1 - Check if SPI and GPIO devices are ready */
	err = spi_is_ready_dt(&spispec);
	if (!err) {
		LOG_ERR("Error: SPI device is not ready, err: %d", err);
		return 0;
	}
	bma400_init(&bma_sensor);
    init_fifo_watermark();
    const struct device *cons = DEVICE_DT_GET(DT_NODELABEL(spi1));
    pm_device_action_run(cons, PM_DEVICE_ACTION_SUSPEND);

	// =================== GPIO for bma_int
    if (!device_is_ready(int_pin.port)) {
        return -1;
    }
    err = gpio_pin_configure_dt(&int_pin, GPIO_INPUT);
    if (err < 0) {
        return -1;
    }
    /* STEP 3 - Configure the interrupt on the button's pin */
    err = gpio_pin_interrupt_configure_dt(&int_pin, GPIO_INT_EDGE_RISING);
    /* STEP 6 - Initialize the static struct gpio_callback variable   */
    gpio_init_callback(&int_cb_data, bma_int_handler, BIT(int_pin.pin));
    /* STEP 7 - Add the callback function by calling gpio_add_callback()   */
    gpio_add_callback(int_pin.port, &int_cb_data);
    // Need to reenable the gpio when we start the bma
    const struct device *cons1 = DEVICE_DT_GET(DT_NODELABEL(gpio0));
    pm_device_action_run(cons1, PM_DEVICE_ACTION_SUSPEND);


	// =================== ADC
	sequence.buffer = &adc_buf;
	sequence.buffer_size = sizeof(adc_buf);

	/* STEP 3.3 - validate that the ADC peripheral (SAADC) is ready */
	if (!adc_is_ready_dt(&adc_channel)) {
		LOG_ERR("ADC controller devivce %s not ready", adc_channel.dev->name);
		return 0;
	}
	/* STEP 3.4 - Setup the ADC channel */
	err = adc_channel_setup_dt(&adc_channel);
	if (err < 0) {
		LOG_ERR("Could not setup channel #%d (%d)", 0, err);
		return 0;
	}
	/* STEP 4.2 - Initialize the ADC sequence */
	err = adc_sequence_init_dt(&adc_channel, &sequence);
	if (err < 0) {
		LOG_ERR("Could not initalize sequnce");
		return 0;
	}
	const struct device *cons2 = adc_channel.dev;
    pm_device_action_run(cons2, PM_DEVICE_ACTION_SUSPEND);
	
	// Start the policy
	k_timer_start(&timer0, K_MSEC(500), K_MSEC(500));

	while(1){
		k_sleep(K_FOREVER);
	}

	return 0;
}