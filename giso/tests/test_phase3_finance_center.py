# -*- coding: utf-8 -*-
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_finance_center_is_read_only_aggregation():
 s=(ROOT/'giso/panel/modules/finance_overview.py').read_text(encoding='utf-8')
 for forbidden in ('INSERT INTO','UPDATE ','DELETE FROM','CREATE TABLE','ALTER TABLE'):
  assert forbidden not in s
 for key in ('finance_overview','finance_users','finance_shop','finance_marketplace','finance_beauty','finance_ai','finance_discrepancies'):
  assert key in s

def test_wallet_navigation_exposes_all_views():
 module=(ROOT/'giso/panel/modules/wallet.py').read_text(encoding='utf-8')
 html=(ROOT/'giso/panel/templates/modules/wallet.html').read_text(encoding='utf-8')
 for tab in ('overview','users','shop','marketplace','beauty','ai','discrepancies'):
  assert f'"{tab}"' in module
  assert f"tab='{tab}'" in html
 assert "overview_context()" in module

def test_finance_module_remains_super_only():
 permissions=(ROOT/'giso/panel/permissions.py').read_text(encoding='utf-8')
 assert '"wallet"' in permissions[permissions.index('SUPER_ONLY_MODULES'):]

if __name__=='__main__':
 test_finance_center_is_read_only_aggregation();test_wallet_navigation_exposes_all_views();test_finance_module_remains_super_only()
