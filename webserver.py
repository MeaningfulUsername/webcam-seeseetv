from flask import Flask, send_from_directory, redirect, url_for
import cv2
import time
import os

app = Flask(__name__)
IMAGE_DIR = os.path.join(app.root_path, 'images')
os.makedirs(IMAGE_DIR, exist_ok=True)

@app.route('/')
def index():
    return "hi"

@app.route('/home')
def home():
    latest_filename = os.listdir("images")[-1]
    img_tag = f'<img src="/images/{latest_filename}" />'    
    return f'''
    <!DOCTYPE html>
    <html>
        <head>
            <title>SeeSeeTV</title>
        </head>
        <body>
            <h1>Latest Capture</h1>
            {img_tag}
            <br><br>
            <form action="/capture" method="post">
                <button type="submit">Capture</button>
            </form>
        </body>
    </html>
    '''

@app.route('/capture', methods=['POST'])
def capture():
    global latest_filename
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return "Cannot access camera", 500

    ret, frame = cap.read()
    cap.release()

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2000)
