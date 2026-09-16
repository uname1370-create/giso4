from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_contract():
 s=(ROOT/'bot_edu/handlers.py').read_text();assert 'site_temp_link_main' in s and 'site_temp_link_giso' in s;assert 'ADMIN_IDS' in s
 assert "consume('giso',token)" in (ROOT/'giso/app.py').read_text();assert "consume('main',token)" in (ROOT/'web/app.py').read_text()
def test_one_time():
 from maintenance_access import create,consume,revoke
 t=create('test','1');assert consume('test',t);assert not consume('test',t)
 t=create('test','1');revoke('test');assert not consume('test',t)
if __name__=='__main__':test_contract();test_one_time()
