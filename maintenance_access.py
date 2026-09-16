import hashlib,secrets,sqlite3
from datetime import datetime,timedelta
from pathlib import Path
DB=Path(__file__).resolve().parent/'bot_edu'/'data'/'bot.db'
def _conn():
 DB.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute("CREATE TABLE IF NOT EXISTS maintenance_access_tokens(id INTEGER PRIMARY KEY,scope TEXT,token_hash TEXT UNIQUE,expires_at TEXT,used_at TEXT DEFAULT '',created_by TEXT,created_at TEXT)");return c
def create(scope,actor):
 token=secrets.token_urlsafe(32);h=hashlib.sha256(token.encode()).hexdigest();now=datetime.now();c=_conn();c.execute("UPDATE maintenance_access_tokens SET used_at=? WHERE scope=? AND used_at=''",(now.isoformat(' '),scope));c.execute("INSERT INTO maintenance_access_tokens(scope,token_hash,expires_at,created_by,created_at) VALUES(?,?,?,?,?)",(scope,h,(now+timedelta(minutes=10)).isoformat(' '),str(actor),now.isoformat(' ')));c.commit();c.close();return token
def consume(scope,token):
 h=hashlib.sha256(str(token).encode()).hexdigest();c=_conn();c.execute('BEGIN IMMEDIATE');r=c.execute("SELECT id FROM maintenance_access_tokens WHERE scope=? AND token_hash=? AND used_at='' AND expires_at>datetime('now','localtime')",(scope,h)).fetchone();ok=bool(r)
 if ok:c.execute("UPDATE maintenance_access_tokens SET used_at=datetime('now','localtime') WHERE id=?",(r['id'],));c.commit()
 else:c.rollback()
 c.close();return ok
def revoke(scope):
 c=_conn();c.execute("UPDATE maintenance_access_tokens SET used_at=datetime('now','localtime') WHERE scope=? AND used_at=''",(scope,));c.commit();c.close()
