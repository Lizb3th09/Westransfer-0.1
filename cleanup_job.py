import schedule
import time
import os
from database import get_db_connection
from datetime import datetime
import threading

def cleanup_expired_files():
    """Eliminar archivos expirados automáticamente"""
    print("🔄 Ejecutando limpieza de archivos expirados...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Buscar archivos expirados
    cur.execute('''
        SELECT token, storage_path FROM files 
        WHERE expires_at < NOW() AND is_active = TRUE
    ''')
    
    expired_files = cur.fetchall()
    
    for file in expired_files:
        # Eliminar archivo físico
        try:
            if os.path.exists(file['storage_path']):
                os.remove(file['storage_path'])
                print(f"🗑️ Eliminado: {file['storage_path']}")
        except Exception as e:
            print(f"❌ Error eliminando archivo: {e}")
        
        # Actualizar estado en BD
        cur.execute('''
            UPDATE files SET is_active = FALSE 
            WHERE token = %s
        ''', (file['token'],))
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"✅ Limpieza completada. {len(expired_files)} archivos eliminados.")

def start_cleanup_scheduler():
    """Iniciar scheduler en segundo plano"""
    # Ejecutar cada hora
    schedule.every(1).hours.do(cleanup_expired_files)
    
    # Ejecutar  al iniciar
    cleanup_expired_files()
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
   
    cleanup_thread = threading.Thread(target=start_cleanup_scheduler, daemon=True)
    cleanup_thread.start()
    print("🧹 Job de limpieza iniciado")
    
   
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Deteniendo job de limpieza...")