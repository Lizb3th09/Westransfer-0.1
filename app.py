from flask import Flask, request, send_file, jsonify, abort, render_template, redirect
from flask_cors import CORS
import os
import uuid
import hashlib
import filetype
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from database import get_db_connection
from supabase_client import supabase_mgr
import psycopg2
from dotenv import load_dotenv
import io
import requests

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuración
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 104857600))
ALLOWED_MIME_TYPES = [
    'image/jpeg', 'image/png', 'application/pdf',
    'text/plain', 'application/zip', 'video/mp4',
    'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/octet-stream'
]

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def generate_token():
    return uuid.uuid4().hex + hashlib.sha256(os.urandom(32)).hexdigest()[:16]

def validate_file(file):
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Archivo demasiado grande. Máximo: {MAX_FILE_SIZE/1024/1024}MB")
    
    header = file.read(261)
    file.seek(0)
    
    kind = filetype.guess(header)
    if kind is None:
        mime_type = 'application/octet-stream'
    else:
        mime_type = kind.mime
    
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Tipo de archivo no permitido: {mime_type}")
    
    filename = secure_filename(file.filename)
    if '..' in filename or filename.startswith('/'):
        raise ValueError("Nombre de archivo inválido")
    
    return mime_type

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400
        
        mime_type = validate_file(file)
        token = generate_token()
        original_name = secure_filename(file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, f"{token}_{original_name}")
        file.save(save_path)
        
        expires_in_hours = int(request.form.get('expires_in', 24))
        expires_at = datetime.now() + timedelta(hours=expires_in_hours)
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO files (filename, original_name, file_size, mime_type, token, expires_at, storage_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (save_path, original_name, os.path.getsize(save_path), mime_type, token, expires_at, save_path))
        
        conn.commit()
        
        supabase_mgr.backup_metadata({
            'token': token,
            'filename': save_path,
            'original_name': original_name,
            'file_size': os.path.getsize(save_path),
            'expires_at': expires_at.isoformat()
        })
        
        supabase_mgr.upload_to_storage(save_path, token)
        supabase_mgr.log_activity('UPLOAD', token, request.remote_addr, request.headers.get('User-Agent'))
        
        cur.close()
        conn.close()
        
        base_url = f"{request.scheme}://{request.host}"
        download_url = f"{base_url}/download/{token}"
        
        return jsonify({
            'message': 'File uploaded successfully',
            'token': token,
            'download_url': download_url,
            'expires_at': expires_at.isoformat()
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/download/<token>', methods=['GET'])
def download_file(token):
    """GET /download/{token} - Redirigir a URL firmada de Supabase"""
    print(f"🔍 DEBUG: Token recibido = {token}")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT original_name, expires_at FROM files 
            WHERE token = %s AND is_active = TRUE AND expires_at > NOW()
        ''', (token,))
        
        file_record = cur.fetchone()
        
        print(f"🔍 DEBUG: file_record = {file_record}")
        
        if not file_record:
            return jsonify({'error': 'File not found or expired'}), 404
        
        cur.execute('''
            UPDATE files SET download_count = download_count + 1
            WHERE token = %s
        ''', (token,))
        conn.commit()
        
        supabase_mgr.log_activity('DOWNLOAD', token, request.remote_addr, request.headers.get('User-Agent'))
        
        cur.close()
        conn.close()
        
        signed_url = supabase_mgr.get_signed_url(token, file_record['original_name'], 3600)
        
        if not signed_url:
            return jsonify({'error': 'Error generando enlace de descarga'}), 500
        
        return redirect(signed_url, code=302)
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/file/<token>', methods=['DELETE'])
def delete_file(token):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT storage_path FROM files WHERE token = %s', (token,))
        result = cur.fetchone()
        
        if result:
            try:
                os.remove(result['storage_path'])
            except:
                pass
            cur.execute('DELETE FROM files WHERE token = %s', (token,))
            conn.commit()
            supabase_mgr.log_activity('DELETE', token, request.remote_addr, request.headers.get('User-Agent'))
        
        cur.close()
        conn.close()
        return jsonify({'message': 'File deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)