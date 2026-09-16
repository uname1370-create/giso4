# -*- coding: utf-8 -*-
from werkzeug.security import generate_password_hash
from giso.app import create_app
from giso.base import get_giso_db_conn
from giso.models import db,User,Product
from giso.wallet import edit_shop_checkout_atomic

PHONE='+989120006622'

def test_cod_pending_checkout_edit_is_atomic_and_wallet_checkout_is_blocked():
    app=create_app()
    with app.app_context():
        user=User.query.filter_by(phone=PHONE).first() or User(phone=PHONE,name='خریدار سفارش',password_hash=generate_password_hash('p'))
        db.session.add(user);db.session.flush()
        p1=Product(name='محصول یک',price=1000,in_stock=True,publish_status='published');p2=Product(name='محصول دو',price=2000,in_stock=True,publish_status='published')
        db.session.add_all([p1,p2]);db.session.commit();uid=user.id;p1id,p2id=p1.id,p2.id
    with get_giso_db_conn() as conn:
        c=conn.execute("INSERT INTO shop_checkouts(user_id,gross_amount,discount_amount,wallet_used,cash_wallet_used,spend_wallet_used,cod_amount,status,created_at) VALUES (?,5000,0,0,0,0,5000,'placed','test')",(uid,));cid=c.lastrowid
        inv=conn.execute("INSERT INTO shop_invoices(invoice_number,checkout_id,user_id,customer_address,gross_amount,discount_amount,payable_amount,wallet_paid_amount,cod_amount,payment_status,created_at) VALUES (?,?,?,'قدیم',5000,0,5000,0,5000,'cod_due','test')",(f'TEST-{cid}',cid,uid));iid=inv.lastrowid
        ids=[]
        for pid,q,price in ((p1id,1,1000),(p2id,2,2000)):
            o=conn.execute("INSERT INTO product_orders(user_id,phone,product_id,checkout_id,invoice_id,address,quantity,status,tracking_code,created_at) VALUES (?,?,?,?,?,'قدیم',?,'pending','T','test')",(uid,PHONE,pid,cid,iid,q));oid=o.lastrowid;ids.append(oid)
            conn.execute("INSERT INTO shop_invoice_items(invoice_id,order_id,product_id,product_name,unit_price,quantity,line_total) VALUES (?,?,?,?,?,?,?)",(iid,oid,pid,'محصول',price,q,price*q))
        conn.commit()
    ok,msg=edit_shop_checkout_atomic(uid,cid,{str(ids[0]):'3',str(ids[1]):'0'},'آدرس جدید','یادداشت','عصر')
    assert ok,msg
    with get_giso_db_conn() as conn:
        checkout=conn.execute('SELECT * FROM shop_checkouts WHERE id=?',(cid,)).fetchone();orders=conn.execute('SELECT * FROM product_orders WHERE checkout_id=?',(cid,)).fetchall();invoice=conn.execute('SELECT * FROM shop_invoices WHERE id=?',(iid,)).fetchone()
        assert checkout['gross_amount']==3000 and checkout['cod_amount']==3000
        assert len(orders)==1 and orders[0]['quantity']==3 and orders[0]['address']=='آدرس جدید'
        assert invoice['payable_amount']==3000 and invoice['customer_address']=='آدرس جدید'
        conn.execute("UPDATE shop_checkouts SET wallet_used=100 WHERE id=?",(cid,));conn.commit()
    assert edit_shop_checkout_atomic(uid,cid,{str(ids[0]):'2'},'آدرس دوم')[0] is False
    with get_giso_db_conn() as conn:
        conn.execute('DELETE FROM shop_invoice_items WHERE invoice_id=?',(iid,));conn.execute('DELETE FROM product_orders WHERE checkout_id=?',(cid,));conn.execute('DELETE FROM shop_invoices WHERE id=?',(iid,));conn.execute('DELETE FROM shop_checkouts WHERE id=?',(cid,));conn.commit()
    with app.app_context(): Product.query.filter(Product.id.in_([p1id,p2id])).delete(synchronize_session=False);User.query.filter_by(id=uid).delete();db.session.commit()
