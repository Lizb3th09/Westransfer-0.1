from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class SupabaseManager:
    def __init__(self):
        self.url = os.getenv('SUPABASE_URL', '')
        self.key = os.getenv('SUPABASE_KEY', '')
        self.client = None
        
        if self.url and self.key:
            try:
                self.client: Client = create_client(self.url, self.key)
                print("✅ Supabase conectado")
                # Verificar que el bucket existe
                self._check_bucket()
            except Exception as e:
                print(f"⚠️ Error conectando a Supabase: {e}")
                self.client = None
        else:
            print("⚠️ Supabase no configurado - funcionando solo con PostgreSQL")
    
    def _check_bucket(self):
        """Verificar que el bucket 'files' existe"""
        try:
            buckets = self.client.storage.list_buckets()
            bucket_names = [b.name for b in buckets]
            if 'files' in bucket_names:
                print("✅ Bucket 'files' encontrado")
            else:
                print("⚠️ Bucket 'files' no existe - créalo en el dashboard")
        except Exception as e:
            print(f"⚠️ Error verificando bucket: {e}")
    
    def backup_metadata(self, file_data):
        """Respaldar metadata en Supabase"""
        if not self.client:
            return True
            
        try:
            data = {
                'token': file_data['token'],
                'filename': file_data['filename'],
                'original_name': file_data['original_name'],
                'file_size': file_data['file_size'],
                'expires_at': file_data['expires_at'],
                'backup_date': datetime.now().isoformat()
            }
            
            self.client.table('file_backup').insert(data).execute()
            print(f"✅ Metadata respaldada: {file_data['token']}")
            return True
        except Exception as e:
            print(f"⚠️ Error en backup: {e}")
            return False
    
    def log_activity(self, action, file_token, ip, user_agent):
        """Registrar logs en Supabase"""
        if not self.client:
            return True
            
        try:
            log_data = {
                'action': action,
                'file_token': file_token,
                'ip_address': ip,
                'user_agent': user_agent,
                'timestamp': datetime.now().isoformat()
            }
            
            self.client.table('activity_logs_supabase').insert(log_data).execute()
            print(f"📝 Log registrado: {action}")
            return True
        except Exception as e:
            print(f"⚠️ Error en log: {e}")
            return False
    
    def upload_to_storage(self, file_path, token):
        """Subir archivo a Supabase Storage"""
        if not self.client:
            print("⚠️ No hay cliente de Supabase")
            return False
            
        try:
            # Verificar que el archivo existe
            if not os.path.exists(file_path):
                print(f"❌ El archivo no existe: {file_path}")
                return False
            
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            storage_path = f"{token}/{file_name}"
            
            print(f"📤 Subiendo a Storage: {storage_path} ({file_size} bytes)")
            
            with open(file_path, 'rb') as f:
                result = self.client.storage.from_('files').upload(
                    storage_path,
                    f,
                    {"content-type": "application/octet-stream"}
                )
            
            print(f"☁️ Archivo subido exitosamente a Storage")
            print(f"   Ruta: {storage_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error detallado en storage:")
            print(f"   Tipo: {type(e).__name__}")
            print(f"   Mensaje: {e}")
            import traceback
            traceback.print_exc()
            return False

supabase_mgr = SupabaseManager()