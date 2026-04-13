import threading
import subprocess
import time

if __name__ == '__main__':
    print("🚀 Iniciando WeTransfer Clone...")
    
    # Inicializar base de datos
    from database import init_database
    init_database()
    
    # Iniciar job de limpieza en segundo plano
    from cleanup_job import start_cleanup_scheduler
    cleanup_thread = threading.Thread(target=start_cleanup_scheduler, daemon=True)
    cleanup_thread.start()
    
    # Iniciar API
    from app import app
    print("📡 API disponible en http://localhost:5000")
    print("📤 Endpoints:")
    print("   POST /upload - Subir archivo")
    print("   GET /download/{token} - Descargar archivo")
    print("   GET /file/{token} - Info archivo")
    print("   DELETE /file/{token} - Eliminar archivo")
    
    app.run(debug=False, host='0.0.0.0', port=5000)