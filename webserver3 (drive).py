from flask import Flask, send_from_directory, redirect, url_for, Response, render_template, jsonify
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


import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# Authenticate User for Google Drive
SCOPES = ["https://www.googleapis.com/auth/drive"]

creds = None
if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
else:
    flow = InstalledAppFlow.from_client_secrets_file(
        "creds.json", SCOPES
    )
    creds = flow.run_local_server(port=0)
with open("token.json", "w") as token:
    token.write(creds.to_json())


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
                if camera.isOpened():
                    print("Camera ready.")
                else:
                    print("Failed to open camera.")
        time.sleep(2)

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/home')
def home():
    return f'''
    <!DOCTYPE html>
    <html>
        <head><title>SeeSeeTV</title></head>
        <body>
            <h1>Live Video</h1>
            <img height="200" src="/video_feed" />
            <h1>Last Capture</h1>
            <img src="/last_image" height="200" />
            <form action="/capture" method="post">
                <button>Capture</button>
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
        #SAVE IMAGE (LOCAL)
        timestamp = int(time.time())
        filename = f'SeeSeeTV_{timestamp}.jpg'
        filepath = os.path.join(IMAGE_DIR, filename)
        cv2.imwrite(filepath, frame)

        #SAVE IMAGE (GOOGLE DRIVE)
        try:
            service = build("drive", "v3", credentials=creds)

            # CALL GOOGLE API
            folder_id = get_or_create_folder(service, "SEESEETV")

            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            media = MediaFileUpload(filepath, mimetype='image/*')
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            print(f"File ID: {file.get('id')}")
            return jsonify({"image": filepath})
                
        except HttpError as error:
            return jsonify({"error": "HttpError occurred"})
    
    else:
        return jsonify({"error": "Failed to capture image"})

@app.route('/last_image')
def uploaded_file():
    images = os.listdir("images")
    if images:
        return send_from_directory(IMAGE_DIR, images[-1])
    else:
        return ""

@app.route('/video_feed')
def video_feed():
    global active_viewers
    active_viewers += 1
    print(f"Viewer connected: {active_viewers}")
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def generate_frames():
    global active_viewers
    if active_viewers == 1:
        time.sleep(3)
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

def get_or_create_folder(service, folder_name):
    # Search for folder
    results = service.files().list(
        q=f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false",
        spaces='drive',
        fields="files(id, name)").execute()
    items = results.get('files', [])

    if items:
        print(f"Found folder '{folder_name}' with ID: {items[0]['id']}")
        return items[0]['id']
    else:
        # Create folder
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        print(f"Created folder '{folder_name}' with ID: {folder.get('id')}")
        return folder.get('id')


# Run camera manager thread before starting Flask
if __name__ == '__main__':
    threading.Thread(target=camera_manager, daemon=True).start()
    app.run(host='0.0.0.0', port=2000)
