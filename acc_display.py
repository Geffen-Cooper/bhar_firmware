import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import RadioButtons
from collections import deque
import time
import numpy as np

# -----------------------
# Configuration
# -----------------------
COM_PORT = 'COM11'
BAUD_RATE = 115200
BUFFER_SECONDS = 10
UPDATE_INTERVAL_MS = 10

# -----------------------
# Initialize serial
# -----------------------
ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0.1)

# -----------------------
# Initialize data buffers
# -----------------------
data_buffer_x_1 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_y_1 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_z_1 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))

data_buffer_x_2 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_y_2 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_z_2 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))

data_buffer_x_3 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_y_3 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_z_3 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))

data_buffer_x_4 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_y_4 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
data_buffer_z_4 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))

time_buffer1 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
time_buffer2 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
time_buffer3 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))
time_buffer4 = deque(maxlen=int(BUFFER_SECONDS * (1000 / UPDATE_INTERVAL_MS)))

start_time = time.time()

# -----------------------
# Set up the plot
# -----------------------
fig, ax = plt.subplots(4, 1, sharex=True, figsize=(10, 8))

line_x_1, = ax[0].plot([], [], lw=2, marker='o', markersize=4,
                       linestyle='-', label='X')
line_y_1, = ax[0].plot([], [], lw=2, marker='o', markersize=4,
                       linestyle='-', label='Y')
line_z_1, = ax[0].plot([], [], lw=2, marker='o', markersize=4,
                       linestyle='-', label='Z')

line_x_2, = ax[1].plot([], [], lw=2, marker='o', markersize=4,
                       linestyle='-', label='X')
line_y_2, = ax[1].plot([], [], lw=2, marker='o', markersize=4,
                       linestyle='-', label='Y')
line_z_2, = ax[1].plot([], [], lw=2, marker='o', markersize=4,
                       linestyle='-', label='Z')

line_x_3, = ax[2].plot([], [], lw=2, marker='o', markersize=4,
                       linestyle='-', label='X')
line_y_3, = ax[2].plot([], [], lw=2, marker='o', markersize=4,
                       linestyle='-', label='Y')
line_z_3, = ax[2].plot([], [], lw=2, marker='o', markersize=4,
                       linestyle='-', label='Z')

line_x_4, = ax[3].plot([], [], lw=2, marker='o', markersize=4,
                       linestyle='-', label='X')
line_y_4, = ax[3].plot([], [], lw=2, marker='o', markersize=4,
                       linestyle='-', label='Y')
line_z_4, = ax[3].plot([], [], lw=2, marker='o', markersize=4,
                       linestyle='-', label='Z')

ax[-1].set_xlim(0, BUFFER_SECONDS)

for a in ax:
    a.set_ylim(-3.5, 3.5)

ax[0].set_title("Left Wrist", loc="left", fontweight="bold")
ax[1].set_title("Right Wrist", loc="left", fontweight="bold")
ax[2].set_title("Left Foot", loc="left", fontweight="bold")
ax[3].set_title("Right Foot", loc="left", fontweight="bold")

ax[-1].set_xlabel("Time (s)")

for a in ax:
    a.set_ylabel("G's")
    a.axhline(1, linestyle='--', c='k', lw=4, alpha=0.1)
    a.axhline(-1, linestyle='--', c='r', lw=4, alpha=0.1)

# -----------------------
# Radio buttons
# -----------------------

# Leave some space on the right for the controls
plt.subplots_adjust(right=0.82)

radio_axes = []
radio_buttons = []

sensor_ids = ['A', 'B', 'C', 'D']

# Vertical position of each radio button group
radio_height = 0.13
radio_width = 0.08

for i, sensor_id in enumerate(sensor_ids):

    # Get position of corresponding plot
    pos = ax[i].get_position()

    # Place radio buttons just to the right of the plot
    radio_ax = fig.add_axes([
        0.84,
        pos.y0 + (pos.height - radio_height) / 2,
        radio_width,
        radio_height
    ])

    radio = RadioButtons(
        radio_ax,
        ('0', '1', '2', '3'),
        active=0
    )

    radio_axes.append(radio_ax)
    radio_buttons.append(radio)

    # Callback for this sensor
    def make_callback(sensor):
        def callback(label):
            command = f"{sensor}{label}"
            print(f"Sending: {command}")
            ser.write(command.encode('ascii'))
        return callback

    radio.on_clicked(make_callback(sensor_id))

