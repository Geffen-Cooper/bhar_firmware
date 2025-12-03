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
BUFFER_SECONDS = 10#60
UPDATE_INTERVAL_MS = 50  # update every 100 ms

# -----------------------
# Initialize serial
# -----------------------
ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)

# -----------------------
# Initialize data buffers
# -----------------------
data_buffer_x_1 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_y_1 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_z_1 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))

data_buffer_x_2 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_y_2 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_z_2 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))

time_buffer1 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
time_buffer2 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))

start_time = time.time()

# -----------------------
# Set up the plot
# -----------------------
fig, ax = plt.subplots(2,1,sharex=True)
line_x_1, = ax[0].plot([], [], lw=2, marker='o', markersize=4, linestyle='-',label='X')  # add marker='o' for dots
line_y_1, = ax[0].plot([], [], lw=2, marker='o', markersize=4, linestyle='-',label='y')  # add marker='o' for dots
line_z_1, = ax[0].plot([], [], lw=2, marker='o', markersize=4, linestyle='-',label='Z')  # add marker='o' for dots

line_x_2, = ax[1].plot([], [], lw=2, marker='o', markersize=4, linestyle='-',label='X')  # add marker='o' for dots
line_y_2, = ax[1].plot([], [], lw=2, marker='o', markersize=4, linestyle='-',label='Y')  # add marker='o' for dots
line_z_2, = ax[1].plot([], [], lw=2, marker='o', markersize=4, linestyle='-',label='Z')  # add marker='o' for dots

ax[1].set_xlim(0, BUFFER_SECONDS)

ax[0].set_ylim(-4.5, 4.5)  # adjust based on your sensor/data range
ax[1].set_ylim(-4.5, 4.5)

ax[1].set_xlabel("Time (s)")

ax[0].set_ylabel("Accelerometer G's")
ax[0].set_title("Accelerometer Over Time")
ax[0].axhline(1,linestyle='--',c='k',lw=4,alpha=0.1,label='1G')
ax[0].axhline(-1,linestyle='--',c='r',lw=4,alpha=0.1,label='-1G')
ax[0].grid()

ax[1].set_ylabel("Accelerometer G's")
ax[1].axhline(1,linestyle='--',c='k',lw=4,alpha=0.1,label='1G')
ax[1].axhline(-1,linestyle='--',c='r',lw=4,alpha=0.1,label='-1G')
ax[1].grid()

ax[0].legend(loc="center left", bbox_to_anchor=(1, 0.5))
ax[1].legend(loc="center left", bbox_to_anchor=(1, 0.5))

