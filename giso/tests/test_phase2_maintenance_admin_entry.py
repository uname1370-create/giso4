# -*- coding: utf-8 -*-
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_giso_private_entry_keeps_real_auth():
 s=(ROOT/'giso/app.py').read_text(encoding='utf-8')
 assert 'GISO_MAINTENANCE_ADMIN_PATH' in s
 assert 'giso_maintenance_entry_until' in s
 assert 'return redirect(url_for("login"))' in s
 assert 'request.path in ("/login", "/admin/verify") and (entry_valid or not _private_admin_path)' in s

def test_main_private_entry_is_short_lived():
 s=(ROOT/'web/app.py').read_text(encoding='utf-8')
 assert 'MAIN_MAINTENANCE_ADMIN_PATH' in s
 assert "max_age=900" in s
 assert "httponly=True" in s and "samesite='Lax'" in s
 assert 'private_token' in s

def test_env_documents_distinct_paths():
 s=(ROOT/'.env.example').read_text(encoding='utf-8')
 assert 'GISO_MAINTENANCE_ADMIN_PATH=' in s
 assert 'MAIN_MAINTENANCE_ADMIN_PATH=' in s

if __name__=='__main__':
 test_giso_private_entry_keeps_real_auth();test_main_private_entry_is_short_lived();test_env_documents_distinct_paths()
