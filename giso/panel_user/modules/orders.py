# -*- coding: utf-8 -*-
"""خریدهای فروشگاه و امکان ویرایش محدود سفارش COD در انتظار."""
from giso.panel_user.modules._base import get_shop_orders,get_stock_notifies
from giso.models import ShopCheckout,ShopInvoice


def context():
    orders=get_shop_orders();ids={o.checkout_id for o in orders if o.checkout_id}
    checkouts={row.id:row for row in ShopCheckout.query.filter(ShopCheckout.id.in_(ids)).all()} if ids else {}
    invoices={row.checkout_id:row for row in ShopInvoice.query.filter(ShopInvoice.checkout_id.in_(ids)).all()} if ids else {}
    editable={cid:bool(c.status=='placed' and not c.wallet_used and not c.discount_amount) for cid,c in checkouts.items()}
    return {"orders":orders,"stock_notifies":get_stock_notifies(),"checkout_map":checkouts,"invoice_map":invoices,"editable_checkouts":editable}