# -----------------------
# Update function
# -----------------------
def update(frame):

    try:
        line_data = ser.readline().decode('utf-8').strip()

        if len(line_data) == 0:
            return (
                line_x_1, line_y_1, line_z_1,
                line_x_2, line_y_2, line_z_2,
                line_x_3, line_y_3, line_z_3,
                line_x_4, line_y_4, line_z_4
            )

        line_data = line_data.split('app: ')[1][:7]

        if 'START' in line_data:

            sensor_id = line_data.split('START')[1]
            print("")

            data_header = ser.readline()

            data_bytes1 = ser.readline().decode('utf-8').strip()
            data_bytes1 = data_bytes1.split('|')[0].strip()

            data_bytes2 = ser.readline().decode('utf-8').strip()
            data_bytes2 = data_bytes2.split('|')[0].strip()

            byte_list = data_bytes1.split() + data_bytes2.split()

            read_bytes = np.zeros(24)

            for b_i, b in enumerate(byte_list):

                raw_byte = int(b, 16) << 4

                if raw_byte > 2047:
                    value = raw_byte - 4096
                else:
                    value = raw_byte

                read_bytes[b_i] = value

            # Final scaling
            read_bytes = read_bytes * 8 / 4096

            print("Sensor:", sensor_id)
            print("X:", read_bytes[0::3])
            print("Y:", read_bytes[1::3])
            print("Z:", read_bytes[2::3])

            current_time = time.time() - start_time

            if sensor_id == 'AA':

                data_buffer_x_1.append(np.nan)
                data_buffer_y_1.append(np.nan)
                data_buffer_z_1.append(np.nan)
                time_buffer1.append(np.nan)

                data_buffer_x_1.extend(list(read_bytes[0::3]))
                data_buffer_y_1.extend(list(read_bytes[1::3]))
                data_buffer_z_1.extend(list(read_bytes[2::3]))

                time_buffer1.extend(
                    list(current_time - np.linspace(0, .32, 9)[::-1][1:])
                )

            elif sensor_id == 'AB':

                data_buffer_x_2.append(np.nan)
                data_buffer_y_2.append(np.nan)
                data_buffer_z_2.append(np.nan)
                time_buffer2.append(np.nan)

                data_buffer_x_2.extend(list(read_bytes[0::3]))
                data_buffer_y_2.extend(list(read_bytes[1::3]))
                data_buffer_z_2.extend(list(read_bytes[2::3]))

                time_buffer2.extend(
                    list(current_time - np.linspace(0, .32, 9)[::-1][1:])
                )

            elif sensor_id == 'AC':

                data_buffer_x_3.append(np.nan)
                data_buffer_y_3.append(np.nan)
                data_buffer_z_3.append(np.nan)
                time_buffer3.append(np.nan)

                data_buffer_x_3.extend(list(read_bytes[0::3]))
                data_buffer_y_3.extend(list(read_bytes[1::3]))
                data_buffer_z_3.extend(list(read_bytes[2::3]))

                time_buffer3.extend(
                    list(current_time - np.linspace(0, .32, 9)[::-1][1:])
                )

            elif sensor_id == 'AD':

                data_buffer_x_4.append(np.nan)
                data_buffer_y_4.append(np.nan)
                data_buffer_z_4.append(np.nan)
                time_buffer4.append(np.nan)

                data_buffer_x_4.extend(list(read_bytes[0::3]))
                data_buffer_y_4.extend(list(read_bytes[1::3]))
                data_buffer_z_4.extend(list(read_bytes[2::3]))

                time_buffer4.extend(
                    list(current_time - np.linspace(0, .32, 9)[::-1][1:])
                )

    except Exception as e:
        print("Error reading serial:", e)

    # -----------------------
    # Update plot data
    # -----------------------

    if time_buffer1:
        time_data = list(time_buffer1)

        line_x_1.set_data(time_data, list(data_buffer_x_1))
        line_y_1.set_data(time_data, list(data_buffer_y_1))
        line_z_1.set_data(time_data, list(data_buffer_z_1))

    if time_buffer2:
        time_data = list(time_buffer2)

        line_x_2.set_data(time_data, list(data_buffer_x_2))
        line_y_2.set_data(time_data, list(data_buffer_y_2))
        line_z_2.set_data(time_data, list(data_buffer_z_2))

    if time_buffer3:
        time_data = list(time_buffer3)

        line_x_3.set_data(time_data, list(data_buffer_x_3))
        line_y_3.set_data(time_data, list(data_buffer_y_3))
        line_z_3.set_data(time_data, list(data_buffer_z_3))

    if time_buffer4:
        time_data = list(time_buffer4)

        line_x_4.set_data(time_data, list(data_buffer_x_4))
        line_y_4.set_data(time_data, list(data_buffer_y_4))
        line_z_4.set_data(time_data, list(data_buffer_z_4))

    # -----------------------
    # Sliding X-axis
    # -----------------------

    if time_buffer1 or time_buffer2 or time_buffer3 or time_buffer4:

        lists = [
            list(time_buffer1),
            list(time_buffer2),
            list(time_buffer3),
            list(time_buffer4)
        ]

        most_recent = max(
            lst[-1] for lst in lists if len(lst) > 0
        )

        if most_recent > BUFFER_SECONDS:

            for a in ax:
                a.set_xlim(
                    most_recent - BUFFER_SECONDS,
                    most_recent
                )

        else:

            for a in ax:
                a.set_xlim(0, BUFFER_SECONDS)

    return (
        line_x_1, line_y_1, line_z_1,
        line_x_2, line_y_2, line_z_2,
        line_x_3, line_y_3, line_z_3,
        line_x_4, line_y_4, line_z_4
    )


# -----------------------
# Animate
# -----------------------
ani = animation.FuncAnimation(
    fig,
    update,
    interval=UPDATE_INTERVAL_MS,
    blit=True
)

plt.show()

# -----------------------
# Clean up on exit
# -----------------------
ser.close()
