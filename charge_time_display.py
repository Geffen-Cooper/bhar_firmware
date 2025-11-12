import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import time
import numpy as np

# -----------------------
# Configuration
# -----------------------
COM_PORT = 'COM7'
BAUD_RATE = 115200
BUFFER_SECONDS = 60
UPDATE_INTERVAL_MS = 100  # update every 100 ms
HIST_BINS = 10  # number of bins in histogram
MAX_SAMPLES = 1000  # number of inter-arrival samples to keep

# -----------------------
# Initialize serial
# -----------------------
ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)

# -----------------------
# Initialize data buffers
# -----------------------
arrival_deltas = deque(maxlen=MAX_SAMPLES)
last_packet_time = None

# -----------------------
# Set up the plot
# -----------------------
fig, ax = plt.subplots()
bars = None
ax.set_title("Live Packet Arrival Time Histogram")
ax.set_xlabel("Inter-packet Time (ms)")
ax.set_ylabel("Frequency")
ax.grid(True)

# -----------------------
# Update function
# -----------------------
def update(frame):
    global last_packet_time, bars

    try:
        line_data = ser.readline().decode('utf-8').strip()
        if not line_data:
            return bars

        now = time.time()
        if last_packet_time is not None:
            delta_t = (now - last_packet_time) * 1000.0  # ms
            if delta_t > 800 and delta_t < 6000:
                arrival_deltas.append(delta_t)
        last_packet_time = now
        print(line_data,delta_t)

    except Exception as e:
        print("Error reading serial:", e)
        return bars

    # Clear and redraw histogram
    ax.cla()
    ax.set_title("Live Packet Arrival Time Histogram")
    ax.set_xlabel("Inter-packet Time (ms)")
    ax.set_ylabel("Frequency")
    ax.grid(True)

    if len(arrival_deltas) > 1:
        ax.hist(arrival_deltas, bins=HIST_BINS, color='skyblue', edgecolor='black')
        ax.set_xlim(0, max(5, np.percentile(arrival_deltas, 99)))  # auto-adjust upper range

    return bars

# -----------------------
# Animate
# -----------------------
ani = animation.FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS, blit=False)

plt.show()

# -----------------------
# Clean up on exit
# -----------------------
print(arrival_deltas)
np.save("charge_times_ms.npy",np.array(list(arrival_deltas)))
ser.close()
