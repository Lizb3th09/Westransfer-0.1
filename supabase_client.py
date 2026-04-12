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
            except Exception as e:
                print(f"⚠️ Error conectando a Supabase: {e}")
                self.client = None
        else:
            print("⚠️ Supabase no configurado - funcionando solo con PostgreSQL")
    
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
            return True
            
        try:
            with open(file_path, 'rb') as f:
                self.client.storage.from_('files').upload(
                    f'{token}/{os.path.basename(file_path)}',
                    f
                )
            print(f"☁️ Archivo respaldado en Storage")
            return True
        except Exception as e:
            print(f"⚠️ Error en storage: {e}")
            return False

supabase_mgr = SupabaseManager()