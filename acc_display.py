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
BUFFER_SECONDS = 30#60
UPDATE_INTERVAL_MS = 50  # update every 100 ms

# -----------------------
# Initialize serial
# -----------------------
ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)

# -----------------------
# Initialize data buffers
# -----------------------
data_buffer_x = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_y = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_z = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
time_buffer = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))

start_time = time.time()

# -----------------------
# Set up the plot
# -----------------------
fig, ax = plt.subplots()
line_x, = ax.plot([], [], lw=2, marker='o', markersize=4, linestyle='-')  # add marker='o' for dots
line_y, = ax.plot([], [], lw=2, marker='o', markersize=4, linestyle='-')  # add marker='o' for dots
line_z, = ax.plot([], [], lw=2, marker='o', markersize=4, linestyle='-')  # add marker='o' for dots
ax.set_xlim(0, BUFFER_SECONDS)
ax.set_ylim(-4.5, 4.5)  # adjust based on your sensor/data range
ax.set_xlabel("Time (s)")
ax.set_ylabel("Accelerometer G's")
ax.set_title("Accelerometer Over Time")
ax.axhline(1,linestyle='--',c='k',lw=8,alpha=0.2)
ax.axhline(-1,linestyle='--',c='r',lw=8,alpha=0.2)
ax.grid()

# -----------------------
# Update function
# -----------------------
def update(frame):
    # Read line from serial
    try:
        line_data = ser.readline().decode('utf-8').strip()
        # print(line_data)
        if len(line_data) == 0:
            return line_x,line_y,line_z
        # else:
        line_data = line_data.split('app: ')[1][:5]
        if line_data == 'START':
            print("")
            read_bytes = np.zeros(24)
            for i in range(24):
                read_byte = ser.readline().decode('utf-8').strip()
                read_byte = read_byte.split('app: ')[1][:2]
                raw_byte = int(read_byte, 16) << 4
                if raw_byte > 2047:
                    read_bytes[i] = raw_byte - 4096
                else:
                    read_bytes[i] = raw_byte
            read_bytes = read_bytes*8/4096
            # print(read_bytes)
            print("X:",read_bytes[0::3])
            print("Y:",read_bytes[1::3])
            print("Z:",read_bytes[2::3])
        # print(line_data)
        # if line_data:
        #     value = float(int(line_data,16))*1.5/1000  # convert to float
        #     print(line_data,value)
            current_time = time.time() - start_time
            data_buffer_x.extend(list(read_bytes[0::3]))
            data_buffer_y.extend(list(read_bytes[1::3]))
            data_buffer_z.extend(list(read_bytes[2::3]))
            time_buffer.extend(list(current_time - np.linspace(0,.32,8)[::-1]))
            # print(list(time_buffer)[-8:])
            # print(data_buffer_x)
            # print(data_buffer_y)
            # print(data_buffer_z)
            # print(time_buffer)
    except Exception as e:
        print("Error reading serial:", e)

    # Update plot data
    if time_buffer:
        time_data = list(time_buffer)
        line_x.set_data(time_data, list(data_buffer_x))
        line_y.set_data(time_data, list(data_buffer_y))
        line_z.set_data(time_data, list(data_buffer_z))
        # print(len(line_x.get_ydata()),len(line_y.get_ydata()),len(line_z.get_ydata()))
        # print(len(line_x.get_xdata()),len(line_y.get_xdata()),len(line_z.get_xdata()))
        # exit()

        # Sliding X-axis: always show last BUFFER_SECONDS seconds
        if time_data[-1] > BUFFER_SECONDS:
            ax.set_xlim(time_data[-1]-BUFFER_SECONDS, time_data[-1])
        else:
            ax.set_xlim(0, BUFFER_SECONDS)

        # Optionally auto-scale y-axis:
        # ax.set_ylim(min(y_data)-0.1, max(y_data)+0.1)

    return line_x, line_y, line_z


# -----------------------
# Animate
# -----------------------
ani = animation.FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS, blit=False)

plt.show()

# -----------------------
# Clean up on exit
# -----------------------
ser.close()
