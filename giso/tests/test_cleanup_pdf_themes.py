from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OLD=('simple','classic','modern','luxury3d','hair_market','beauty_ai')
def test_analysis_download_stack_removed():
 assert not (ROOT/'giso/analysis_image.py').exists();assert not (ROOT/'giso/templates/pdf_analysis.html').exists()
 source=(ROOT/'giso/analysis.py').read_text(encoding='utf-8')
 for x in ('download_checklist_pdf','download_full_pdf','download_quick_solution_pdf','download_pdf','analysis_report_image','reportlab','pdf_analysis'):assert x not in source
 assert 'reportlab' not in (ROOT/'requirements.txt').read_text()
def test_retired_theme_selectors_removed():
 css=''.join((ROOT/f).read_text(encoding='utf-8') for f in ('giso/static/css/themes.css','giso/static/css/theme_experiences.css'))
 html=(ROOT/'giso/templates/index.html').read_text(encoding='utf-8')
 for theme in OLD:
  assert f'data-theme="{theme}"' not in css
  assert f"site_theme == '{theme}'" not in html
 assert css.count('{')==css.count('}')
if __name__=='__main__':test_analysis_download_stack_removed();test_retired_theme_selectors_removed()
