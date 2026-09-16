import sqlite3,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_reset_contract_and_template_buttons():
 r=(ROOT/'giso/panel/routes.py').read_text();h=(ROOT/'giso/panel/templates/modules/monitoring.html').read_text()
 assert '@require_super\ndef monitoring_reset' in r and "request.form.get('confirm')!='RESET'" in r
 for scope in ('errors','behavior','security','broadcasts','ai_reports'):assert f"reset_report('{scope}')" in h
def test_reset_scopes_keep_active_campaigns():
 import giso.monitoring_reset as m
 p=Path(tempfile.gettempdir())/'giso_reset_test.db';p.unlink(missing_ok=True)
 def conn():c=sqlite3.connect(p);c.row_factory=sqlite3.Row;return c
 with conn() as c:
  c.executescript("CREATE TABLE giso_system_errors(id INTEGER);INSERT INTO giso_system_errors VALUES(1);CREATE TABLE giso_ux_events(id INTEGER);INSERT INTO giso_ux_events VALUES(1);CREATE TABLE giso_login_events(id INTEGER);INSERT INTO giso_login_events VALUES(1);CREATE TABLE giso_monitoring_ai_reports(id INTEGER);INSERT INTO giso_monitoring_ai_reports VALUES(1);CREATE TABLE giso_broadcast_campaigns(id INTEGER,status TEXT);CREATE TABLE giso_broadcast_recipients(id INTEGER,campaign_id INTEGER);INSERT INTO giso_broadcast_campaigns VALUES(1,'completed'),(2,'sending');INSERT INTO giso_broadcast_recipients VALUES(1,1),(2,2);")
 m.get_giso_db_conn=conn
 for scope in ('errors','behavior','security','ai_reports'):assert m.reset(scope)[0]
 assert m.reset('broadcasts')[2]==1
 with conn() as c:assert c.execute('SELECT COUNT(*) FROM giso_broadcast_campaigns WHERE id=2').fetchone()[0]==1;assert c.execute('SELECT COUNT(*) FROM giso_broadcast_recipients WHERE campaign_id=2').fetchone()[0]==1
 p.unlink(missing_ok=True)
if __name__=='__main__':test_reset_contract_and_template_buttons();test_reset_scopes_keep_active_campaigns()