# -----------------------
# Update function
# -----------------------
def update(frame):
    # Read line from serial
    try:
        line_data = ser.readline().decode('utf-8').strip()
        # print(line_data)
        if len(line_data) == 0:
            return line_x_1,line_y_1,line_z_1,line_x_2,line_y_2,line_z_2
        # else:
        line_data = line_data.split('app: ')[1][:7]
        # if line_data == 'START':
        if 'START' in line_data:
            # print(line_data.split('START')[1])
            sensor_id = line_data.split('START')[1]
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
            print("Sensor:",sensor_id)
            print("X:",read_bytes[0::3])
            print("Y:",read_bytes[1::3])
            print("Z:",read_bytes[2::3])
        # print(line_data)
        # if line_data:
        #     value = float(int(line_data,16))*1.5/1000  # convert to float
        #     print(line_data,value)
            current_time = time.time() - start_time
            if sensor_id == 'AA':
                data_buffer_x_1.append(np.nan)
                data_buffer_y_1.append(np.nan)
                data_buffer_z_1.append(np.nan)
                time_buffer1.append(np.nan)
                data_buffer_x_1.extend(list(read_bytes[0::3]))
                data_buffer_y_1.extend(list(read_bytes[1::3]))
                data_buffer_z_1.extend(list(read_bytes[2::3]))
                time_buffer1.extend(list(current_time - np.linspace(0,.32,8)[::-1]))
            elif sensor_id == 'AB':
                data_buffer_x_2.append(np.nan)
                data_buffer_y_2.append(np.nan)
                data_buffer_z_2.append(np.nan)
                time_buffer2.append(np.nan)
                data_buffer_x_2.extend(list(read_bytes[0::3]))
                data_buffer_y_2.extend(list(read_bytes[1::3]))
                data_buffer_z_2.extend(list(read_bytes[2::3]))
                time_buffer2.extend(list(current_time - np.linspace(0,.32,8)[::-1]))
            # print(list(time_buffer)[-8:])
            # print(data_buffer_x)
            # print(data_buffer_y)
            # print(data_buffer_z)
            # print(time_buffer)
    except Exception as e:
        print("Error reading serial:", e)

    # Update plot data
    if time_buffer1:
        time_data = list(time_buffer1)
        line_x_1.set_data(time_data, list(data_buffer_x_1))
        line_y_1.set_data(time_data, list(data_buffer_y_1))
        line_z_1.set_data(time_data, list(data_buffer_z_1))
        # print(len(line_x.get_ydata()),len(line_y.get_ydata()),len(line_z.get_ydata()))
        # print(len(line_x.get_xdata()),len(line_y.get_xdata()),len(line_z.get_xdata()))
        # exit()

        # # Sliding X-axis: always show last BUFFER_SECONDS seconds
        # if time_data[-1] > BUFFER_SECONDS:
        #     ax[0].set_xlim(time_data[-1]-BUFFER_SECONDS, time_data[-1])
        #     ax[1].set_xlim(time_data[-1]-BUFFER_SECONDS, time_data[-1])
        # else:
        #     ax[0].set_xlim(0, BUFFER_SECONDS)
        #     ax[1].set_xlim(0, BUFFER_SECONDS)

    if time_buffer2:
        time_data = list(time_buffer2)
        line_x_2.set_data(time_data, list(data_buffer_x_2))
        line_y_2.set_data(time_data, list(data_buffer_y_2))
        line_z_2.set_data(time_data, list(data_buffer_z_2))
        # print(len(line_x.get_ydata()),len(line_y.get_ydata()),len(line_z.get_ydata()))
        # print(len(line_x.get_xdata()),len(line_y.get_xdata()),len(line_z.get_xdata()))
        # exit()

        # # Sliding X-axis: always show last BUFFER_SECONDS seconds
        # if time_data[-1] > BUFFER_SECONDS:
        #     ax[0].set_xlim(time_data[-1]-BUFFER_SECONDS, time_data[-1])
        #     ax[1].set_xlim(time_data[-1]-BUFFER_SECONDS, time_data[-1])
        # else:
        #     ax[0].set_xlim(0, BUFFER_SECONDS)
        #     ax[1].set_xlim(0, BUFFER_SECONDS)
    
    if time_buffer1 or time_buffer2:
        # Sliding X-axis: always show last BUFFER_SECONDS seconds
        # time_data = list(time_buffer2) if len(list(time_buffer2)) > len(list(time_buffer1)) else list(time_buffer1)
        # if time_data[-1] > BUFFER_SECONDS:
        #     # ax[0].set_xlim(time_data[-1]-BUFFER_SECONDS, time_data[-1])
        #     ax[0].set_xlim(time_data[-1]-BUFFER_SECONDS, time_data[-1])
        # else:
        #     # ax[0].set_xlim(0, BUFFER_SECONDS)
        #     ax[0].set_xlim(0, BUFFER_SECONDS)
        time_data1 = list(time_buffer1)
        time_data2 = list(time_buffer2)
        if len(time_data1) == 0:
            most_recent = time_data2[-1]
        elif len(time_data2) == 0:
            most_recent = time_data1[-1]
        else:
            most_recent = max(time_data1[-1],time_data2[-1])
        if most_recent > BUFFER_SECONDS:
            ax[0].set_xlim(most_recent-BUFFER_SECONDS, most_recent)
            ax[1].set_xlim(most_recent-BUFFER_SECONDS, most_recent)
        else:
            ax[0].set_xlim(0, BUFFER_SECONDS)
            ax[1].set_xlim(0, BUFFER_SECONDS)


    return line_x_1, line_y_1, line_z_1, line_x_2, line_y_2, line_z_2


# -----------------------
# Animate
# -----------------------
ani = animation.FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS, blit=False)

plt.show()

# -----------------------
# Clean up on exit
# -----------------------
ser.close()
