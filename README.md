# What This Branch Does
- This is the basic data sending application for batteryless beacon
- *** To receive this data, use the scan_beacon branch which runs on the DK
- Batteryless sensor firmware to transmit data from BMA400 opportunistically
- When the voltage on Cap > thresh (sensed by ADC at 5Hz), we set off the BMA400
- When the fifo fills to 8 samples (320ms), we read it, then advertise a BLE packet
- We also set the BLE address in main()

# Software Config
- Logging disabled in prj.conf

# Hardware Config
- Uses pinout of new PCB in .overlay 

# Random Notes
