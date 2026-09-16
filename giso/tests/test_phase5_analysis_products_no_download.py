from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_analysis_ui_has_no_download_actions():
 files=list((ROOT/'giso/templates').glob('analysis*.html'))+[ROOT/'giso/templates/dashboard_analyses.html',ROOT/'giso/panel_user/templates/user_modules/analyses.html']
 for p in files:
  s=p.read_text(encoding='utf-8');assert 'دانلود PDF' not in s;assert 'دانلود تصویر' not in s
def test_product_cards_are_explanatory():
 s=(ROOT/'giso/panel_user/templates/user_modules/analyses.html').read_text(encoding='utf-8')
 for x in ('pu-analysis-product-card','image_path','short_description','گفتگو با همراه هوشمند','analysis_products[:3]'):assert x in s
if __name__=='__main__':test_analysis_ui_has_no_download_actions();test_product_cards_are_explanatory()
