import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import time

# -----------------------
# Configuration
# -----------------------
COM_PORT = 'COM7'
BAUD_RATE = 115200
BUFFER_SECONDS = 120
UPDATE_INTERVAL_MS = 50  # update every 100 ms

# -----------------------
# Initialize serial
# -----------------------
ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0.1)

# -----------------------
# Initialize data buffers
# -----------------------
data_buffer = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
time_buffer = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))

start_time = time.time()

# -----------------------
# Set up the plot
# -----------------------
fig, ax = plt.subplots()
line, = ax.plot([], [], lw=2, marker='o', markersize=4, linestyle='-')  # add marker='o' for dots
ax.set_xlim(0, BUFFER_SECONDS)
ax.set_ylim(2.1, 2.8)  # adjust based on your sensor/data range
ax.set_xlabel("Time (s)")
ax.set_ylabel("Voltage on Capacitor")
ax.set_title("Voltage Over Time")
ax.axhline(2.2,linestyle='--',c='r',lw=8,alpha=0.2)
ax.axhline(2.7,linestyle='--',c='g',lw=8,alpha=0.2)
ax.grid()

# -----------------------
# Update function
# -----------------------
def update(frame):
    # Read line from serial
    try:
        line_data = ser.readline().decode('utf-8').strip()
        if len(line_data) == 0:
            return line,
        line_data = line_data.split('app: ')[1][:4]
        if line_data:
            value = float(int(line_data,16))*1.5/1000  # convert to float
            print(line_data,value)
            current_time = time.time() - start_time
            data_buffer.append(value)
            time_buffer.append(current_time)
    except Exception as e:
        print("Error reading serial:", e)

    # Update plot data
    if time_buffer:
        x_data = list(time_buffer)
        y_data = list(data_buffer)
        line.set_data(x_data, y_data)

        # Sliding X-axis: always show last BUFFER_SECONDS seconds
        if x_data[-1] > BUFFER_SECONDS:
            ax.set_xlim(x_data[-1]-BUFFER_SECONDS, x_data[-1])
        else:
            ax.set_xlim(0, BUFFER_SECONDS)

        # Optionally auto-scale y-axis:
        # ax.set_ylim(min(y_data)-0.1, max(y_data)+0.1)

    return line,


# -----------------------
# Animate
# -----------------------
ani = animation.FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS, blit=False)

plt.show()

# -----------------------
# Clean up on exit
# -----------------------
ser.close()
