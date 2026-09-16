# -*- coding: utf-8 -*-
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_beauty_notification_category_routes_to_admin_and_super():
 from giso.panel.modules.notifications import DEFAULT_CATEGORY_SETTINGS
 assert DEFAULT_CATEGORY_SETTINGS['beauty_centers']=={'target_role':'both','enabled':1,'destination':'both','title':'مراکز زیبایی'}

def test_center_request_status_report_and_message_hooks_exist():
 service=(ROOT/'giso/beauty_centers/services.py').read_text(encoding='utf-8')
 routes=(ROOT/'giso/beauty_centers/routes.py').read_text(encoding='utf-8')
 for marker in ('notify_center_admins(center)','notify_center_owner(updated','notify_conversation_message(conversation','category="beauty_centers"'):
  assert marker in service
 assert 'safe_log("beauty_centers", "report"' in routes

def test_admin_bale_review_buttons_and_owner_deep_links_exist():
 service=(ROOT/'giso/beauty_centers/services.py').read_text(encoding='utf-8')
 for callback in ('bc_act|{center_id}|review','bc_act|{center_id}|publish','bc_act|{center_id}|reject'):
  assert callback in service
 assert '/dashboard/beauty-center?tab=messages' in service
 assert '/beauty-centers/{conversation[' in service
