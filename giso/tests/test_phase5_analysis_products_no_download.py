from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_analysis_ui_has_no_download_actions():
 files=list((ROOT/'giso/templates').glob('analysis*.html'))+[ROOT/'giso/templates/dashboard_analyses.html',ROOT/'giso/panel_user/templates/user_modules/analyses.html']
 for p in files:
  s=p.read_text(encoding='utf-8');assert 'دانلود PDF' not in s;assert 'دانلود تصویر' not in s
def test_site_analysis_page_does_not_compute_unused_products():
 s=(ROOT/'giso/panel_user/modules/analyses.py').read_text(encoding='utf-8')
 assert 'get_recommendation_for_user' not in s and 'analysis_products' not in s

if __name__=='__main__':test_analysis_ui_has_no_download_actions();test_product_cards_are_explanatory()
