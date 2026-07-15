import cv2
import numpy as np

# Global variables to track mouse state and cropping coordinates
cropping = False
x_start, y_start, x_end, y_end = 0, 0, 0, 0
crop_defined = False

def select_crop_region(event, x, y, flags, param):
    global x_start, y_start, x_end, y_end, cropping, crop_defined

    # Adjust mouse coordinates based on the letterboxing padding
    # so clicking and dragging still aligns perfectly with the image
    if 'pad_left' in param and 'pad_top' in param and 'scale' in param:
        if param['scale'] > 0:
            x = int((x - param['pad_left']) / param['scale'])
            y = int((y - param['pad_top']) / param['scale'])

    if event == cv2.EVENT_LBUTTONDOWN:
        x_start, y_start = x, y
        x_end, y_end = x, y
        cropping = True
        crop_defined = False

    elif event == cv2.EVENT_MOUSEMOVE:
        if cropping:
            x_end, y_end = x, y

    elif event == cv2.EVENT_LBUTTONUP:
        x_end, y_end = x, y
        cropping = False
        if abs(x_start - x_end) > 10 and abs(y_start - y_end) > 10:
            crop_defined = True

# Dictionary to pass dynamic layout scaling parameters to the mouse callback
layout_params = {'pad_left': 0, 'pad_top': 0, 'scale': 1.0}

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

window_name = "Camera Feed"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_name, 600, 950)
cv2.setMouseCallback(window_name, select_crop_region, param=layout_params)

print("Instructions:")
print("- Drag the window edges freely. Your face will no longer stretch!")
print("- Click and drag to crop; press 'r' to reset; press 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Can't receive frame.")
        break

    # Determine which frame matrix to process based on user cropping state
    if cropping:
        display_frame = frame.copy()
        cv2.rectangle(display_frame, (x_start, y_start), (x_end, y_end), (0, 255, 0), 2)
        active_frame = display_frame
    elif crop_defined:
        y1, y2 = sorted([y_start, y_end])
        x1, x2 = sorted([x_start, x_end])
        h, w, _ = frame.shape
        y1, y2 = max(0, y1), min(h, y2)
        x1, x2 = max(0, x1), min(w, x2)
        active_frame = frame[y1:y2, x1:x2]
    else:
        active_frame = frame

    # --- LETTERBOX / ASPECT RATIO ENGINE ---
    # 1. Get the current physical size of the window container on your desktop
    try:
        _, _, win_w, win_h = cv2.getWindowImageRect(window_name)
    except Exception:
        win_w, win_h = 600, 950 # Fallback default if window bounds aren't fully initialized

    # Catch edge case where window is minimized or collapsed
    if win_w <= 0 or win_h <= 0:
        win_w, win_h = 600, 950

    img_h, img_w, _ = active_frame.shape

    # 2. Calculate aspect ratios to determine how to fit the frame
    img_aspect = img_w / img_h
    win_aspect = win_w / win_h

    if img_aspect > win_aspect:
        # Image is wider than the window -> scale by width, pad top/bottom
        scale = win_w / img_w
        new_w = win_w
        new_h = int(img_h * scale)
        pad_left = 0
        pad_top = (win_h - new_h) // 2
    else:
        # Image is taller than the window -> scale by height, pad left/right
        scale = win_h / img_h
        new_w = int(img_w * scale)
        new_h = win_h
        pad_left = (win_w - new_w) // 2
        pad_top = 0

    # 3. Update global parameters so the mouse selection clicks match the image pixels
    layout_params['scale'] = scale
    layout_params['pad_left'] = pad_left
    layout_params['pad_top'] = pad_top

    # 4. Resize the image and construct the final black canvas container
    resized_img = cv2.resize(active_frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((win_h, win_w, 3), dtype=np.uint8) # Blank black window frame
    canvas[pad_top:pad_top+new_h, pad_left:pad_left+new_w] = resized_img

    # Show the undistorted frame inside the canvas window
    cv2.imshow(window_name, canvas)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('r'):
        crop_defined = False
        print("Crop reset to full view.")
    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()