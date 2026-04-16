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
                self._check_bucket()
            except Exception as e:
                print(f"⚠️ Error conectando a Supabase: {e}")
                self.client = None
        else:
            print("⚠️ Supabase no configurado - funcionando solo con PostgreSQL")
    
    def _check_bucket(self):
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
        if not self.client:
            print("⚠️ No hay cliente de Supabase")
            return False
        try:
            if not os.path.exists(file_path):
                print(f"❌ El archivo no existe: {file_path}")
                return False
            
            file_name = os.path.basename(file_path)
            storage_path = f"{token}/{file_name}"
            
            print(f"📤 Subiendo a Storage: {storage_path}")
            
            with open(file_path, 'rb') as f:
                self.client.storage.from_('files').upload(
                    storage_path,
                    f,
                    {"content-type": "application/octet-stream"}
                )
            
            print(f"☁️ Archivo subido exitosamente a Storage")
            return True
        except Exception as e:
            print(f"❌ Error en storage: {e}")
            return False
        
    def get_signed_url(self, token, original_name, expires_in=3600):
        """Genera URL firmada de Supabase (expira por defecto en 1 hora)"""
        if not self.client:
            return None
        try:
            file_path = f"{token}/{token}_{original_name}"
            print(f"🔗 Generando URL firmada para: {file_path}")
            response = self.client.storage.from_('files').create_signed_url(file_path, expires_in)
            return response['signedURL']
        except Exception as e:
            print(f"⚠️ Error generando URL firmada: {e}")
            return None

supabase_mgr = SupabaseManager()