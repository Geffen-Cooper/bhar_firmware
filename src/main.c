/*
 * Copyright (c) 2024 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/logging/log.h>
/* STEP 3.1 - Include the header file of the Zephyr ADC API */
#include <zephyr/drivers/adc.h>

/* STEP 3.2 - Define a variable of type adc_dt_spec for each channel */
static const struct adc_dt_spec adc_channel = ADC_DT_SPEC_GET(DT_PATH(zephyr_user));

LOG_MODULE_REGISTER(Lesson6_Exercise1, LOG_LEVEL_DBG);

int main(void)
{
	int err;
	uint32_t count = 0;

	/* STEP 4.1 - Define a variable of type adc_sequence and a buffer of type uint16_t */
	int16_t buf;
	struct adc_sequence sequence = {
		.buffer = &buf,
		/* buffer size in bytes, not number of samples */
		.buffer_size = sizeof(buf),
		// Optional
		//.calibrate = true,
	};

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

	#define buffer_size 10
	int power_vals[buffer_size] = {0};
	int count_idx = 0;
	int avg_power = 0;
	int last_mv = -1;
	bool buffer_full = 0;
	while (1) {
		int val_mv;

		/* STEP 5 - Read a sample from the ADC */
		err = adc_read(adc_channel.dev, &sequence);
		if (err < 0) {
			LOG_ERR("Could not read (%d)", err);
			continue;
		}
		

		val_mv = (int)buf;
		LOG_INF("ADC reading[%u]: %s, channel %d: Raw: %d", count++, adc_channel.dev->name,
			adc_channel.channel_id, val_mv);

		/* STEP 6 - Convert raw value to mV*/
		err = adc_raw_to_millivolts_dt(&adc_channel, &val_mv);
		/* conversion to mV may not be supported, skip if not */
		if (err < 0) {
			LOG_WRN(" (value in mV not available)\n");
		} else {
			LOG_INF("Pre: %d mV, Post: %d mV", val_mv, (val_mv*3)/2);
		}

		if(buffer_full == 0 && count_idx == buffer_size)
		{
			buffer_full = 1;
		}

		if(count_idx == buffer_size)
		{
			count_idx = 0;
		}
		// only received one voltage
		if(last_mv == -1)
		{
			last_mv = val_mv;
		}
		else
		{
			power_vals[count_idx] = ((val_mv*val_mv) - (last_mv*last_mv)) / 2000;
			count_idx += 1;
			last_mv = val_mv;
		}

		if(buffer_full == 1)
		{
			int avg_power = 0;
			for(int i = 0; i < buffer_size; i++)
			{
				avg_power += power_vals[i];
			}
			avg_power = avg_power / buffer_size;
			LOG_INF("Avg Power: %d uW", avg_power);
		}
		k_sleep(K_MSEC(100));
	}
	return 0;
}