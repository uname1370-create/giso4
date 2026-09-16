#!/usr/bin/env node
/*
  تست UI مرحله ۱ (اصلاح): displayImageChecks

  سه حالت:
  1) عکس تار (قابل قبول با warning)  -> status-warning + دکمه «تحلیل با همین عکس» + ادامه فعال
  2) عکس صورت به‌جای مو (رد)           -> status-fail + دکمه «عکس جدید» + ادامه غیرفعال
  3) عکس عالی (بدون هشدار)             -> status-ok + ادامه فعال
*/
const fs = require('fs');

function makeEl(id) {
    return {
        id,
        style: {},
        classList: { _s: new Set(), add(c){this._s.add(c);}, remove(c){this._s.delete(c);},
                     contains(c){return this._s.has(c);} },
        innerHTML: '',
        textContent: '',
        querySelector() { return makeEl(id + '-inner'); },
    };
}

function extractFunction(template, name) {
    const html = fs.readFileSync(template, 'utf8');
    const m = html.match(/<script>([\s\S]*?)<\/script>/);
    if (!m) throw new Error('no script in ' + template);
    const src = m[1];
    // پیدا کردن بدنه تابع نام‌برده شده (تا کروشه بستن هم‌تراز)
    const start = src.indexOf('function ' + name);
    if (start < 0) throw new Error('function not found: ' + name);
    let i = src.indexOf('{', start);
    let depth = 0;
    let end = -1;
    for (; i < src.length; i++) {
        if (src[i] === '{') depth++;
        else if (src[i] === '}') { depth--; if (depth === 0) { end = i + 1; break; } }
    }
    return src.slice(start, end);
}

function runTest(template) {
    const fnSrc = extractFunction(template, 'displayImageChecks');
    // بدنه تابع را به‌علاوه فراخوانی آن با result و بازگشت imageValid می‌سازیم
    const fn = new Function(
        'document', 'result', 'imageValid',
        fnSrc + '; displayImageChecks(result); return imageValid;'
    );

    // حالت ۱: تار اما قابل قبول با warning
    {
        const els = {};
        for (const id of ['validationLoading','checkList','checkStatus','continueBtn','checkMessage',
                          'check-natural-light','check-no-filter','check-distance',
                          'check-visible','check-one-person','check-clear']) els[id] = makeEl(id);
        const doc = { getElementById: id => els[id] };
        const blurry = {
            valid: true, quality_score: 60,
            warnings: ['عکس یکم تاره', 'نور می‌تونه بهتر باشه'],
            message: '✅ عکس قابل تحلیله ولی چند نکته هست',
            can_proceed_with_warnings: true,
            checks: { natural_light: true, no_filter: true, good_distance: true,
                      hair_visible: true, one_person: true, clear_image: false },
        };
        fn(doc, blurry, false);

        // چیدمان درست: عنوان → نکات → (تیک‌ها) → دکمه‌ها فقط در پایین (بدون دکمه وسط)
        const ok =
            els['checkStatus'].innerHTML.includes('status-warning') &&
            els['checkStatus'].innerHTML.includes('نکات') &&
            !els['checkStatus'].innerHTML.includes('proceedAnyway()') &&
            !els['checkStatus'].innerHTML.includes('action-buttons') &&
            !els['continueBtn'].classList.contains('disabled');
        console.log((ok ? 'PASS' : 'FAIL') + '  blurry-accept-with-warnings: ' + template);
        if (!ok) throw new Error('blurry accept render failed');
    }

    // حالت ۲: صورت به‌جای مو -> رد
    {
        const els = {};
        for (const id of ['validationLoading','checkList','checkStatus','continueBtn','checkMessage',
                          'check-natural-light','check-no-filter','check-distance',
                          'check-visible','check-one-person','check-clear']) els[id] = makeEl(id);
        const doc = { getElementById: id => els[id] };
        const reject = {
            valid: false, reason_code: 'not_hair',
            message: '❌ این عکس مو نیست',
            checks: { hair_visible: false },
        };
        fn(doc, reject, false);
        // چیدمان درست: فقط پیام رد + ادامه غیرفعال (دکمه «عکس جدید» در پایین است)
        const ok =
            els['checkStatus'].innerHTML.includes('status-fail') &&
            els['checkStatus'].innerHTML.includes('این عکس مو نیست') &&
            !els['checkStatus'].innerHTML.includes('action-buttons') &&
            els['continueBtn'].classList.contains('disabled');
        console.log((ok ? 'PASS' : 'FAIL') + '  reject-not-hair: ' + template);
        if (!ok) throw new Error('reject render failed');
    }

    // حالت ۳: عالی بدون هشدار
    {
        const els = {};
        for (const id of ['validationLoading','checkList','checkStatus','continueBtn','checkMessage',
                          'check-natural-light','check-no-filter','check-distance',
                          'check-visible','check-one-person','check-clear']) els[id] = makeEl(id);
        const doc = { getElementById: id => els[id] };
        const great = { valid: true, quality_score: 92, warnings: [],
                        message: '✨ عکس عالیه!', checks: {} };
        fn(doc, great, false);
        const ok =
            els['checkStatus'].innerHTML.includes('status-ok') &&
            !els['checkStatus'].innerHTML.includes('status-warning') &&
            !els['continueBtn'].classList.contains('disabled');
        console.log((ok ? 'PASS' : 'FAIL') + '  great-no-warnings: ' + template);
        if (!ok) throw new Error('great render failed');
    }
}

for (const t of ['giso/templates/analysis_hair.html', 'giso/templates/analysis_skin.html']) {
    runTest(t);
}
console.log('\nALL JS CHECKS PASSED');
