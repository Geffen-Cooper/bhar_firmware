# What This Branch Does
- This is the basic data **receiving** application for batteryless beacon scanning
- *** The firmware runs on the central DK and receives data from beacons which use the opp_beacon branch
- The DK firmware scans for beacons with BLE address ending in AA,AB,AC,AD,AE
- It then dumps the data in the advertising packet to the serial port
- Then acc_display.py (run on laptop), reads this data from the serial and displays to matplotlib

# Software Config
- Logging happens over RTT or serial for debugging

# Hardware Config
- This uses the default DK .overlay with no modifications

# Random Notes
- If want to have more than 5 beacons to scan, need to add filter in prj.conf and main.c