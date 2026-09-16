from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_master_toggle_reaches_all_collectors():
 settings=(ROOT/'giso/monitoring_settings.py').read_text();assert "'master'" in settings and "data.get('master',True)" in settings
 for name,key in [('monitoring_errors.py','errors'),('login_history.py','login_history'),('monitoring_events.py','behavior'),('broadcasts.py','broadcasts'),('monitoring_ai.py','ai_reports')]:
  s=(ROOT/'giso'/name).read_text();assert f"enabled('{key}')" in s,(name,key)
def test_idle_work_is_reduced():
 bot=(ROOT/'giso/bot.py').read_text();assert "interval=60" in bot
 assert 'TTL=45' in (ROOT/'giso/monitoring_settings.py').read_text()
 assert '_SCHEMA_READY' in (ROOT/'giso/broadcasts.py').read_text()
 assert '_SCHEMA_READY' in (ROOT/'giso/monitoring_events.py').read_text()
def test_panel_has_master_control():
 h=(ROOT/'giso/panel/templates/modules/monitoring.html').read_text();assert 'name="master"' in h and 'کل پایش هوشمند' in h
if __name__=='__main__':test_master_toggle_reaches_all_collectors();test_idle_work_is_reduced();test_panel_has_master_control()
