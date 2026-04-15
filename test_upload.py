import os
from supabase_client import supabase_mgr

# 1. Primero, verifica que hay archivos en la carpeta uploads
uploads_dir = "C:/Users/Calab/OneDrive/Escritorio/WeTransfer/uploads"

if os.path.exists(uploads_dir):
    files = os.listdir(uploads_dir)
    print(f"📁 Archivos en uploads: {files}")
    
    if files:
        # Toma el primer archivo
        test_file = os.path.join(uploads_dir, files[0])
        print(f"📄 Probando con: {test_file}")
        
        # Intenta subir
        supabase_mgr.upload_to_storage(test_file, "test_token_123")
    else:
        print("❌ No hay archivos en uploads. Sube uno primero desde la web.")
else:
    print(f"❌ La carpeta {uploads_dir} no existe")