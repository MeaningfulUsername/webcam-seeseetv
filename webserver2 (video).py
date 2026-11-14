from flask import Flask, send_from_directory, redirect, url_for, Response
import cv2
import time
import os
import threading

app = Flask(__name__)
IMAGE_DIR = os.path.join(app.root_path, 'images')
os.makedirs(IMAGE_DIR, exist_ok=True)

camera = None
active_viewers = 0
camera_lock = threading.Lock()
camera_ready_event = threading.Event()

def camera_manager():
    global camera, active_viewers
    while True:
        with camera_lock:
            if active_viewers == 0 and camera:
                print("Releasing camera")
                camera.release()
                camera = None
            elif active_viewers > 0 and not camera:
                print("Starting camera")
                camera = cv2.VideoCapture(0)
                time.sleep(0.5)  # Let the camera warm up
                if camera.isOpened():
                    print("Camera ready.")
                    camera_ready_event.set()
                else:
                    print("Failed to open camera.")
                    camera_ready_event.clear()
                    
        time.sleep(1)

@app.route('/home')
def home():
    latest_images = os.listdir("images")
    latest_filename = latest_images[-1] if latest_images else ""
    img_tag = f'<img src="/images/{latest_filename}" />' if latest_filename else "No image captured yet."

    return f'''
    <!DOCTYPE html>
    <html>
        <head><title>SeeSeeTV</title></head>
        <body>
            <h1>Live Video</h1>
            <img width="500" src="/video_feed" />
            <h1>Last Capture</h1>
            {img_tag}
            <form action="/capture" method="post">
                <button type="submit">Capture</button>
            </form>
        </body>
    </html>
    '''

@app.route('/capture', methods=['POST'])
def capture():
    global camera
    with camera_lock:
        if not camera or not camera.isOpened():
            return "Cannot access camera", 500
        ret, frame = camera.read()
    if ret:
        timestamp = int(time.time())
        filename = f'SeeSeeTV_{timestamp}.jpg'
        filepath = os.path.join(IMAGE_DIR, filename)
        cv2.imwrite(filepath, frame)
        return redirect(url_for('home'))
    else:
        return "Failed to capture image", 500

@app.route('/images/<filename>')
def uploaded_file(filename):
    return send_from_directory(IMAGE_DIR, filename)

@app.route('/video_feed')
def video_feed():
    global active_viewers
    active_viewers += 1
    print(f"Viewer connected: {active_viewers}")
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def generate_frames():
    global active_viewers
    try:
        while True:
            with camera_lock:
                if not camera or not camera.isOpened():
                    break
                success, frame = camera.read()
            if not success:
                break
            _, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    finally:
        active_viewers -= 1
        print(f"Viewer disconnected: {active_viewers}")

# Run camera manager thread before starting Flask
if __name__ == '__main__':
    threading.Thread(target=camera_manager, daemon=True).start()
    app.run(host='0.0.0.0', port=2000)
