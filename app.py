import os
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, render_template, url_for
from flask_cors import CORS
import qrcode
from werkzeug.security import generate_password_hash, check_password_hash

# --- Initialization and Configuration ---
app = Flask(__name__, template_folder='.')
CORS(app)

UPLOAD_FOLDER = 'uploads'
QR_FOLDER = 'qrcodes'
USERS_FILE = 'users.txt'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(QR_FOLDER):
    os.makedirs(QR_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['QR_FOLDER'] = QR_FOLDER

if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'w') as f:
        pass

# --- In-Memory Database Simulation ---
file_database = {}

# --- HTML Page Routes ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login.html')
def login_page():
    return render_template('login.html')

@app.route('/feedback.html')
def feedback_page():
    return render_template('feedback.html')

@app.route('/scanner.html')
def scanner_page():
    return render_template('scanner.html')
    
@app.route('/profile.html')
def profile_page():
    return render_template('profile.html')

@app.route('/qr_code.html')
def qr_code_page():
    return render_template('qr_code.html')

# --- CSS File Routes ---
@app.route('/style.css')
def style_css():
    return send_file('style.css')

@app.route('/login_style.css')
def login_style_css():
    return send_file('login_style.css')
    
@app.route('/feedback_style.css')
def feedback_style_css():
    return send_file('feedback_style.css')

@app.route('/profile_style.css')
def profile_style_css():
    return send_file('profile_style.css')

# --- API Endpoints ---
def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'png', 'jpg', 'jpeg', 'dicom'}

# --- Authentication Routes ---
@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')

    if not all([name, email, password, role]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    with open(USERS_FILE, 'r') as f:
        for line in f:
            if line.split(':')[0] == email:
                return jsonify({'success': False, 'message': 'User with this email already exists'}), 409

    hashed_password = generate_password_hash(password)

    with open(USERS_FILE, 'a') as f:
        f.write(f"{email}:{hashed_password}:{name}:{role}\n")

    return jsonify({'success': True, 'message': 'Account created successfully!'}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({'success': False, 'message': 'Missing email or password'}), 400

    with open(USERS_FILE, 'r') as f:
        for line in f:
            parts = line.strip().split(':')
            if len(parts) < 4: continue

            stored_email = parts[0]
            role = parts[-1]
            name = parts[-2]
            stored_hash = ":".join(parts[1:-2])

            if stored_email == email and check_password_hash(stored_hash, password):
                return jsonify({
                    'success': True, 
                    'message': 'Login successful!',
                    'user': {
                        'name': name,
                        'email': email,
                        'role': role
                    }
                }), 200

    return jsonify({'success': False, 'message': 'Invalid email or password'}), 401


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        unique_filename = secrets.token_hex(16) + os.path.splitext(file.filename)[1]
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        access_token = secrets.token_urlsafe(16)
        expiration_time = datetime.utcnow() + timedelta(minutes=30)
        
        file_database[access_token] = {
            'file_name': file.filename,
            'file_path': file_path,
            'expiration': expiration_time
        }

        qr_data = url_for('download_file', token=access_token, _external=True)
        
        img = qrcode.make(qr_data)
        qr_code_filename = f'{access_token}.png'
        qr_code_path = os.path.join(app.config['QR_FOLDER'], qr_code_filename)
        img.save(qr_code_path)

        # *** MODIFIED RESPONSE: Send a direct download URL for the QR code ***
        qr_download_url = url_for('download_qr_code', filename=qr_code_filename, _external=True)

        return jsonify({
            'message': 'File uploaded successfully',
            'download_qr_url': qr_download_url,
            'original_filename': file.filename
        }), 200
    else:
        return jsonify({'error': 'File type not allowed'}), 400

@app.route('/download_qr/<path:filename>')
def download_qr_code(filename):
    return send_file(os.path.join(app.config['QR_FOLDER'], filename), as_attachment=True)

@app.route('/download/<token>')
def download_file(token):
    record = file_database.get(token)
    if not record or datetime.utcnow() > record['expiration']:
        return jsonify({'error': 'Invalid or expired token'}), 401
    return send_file(record['file_path'], as_attachment=True, download_name=record['file_name'])

if __name__ == '__main__':
    app.run(debug=True, port=5000)