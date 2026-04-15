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
    """Generar token seguro"""
    return uuid.uuid4().hex + hashlib.sha256(os.urandom(32)).hexdigest()[:16]

def validate_file(file):
    """Validar archivo (tamaño, tipo, seguridad)"""
    # Validar tamaño
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Archivo demasiado grande. Máximo: {MAX_FILE_SIZE/1024/1024}MB")
    
    # Validar MIME type usando filetype
    header = file.read(261)
    file.seek(0)
    
    kind = filetype.guess(header)
    if kind is None:
        mime_type = 'application/octet-stream'
    else:
        mime_type = kind.mime
    
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Tipo de archivo no permitido: {mime_type}")
    
    # Prevenir path traversal
    filename = secure_filename(file.filename)
    if '..' in filename or filename.startswith('/'):
        raise ValueError("Nombre de archivo inválido")
    
    return mime_type

def get_supabase_public_url(token, original_name):
    """Genera la URL pública de Supabase para un archivo"""
    import urllib.parse
    supabase_url = os.getenv('SUPABASE_URL', '')
    
    # Codificar el nombre original por si tiene espacios
    clean_name = urllib.parse.quote(original_name)
    
    # IMPORTANTE: El archivo se guarda como {token}_{nombre}
    file_name = f"{token}_{clean_name}"
    
    # Generar URL completa (carpeta token + archivo con token_nombre)
    return f"{supabase_url}/storage/v1/object/public/files/{token}/{file_name}"

# ========== ENDPOINTS ==========

@app.route('/upload', methods=['POST'])
def upload_file():
    """POST /upload - Subir archivo"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400
        
        # Validar archivo
        mime_type = validate_file(file)
        
        # Generar token único
        token = generate_token()
        
        # Guardar archivo temporalmente
        original_name = secure_filename(file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, f"{token}_{original_name}")
        file.save(save_path)
        
        # Configurar expiración (24 horas por defecto)
        expires_in_hours = int(request.form.get('expires_in', 24))
        expires_at = datetime.now() + timedelta(hours=expires_in_hours)
        
        # Guardar en PostgreSQL (principal)
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            INSERT INTO files (filename, original_name, file_size, mime_type, token, expires_at, storage_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (save_path, original_name, os.path.getsize(save_path), mime_type, token, expires_at, save_path))
        
        file_id = cur.fetchone()['id']
        conn.commit()
        
        # Respaldar metadata en Supabase
        supabase_mgr.backup_metadata({
            'token': token,
            'filename': save_path,
            'original_name': original_name,
            'file_size': os.path.getsize(save_path),
            'expires_at': expires_at.isoformat()
        })
        
        # Subir archivo a Supabase Storage
        supabase_mgr.upload_to_storage(save_path, token)
        
        # Registrar log en Supabase
        supabase_mgr.log_activity(
            'UPLOAD', 
            token, 
            request.remote_addr, 
            request.headers.get('User-Agent')
        )
        
        cur.close()
        conn.close()
        
        # Generar enlace de descarga desde Supabase (público)
        download_url = get_supabase_public_url(token, original_name)
        
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
    """GET /download/{token} - Redirigir a la descarga desde Supabase"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Buscar archivo en PostgreSQL
        cur.execute('''
            SELECT original_name, token FROM files 
            WHERE token = %s AND is_active = TRUE AND expires_at > NOW()
        ''', (token,))
        
        file_record = cur.fetchone()
        
        if not file_record:
            supabase_mgr.log_activity('DOWNLOAD_FAILED', token, request.remote_addr, request.headers.get('User-Agent'))
            return jsonify({'error': 'File not found or expired'}), 404
        
        # Actualizar contador de descargas
        cur.execute('''
            UPDATE files SET download_count = download_count + 1
            WHERE token = %s
        ''', (token,))
        conn.commit()
        
        # Registrar log en Supabase
        supabase_mgr.log_activity(
            'DOWNLOAD', 
            token, 
            request.remote_addr, 
            request.headers.get('User-Agent')
        )
        
        cur.close()
        conn.close()
        
        # Redirigir a la URL pública de Supabase
        supabase_url = os.getenv('SUPABASE_URL')
        file_path = f"{token}/{file_record['original_name']}"
        supabase_file_url = f"{supabase_url}/storage/v1/object/public/files/{file_path}"
        
        return redirect(supabase_file_url, code=302)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/file/<token>', methods=['GET'])
def file_info(token):
    """GET /file/{token} - Información del archivo"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT original_name, file_size, mime_type, download_count, 
                   created_at, expires_at, is_active
            FROM files 
            WHERE token = %s
        ''', (token,))
        
        file_record = cur.fetchone()
        cur.close()
        conn.close()
        
        if not file_record:
            return jsonify({'error': 'File not found'}), 404
        
        return jsonify({
            'filename': file_record['original_name'],
            'size': file_record['file_size'],
            'mime_type': file_record['mime_type'],
            'downloads': file_record['download_count'],
            'uploaded_at': file_record['created_at'].isoformat(),
            'expires_at': file_record['expires_at'].isoformat(),
            'is_active': file_record['is_active']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/file/<token>', methods=['DELETE'])
def delete_file(token):
    """DELETE /file/{token} - Eliminar archivo"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Obtener ruta del archivo
        cur.execute('SELECT storage_path FROM files WHERE token = %s', (token,))
        result = cur.fetchone()
        
        if result:
            # Eliminar archivo físico local
            try:
                os.remove(result['storage_path'])
            except:
                pass
            
            # Eliminar en DB
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
    return jsonify({'status': 'healthy', 'database': 'postgresql + supabase'})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)