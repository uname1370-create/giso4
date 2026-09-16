# -*- coding: utf-8 -*-
"""Single Persian vocabulary for analysis metrics across site, bot and images."""
METRIC_LABELS={
'hydration':'رطوبت','elasticity':'انعطاف‌پذیری','strength':'استحکام','shine':'درخشندگی',
'scalp_health':'سلامت پوست سر','growth_rate':'وضعیت رشد','density':'تراکم','porosity':'تخلخل مو',
'damage':'میزان آسیب','oiliness':'چربی','sensitivity':'حساسیت','acne':'جوش','texture':'بافت پوست',
'health':'سلامت کلی','dryness':'خشکی','hair_loss':'ریزش مو','dandruff':'شوره سر',
}
def metric_label(key,value=None):
 if isinstance(value,dict) and value.get('label'):return str(value['label'])
 raw=str(key or '').strip();return METRIC_LABELS.get(raw.lower(),raw.replace('_',' '))
