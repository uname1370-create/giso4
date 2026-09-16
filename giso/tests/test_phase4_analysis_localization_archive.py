# -*- coding: utf-8 -*-
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_metric_dictionary_is_shared_by_online_panel():
 labels=(ROOT/'giso/analysis_labels.py').read_text(encoding='utf-8');module=(ROOT/'giso/panel_user/modules/analyses.py').read_text(encoding='utf-8')
 for key in ('hydration','elasticity','strength','shine','scalp_health','growth_rate'):assert f"'{key}'" in labels
 assert 'metric_label' in module
 assert 'to_shamsi(row.created_at)' in module
 assert "'hydration':'رطوبت'" in labels and "'scalp_health':'سلامت پوست سر'" in labels
def test_archive_has_restore_and_no_delete():
 routes=(ROOT/'giso/panel_user/routes.py').read_text(encoding='utf-8');html=(ROOT/'giso/panel_user/templates/user_modules/analyses.html').read_text(encoding='utf-8')
 assert 'def analysis_restore' in routes and 'row.archived_at=""' in routes
 assert "tab=='archive'" in html and 'بازیابی آنالیز' in html
if __name__=='__main__':test_metric_dictionary_is_shared_by_online_panel();test_archive_has_restore_and_no_delete()
