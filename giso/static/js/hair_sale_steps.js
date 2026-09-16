/* -*- coding: utf-8 -*-
 * تجربه چهارمرحله‌ای ارزیابی و خرید هوشمند موی طبیعی گیسو
 * Scope: /hair-sale — مرحله‌بندی، بررسی هوشمند عکس و انتخاب مسیر فروش
 */

(function () {
    'use strict';

    const storageKeys = {
        proposalPrice: 'giso_hair_expected_price',
        proposalNote: 'giso_hair_price_note',
        salePath: 'giso_hair_sale_path'
    };

    const salePathConfig = {
        marketplace: {
            title: 'ثبت آگهی در بازارچه مو',
            text: 'اطلاعات لازم برای ساخت آگهی را تکمیل کنید. هماهنگی با خریداران از طریق گفت‌وگو انجام می‌شود و نیازی به انتخاب ساعت تماس نیست.',
            badge: 'بازارچه مو',
            submit: 'ثبت اطلاعات آگهی و ارسال برای بررسی',
            requiresContactTime: false
        },
        both: {
            title: 'ثبت هم‌زمان برای گیسو و بازارچه',
            text: 'اطلاعات تماس کامل می‌شود تا تیم گیسو ارزیابی مستقیم را انجام دهد و درخواست برای مسیر بازارچه نیز بررسی شود.',
            badge: 'پیشنهاد گیسو · هر دو مسیر',
            submit: 'ثبت درخواست در هر دو مسیر',
            requiresContactTime: true
        },
        giso: {
            title: 'فروش مستقیم به تیم گیسو',
            text: 'اطلاعات تماس کامل را وارد کنید تا کارشناس گیسو برای بررسی نهایی و هماهنگی خرید مستقیم با شما تماس بگیرد.',
            badge: 'فروش مستقیم به گیسو',
            submit: 'ثبت و ارسال برای بررسی تیم گیسو',
            requiresContactTime: true
        }
    };

    let selectedSalePath = '';
    let photoValidationState = window.GISO_PHOTO_UPLOADED ? 'valid' : 'idle';
    let validatedPhotoSignature = '';
    let photoValidationRequest = 0;

    function toEnglishDigits(value) {
        let text = String(value || '');
        const persian = '۰۱۲۳۴۵۶۷۸۹';
        const arabic = '٠١٢٣٤٥٦٧٨٩';
        for (let i = 0; i < 10; i += 1) {
            text = text.replace(new RegExp(persian[i], 'g'), String(i));
            text = text.replace(new RegExp(arabic[i], 'g'), String(i));
        }
        return text;
    }

    function formatPersianAmount(value) {
        const digits = toEnglishDigits(value).replace(/\D/g, '').slice(0, 15);
        if (!digits) return '';
        return Number(digits).toLocaleString('fa-IR');  // جداکنندهٔ هزارگان فارسی «٬»
    }

    function setupAmountFormatting() {
        const input = document.getElementById('sellerExpectedPrice');
        if (!input) return;
        const format = function () {
            const formatted = formatPersianAmount(input.value);
            input.value = formatted;
            safeStorageSet(storageKeys.proposalPrice, formatted);
            syncFinalFormFields();
        };
        input.addEventListener('input', format);
        if (input.value) input.value = formatPersianAmount(input.value);
    }

    function safeStorageGet(key) {
        try {
            return sessionStorage.getItem(key) || '';
        } catch (error) {
            return '';
        }
    }

    function safeStorageSet(key, value) {
        try {
            sessionStorage.setItem(key, value || '');
        } catch (error) {
            // Hidden inputs preserve data during the current page view when storage is unavailable.
        }
    }

    function safeStorageClear() {
        try {
            Object.values(storageKeys).forEach(function (key) {
                sessionStorage.removeItem(key);
            });
        } catch (error) {
            // Storage can be disabled by the browser.
        }
    }

    function showStepError(elementId, message) {
        const errorElement = document.getElementById(elementId);
        if (!errorElement) return;
        const textElement = errorElement.querySelector('span') || errorElement;
        textElement.textContent = message;
        errorElement.style.display = 'flex';
        errorElement.style.animation = 'none';
        void errorElement.offsetWidth;
        errorElement.style.animation = 'gisoShake 0.4s ease-in-out';
    }

    function hideStepError(elementId) {
        const errorElement = document.getElementById(elementId);
        if (errorElement) errorElement.style.display = 'none';
    }

    function disableButton(button) {
        if (!button) return;
        button.disabled = true;
        button.classList.add('giso-btn-disabled');
        button.setAttribute('aria-disabled', 'true');
    }

    function enableButton(button) {
        if (!button) return;
        button.disabled = false;
        button.classList.remove('giso-btn-disabled');
        button.removeAttribute('aria-disabled');
    }

    function hideStep(element) {
        if (!element) return;
        element.classList.remove('giso-step-visible', 'giso-step-completed');
        element.classList.add('giso-step-hidden');
        element.style.display = 'none';
    }

    function showStep(element, options) {
        if (!element) return;
        const settings = Object.assign({ scroll: true, completePrevious: null }, options || {});
        element.classList.remove('giso-step-hidden');
        element.classList.add('giso-step-visible');
        element.style.display = 'block';
        if (settings.completePrevious) settings.completePrevious.classList.add('giso-step-completed');
        if (settings.scroll) {
            window.setTimeout(function () {
                element.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 90);
        }
    }

    function setActiveStep(stepNumber) {
        document.querySelectorAll('.giso-stepper-item').forEach(function (item) {
            const itemStep = Number(item.getAttribute('data-stepper'));
            const isActive = itemStep === stepNumber;
            item.classList.toggle('is-active', isActive);
            item.classList.toggle('is-complete', itemStep < stepNumber);
            if (isActive) item.setAttribute('aria-current', 'step');
            else item.removeAttribute('aria-current');
        });
    }

    function markLandingComplete(completed) {
        document.querySelectorAll('.giso-hair-hero-section, .giso-hair-trust-section, .giso-hair-intro-section').forEach(function (element) {
            element.classList.toggle('giso-step-completed', Boolean(completed));
        });
    }

    function getElements() {
        return {
            hero: document.querySelector('.giso-hair-hero-section'),
            step1: document.getElementById('step1Section'),
            step2: document.getElementById('step2Section'),
            step3: document.getElementById('priceResultSection'),
            step4: document.getElementById('step4Section'),
            login: document.getElementById('step4LoginSection')
        };
    }

    function openPhotoPicker() {
        const photoInput = document.getElementById('photoInput');
        if (photoInput) photoInput.click();
    }

    function revealStep1() {
        const elements = getElements();
        markLandingComplete(true);
        showStep(elements.step1, { scroll: true });
        hideStep(elements.step2);
        if (elements.step3) hideStep(elements.step3);
        if (elements.step4) hideStep(elements.step4);
        setActiveStep(1);
    }

    window.revealStep2 = function () {
        const photoInput = document.getElementById('photoInput');
        const hasNewPhoto = Boolean(photoInput && photoInput.files && photoInput.files.length);
        const hasSavedPhoto = Boolean(window.GISO_PHOTO_UPLOADED);
        const currentSignature = hasNewPhoto ? getFileSignature(photoInput.files[0]) : '';
        const isCurrentPhotoValid = hasSavedPhoto || (
            photoValidationState === 'valid' && currentSignature && currentSignature === validatedPhotoSignature
        );

        if (!hasNewPhoto && !hasSavedPhoto) {
            showStepError('step1ErrorMsg', 'لطفاً ابتدا یک عکس واضح از موی خود انتخاب کنید.');
            return;
        }
        if (photoValidationState === 'checking') {
            showStepError('step1ErrorMsg', 'بررسی هوشمند عکس هنوز تمام نشده است. لطفاً چند لحظه صبر کنید.');
            return;
        }
        if (!isCurrentPhotoValid) {
            showStepError('step1ErrorMsg', 'این عکس برای ارزیابی تأیید نشده است. لطفاً عکس مناسب‌تری انتخاب کنید.');
            return;
        }

        const elements = getElements();
        hideStepError('step1ErrorMsg');
        showStep(elements.step2, { scroll: true, completePrevious: elements.step1 });
        setActiveStep(2);
    };

    window.goBackFromStep = function (currentStep) {
        const elements = getElements();

        if (currentStep <= 1) {
            hideStep(elements.step1);
            hideStep(elements.step2);
            if (elements.step3) hideStep(elements.step3);
            if (elements.step4) hideStep(elements.step4);
            markLandingComplete(false);
            setActiveStep(1);
            if (elements.hero) elements.hero.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return;
        }

        if (currentStep === 2) {
            hideStep(elements.step2);
            if (elements.step3) hideStep(elements.step3);
            if (elements.step4) hideStep(elements.step4);
            if (elements.step1) {
                elements.step1.classList.remove('giso-step-completed');
                showStep(elements.step1, { scroll: true });
            }
            setActiveStep(1);
            return;
        }

        if (currentStep === 3) {
            hideStep(elements.step3);
            if (elements.step4) hideStep(elements.step4);
            if (elements.step2) {
                elements.step2.classList.remove('giso-step-completed');
                showStep(elements.step2, { scroll: true });
            }
            const photoInput = document.getElementById('photoInput');
            if (!photoInput || !photoInput.files || !photoInput.files.length) {
                window.GISO_PHOTO_UPLOADED = false;
                photoValidationState = 'idle';
                validatedPhotoSignature = '';
                showStepError('step2ErrorMsg', 'برای محاسبه دوباره، لطفاً عکس مو را مجدداً انتخاب و تأیید کنید.');
            }
            enableButton(document.getElementById('btnSubmitEval'));
            setActiveStep(2);
            return;
        }

        if (currentStep === 4) {
            hideStep(elements.step4);
            if (elements.login) hideStep(elements.login);
            if (elements.step3) {
                elements.step3.classList.remove('giso-step-completed');
                showStep(elements.step3, { scroll: true });
            }
            setActiveStep(3);
        }
    };

    /* ==================== بررسی هوشمند عکس ==================== */
    function getFileSignature(file) {
        return file ? [file.name, file.size, file.lastModified].join(':') : '';
    }

    function getPersianPhotoReason(result) {
        const reasons = {
            not_hair: 'در تصویر، مو به‌اندازه کافی قابل تشخیص نیست. عکس را از پشت و با نمایش کامل مو بگیرید.',
            face: 'این تصویر بیشتر چهره را نشان می‌دهد. لطفاً عکس واضحی از پشت مو انتخاب کنید.',
            body: 'مو در کادر اصلی تصویر نیست. دوربین را روی تمام طول مو تنظیم کنید.',
            too_blurry: 'عکس تار است. گوشی را ثابت نگه دارید و با نور کافی دوباره عکس بگیرید.',
            too_dark: 'نور عکس کم است. کنار پنجره یا در محیط روشن دوباره عکس بگیرید.',
            too_bright: 'عکس بیش از حد روشن است. نور مستقیم را کمتر کنید و دوباره تلاش کنید.',
            low_resolution: 'ابعاد عکس برای ارزیابی کافی نیست. از دوربین اصلی گوشی استفاده کنید.',
            bad_frame: 'بخشی از مو بیرون کادر است. تمام طول و حجم مو را در تصویر قرار دهید.',
            quality: 'کیفیت یا کادر عکس برای ارزیابی کافی نیست. یک عکس واضح‌تر از پشت مو بگیرید.',
            invalid_image: 'فایل تصویر قابل خواندن نیست. یک عکس JPG یا PNG دیگر انتخاب کنید.',
            system_error: 'بررسی آنلاین در دسترس نبود و کنترل کیفی سبک انجام شد؛ لطفاً نتیجه زیر را ببینید.'
        };
        const code = String((result && result.reason_code) || '').toLowerCase();
        if (reasons[code]) return reasons[code];
        const message = String((result && result.message) || '').trim();
        const hasPersian = /[\u0600-\u06ff]/.test(message);
        return hasPersian ? message : 'عکس برای ارزیابی تأیید نشد. لطفاً عکس واضح‌تری از پشت و تمام طول مو انتخاب کنید.';
    }

    function setPhotoCheck(name, state) {
        const item = document.querySelector('[data-photo-check="' + name + '"]');
        if (!item) return;
        item.classList.remove('is-pass', 'is-warning', 'is-fail');
        item.classList.add(state === true ? 'is-pass' : (state === 'warning' ? 'is-warning' : 'is-fail'));
        const icon = item.querySelector('i');
        if (icon) {
            icon.className = state === true ? 'fas fa-circle-check' :
                (state === 'warning' ? 'fas fa-circle-exclamation' : 'fas fa-circle-xmark');
        }
    }

    function showPhotoValidationLoading() {
        const container = document.getElementById('hairPhotoValidation');
        const loading = document.getElementById('hairPhotoValidationLoading');
        const result = document.getElementById('hairPhotoValidationResult');
        const uploadBox = document.getElementById('photoUploadBox');
        const continueWrap = document.getElementById('step1ContinueBtnWrap');
        const preview = document.getElementById('step1ImagePreviewContainer');
        const previewStatus = document.getElementById('step1PreviewStatus');
        if (container) container.hidden = false;
        if (loading) loading.hidden = false;
        if (result) result.hidden = true;
        if (continueWrap) continueWrap.style.display = 'none';
        if (preview) {
            preview.style.display = 'flex';
            preview.classList.remove('is-valid', 'is-invalid');
            preview.classList.add('is-checking');
        }
        if (previewStatus) previewStatus.textContent = 'در حال بررسی هوشمند عکس...';
        if (uploadBox) {
            uploadBox.classList.remove('is-valid', 'is-invalid');
            uploadBox.classList.add('is-checking');
        }
        hideStepError('step1ErrorMsg');
    }

    function isPhotoResultAccepted(result) {
        if (!result || !result.valid) return false;
        const imageType = result.image_type || '';
        const hairConfirmed = imageType === 'hair' || result.hair_visible === true ||
            (result.checks && result.checks.hair_visible === true);
        const qualityScore = Number(result.quality_score == null ? 70 : result.quality_score);
        const hairInFrame = result.hair_visible !== false &&
            (!result.checks || result.checks.hair_visible !== false);
        return hairConfirmed && hairInFrame && qualityScore >= 45;
    }

    function displayPhotoValidation(result) {
        const loading = document.getElementById('hairPhotoValidationLoading');
        const resultBox = document.getElementById('hairPhotoValidationResult');
        const message = document.getElementById('hairPhotoValidationMessage');
        const uploadBox = document.getElementById('photoUploadBox');
        const continueWrap = document.getElementById('step1ContinueBtnWrap');
        const preview = document.getElementById('step1ImagePreviewContainer');
        const previewStatus = document.getElementById('step1PreviewStatus');
        const accepted = isPhotoResultAccepted(result);
        const warnings = Array.isArray(result && result.warnings) ? result.warnings.filter(Boolean) : [];
        const checks = (result && result.checks) || {};
        const imageType = (result && result.image_type) || '';

        if (loading) loading.hidden = true;
        if (resultBox) resultBox.hidden = false;
        if (message) {
            message.className = 'giso-photo-validation-message ' + (accepted ? (warnings.length ? 'is-warning' : 'is-success') : 'is-error');
            message.replaceChildren();
            const title = document.createElement('strong');
            title.textContent = accepted ? 'عکس برای ارزیابی تأیید شد؛ می‌توانید به مرحله بعد بروید.' : getPersianPhotoReason(result);
            message.appendChild(title);
            if (warnings.length) {
                const list = document.createElement('ul');
                warnings.slice(0, 4).forEach(function (warning) {
                    const item = document.createElement('li');
                    const warningText = String(warning);
                    item.textContent = /[\u0600-\u06ff]/.test(warningText) ? warningText : getPersianPhotoReason(result);
                    list.appendChild(item);
                });
                message.appendChild(list);
            }
        }

        const hairLooksValid = accepted && imageType !== 'face' && imageType !== 'body' && imageType !== 'unknown' && result.hair_visible !== false;
        const qualityLooksValid = checks.clear_image !== false && Number(result.quality_score || 70) >= 45;
        const frameLooksValid = checks.hair_visible !== false && checks.good_distance !== false;
        setPhotoCheck('hair', hairLooksValid ? true : (accepted ? 'warning' : false));
        setPhotoCheck('quality', qualityLooksValid ? true : (accepted ? 'warning' : false));
        setPhotoCheck('frame', frameLooksValid ? true : (accepted ? 'warning' : false));

        photoValidationState = accepted ? 'valid' : 'invalid';
        if (uploadBox) {
            uploadBox.classList.remove('is-checking', 'is-valid', 'is-invalid');
            uploadBox.classList.add(accepted ? 'is-valid' : 'is-invalid');
        }
        if (preview) {
            preview.classList.remove('is-checking', 'is-valid', 'is-invalid');
            preview.classList.add(accepted ? 'is-valid' : 'is-invalid');
        }
        if (previewStatus) previewStatus.textContent = accepted ?
            (result && result.ai_unavailable ?
                'بررسی هوشمند در دسترس نبود؛ عکس شما پذیرفته شد.' :
                'عکس تأیید شد؛ دکمه «مرحله بعد» فعال است.') :
            'عکس تأیید نشد؛ دلیل را ببینید و یک عکس دیگر انتخاب کنید.';
        if (continueWrap) continueWrap.style.display = accepted ? 'flex' : 'none';
        if (!accepted) {
            showStepError('step1ErrorMsg', getPersianPhotoReason(result));
        } else {
            hideStepError('step1ErrorMsg');
        }
    }

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        const field = document.querySelector('#hairEvalForm input[name="csrf_token"]');
        return (meta && meta.content) || (field && field.value) || '';
    }

    /* مأموریت 35: اعتبارسنجی سریع مخصوص فروش مو —
       عکس قبل از آپلود فشرده می‌شود و به مسیر سریع /hair-sale/validate-photo می‌رود. */
    function compressPhotoForValidation(file) {
        return new Promise(function (resolve) {
            try {
                const objectUrl = URL.createObjectURL(file);
                const image = new Image();
                image.onload = function () {
                    try {
                        const MAX_SIDE = 1280;
                        const longest = Math.max(image.naturalWidth, image.naturalHeight);
                        const scale = Math.min(1, MAX_SIDE / (longest || 1));
                        const canvas = document.createElement('canvas');
                        canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
                        canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
                        canvas.toBlob(function (blob) {
                            URL.revokeObjectURL(objectUrl);
                            resolve(blob && blob.size > 0 ? blob : file);
                        }, 'image/jpeg', 0.82);
                    } catch (err) {
                        URL.revokeObjectURL(objectUrl);
                        resolve(file);
                    }
                };
                image.onerror = function () { URL.revokeObjectURL(objectUrl); resolve(file); };
                image.src = objectUrl;
            } catch (err) { resolve(file); }
        });
    }

    async function validatePhotoWithExistingAI(file) {
        const uploadFile = await compressPhotoForValidation(file);
        const formData = new FormData();
        formData.append('image', uploadFile, 'photo.jpg');
        formData.append('analysis_type', 'hair');
        const csrfToken = getCsrfToken();
        if (csrfToken) formData.append('csrf_token', csrfToken);
        const headers = csrfToken ? { 'X-GISO-CSRF': csrfToken } : {};
        const controller = new AbortController();
        const timer = window.setTimeout(function () { controller.abort(); }, 20000);
        try {
            const response = await fetch('/hair-sale/validate-photo', {
                method: 'POST',
                headers: headers,
                body: formData,
                credentials: 'same-origin',
                signal: controller.signal
            });
            const payload = await response.json();
            if (!response.ok && !payload.reason_code) throw new Error('image_validation_failed');
            return payload;
        } finally {
            window.clearTimeout(timer);
        }
    }

    function loadImageFromFile(file) {
        return new Promise(function (resolve, reject) {
            const objectUrl = URL.createObjectURL(file);
            const image = new Image();
            image.onload = function () {
                URL.revokeObjectURL(objectUrl);
                resolve(image);
            };
            image.onerror = function () {
                URL.revokeObjectURL(objectUrl);
                reject(new Error('invalid_image'));
            };
            image.src = objectUrl;
        });
    }

    async function validatePhotoLocally(file) {
        try {
            const image = await loadImageFromFile(file);
            const longest = 220;
            const scale = Math.min(1, longest / Math.max(image.naturalWidth, image.naturalHeight));
            const width = Math.max(1, Math.round(image.naturalWidth * scale));
            const height = Math.max(1, Math.round(image.naturalHeight * scale));
            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            const context = canvas.getContext('2d', { willReadFrequently: true });
            context.drawImage(image, 0, 0, width, height);
            const pixels = context.getImageData(0, 0, width, height).data;
            const luminance = new Float32Array(width * height);
            let sum = 0;
            let sumSquares = 0;
            let hairLikePixels = 0;

            for (let i = 0, p = 0; i < pixels.length; i += 4, p += 1) {
                const red = pixels[i];
                const green = pixels[i + 1];
                const blue = pixels[i + 2];
                const light = 0.2126 * red + 0.7152 * green + 0.0722 * blue;
                luminance[p] = light;
                sum += light;
                sumSquares += light * light;
                const darkHair = light < 105 && Math.max(red, green, blue) - Math.min(red, green, blue) < 85;
                const warmHair = red > blue + 10 && green > blue + 4 && light > 55 && light < 225;
                if (darkHair || warmHair) hairLikePixels += 1;
            }

            const count = luminance.length;
            const average = sum / count;
            const contrast = Math.sqrt(Math.max(0, (sumSquares / count) - (average * average)));
            let gradientTotal = 0;
            let gradientCount = 0;
            for (let y = 1; y < height; y += 1) {
                for (let x = 1; x < width; x += 1) {
                    const index = y * width + x;
                    gradientTotal += Math.abs(luminance[index] - luminance[index - 1]);
                    gradientTotal += Math.abs(luminance[index] - luminance[index - width]);
                    gradientCount += 2;
                }
            }
            const sharpness = gradientCount ? gradientTotal / gradientCount : 0;
            const aspect = image.naturalWidth / image.naturalHeight;
            const resolutionOk = Math.min(image.naturalWidth, image.naturalHeight) >= 360 && Math.max(image.naturalWidth, image.naturalHeight) >= 600;
            const lightOk = average >= 35 && average <= 235;
            const clearOk = sharpness >= 6.5 && contrast >= 14;
            const frameOk = aspect >= 0.38 && aspect <= 2.6;
            const hairRatio = hairLikePixels / count;
            const hairLikely = hairRatio >= 0.055 || (contrast >= 30 && sharpness >= 10);
            const valid = resolutionOk && lightOk && clearOk && frameOk && hairLikely;
            const warnings = [];
            if (!resolutionOk) warnings.push('ابعاد عکس کم است؛ از دوربین اصلی گوشی استفاده کنید.');
            if (!lightOk) warnings.push(average < 35 ? 'نور عکس خیلی کم است.' : 'عکس بیش از حد روشن است.');
            if (!clearOk) warnings.push('عکس تار یا فاقد جزئیات کافی است.');
            if (!frameOk) warnings.push('کادر عکس مناسب نیست؛ مو را کامل و از پشت در کادر قرار دهید.');
            if (!hairLikely) warnings.push('مو در تصویر به‌اندازه کافی قابل تشخیص نیست.');

            return {
                valid: valid,
                image_type: hairLikely ? 'hair' : 'unknown',
                hair_visible: hairLikely,
                quality_score: Math.max(0, Math.min(100, Math.round(35 + contrast + sharpness * 2))),
                warnings: warnings,
                reason_code: valid ? 'ok' : (!hairLikely ? 'not_hair' : (!clearOk ? 'too_blurry' : 'quality')),
                message: valid ?
                    'عکس با بررسی کیفی سبک تأیید شد و می‌توانید ادامه دهید.' :
                    'عکس برای ارزیابی کافی نیست؛ لطفاً یک عکس واضح‌تر از پشت مو بگیرید.',
                checks: {
                    natural_light: lightOk,
                    no_filter: true,
                    good_distance: frameOk,
                    hair_visible: hairLikely,
                    one_person: true,
                    clear_image: clearOk && resolutionOk
                },
                validation_source: 'local'
            };
        } catch (error) {
            return {
                valid: false,
                image_type: 'unknown',
                hair_visible: false,
                warnings: [],
                reason_code: 'invalid_image',
                message: 'فایل تصویر قابل خواندن نیست. لطفاً عکس دیگری انتخاب کنید.',
                checks: { good_distance: false, hair_visible: false, clear_image: false }
            };
        }
    }

    async function validateSelectedPhoto(file) {
        const requestId = ++photoValidationRequest;
        photoValidationState = 'checking';
        validatedPhotoSignature = '';
        showPhotoValidationLoading();
        let result = null;
        try {
            const serverResult = await validatePhotoWithExistingAI(file);
            if (serverResult && serverResult.reason_code !== 'system_error') {
                result = serverResult;
            }
        } catch (error) {
            result = null;
        }
        if (!result) {
            // بررسی هوش مصنوعی در دسترس نبود — عکس را قبول می‌کنیم تا کاربر
            // پشت خطای سرویس AI گیر نکند (اصلاح 2026-08-23).
            result = {
                valid: true, image_type: 'hair', hair_visible: true, quality_score: 70,
                checks: { hair_visible: true, clear_image: true, good_distance: true },
                warnings: [], ai_unavailable: true
            };
        }
        if (requestId !== photoValidationRequest) return;
        if (isPhotoResultAccepted(result)) validatedPhotoSignature = getFileSignature(file);
        displayPhotoValidation(result);
    }

    function rejectPhotoBeforeValidation(input, message) {
        if (input) input.value = '';
        photoValidationRequest += 1;
        photoValidationState = 'invalid';
        validatedPhotoSignature = '';
        const continueWrap = document.getElementById('step1ContinueBtnWrap');
        if (continueWrap) continueWrap.style.display = 'none';
        const preview = document.getElementById('step1ImagePreviewContainer');
        if (preview) preview.style.display = 'none';
        showStepError('step1ErrorMsg', message);
    }

    window.handleImagePreview = function (input) {
        if (!input || !input.files || !input.files[0]) return;
        const file = input.files[0];
        const extension = (file.name.split('.').pop() || '').toLowerCase();
        const validExtensions = ['jpg', 'jpeg', 'png'];

        if (!validExtensions.includes(extension) || (file.type && !file.type.startsWith('image/'))) {
            rejectPhotoBeforeValidation(input, 'لطفاً یک تصویر معتبر با فرمت JPG، JPEG یا PNG انتخاب کنید.');
            return;
        }
        if (file.size > 12 * 1024 * 1024) {
            rejectPhotoBeforeValidation(input, 'حجم عکس زیاد است. لطفاً تصویری کوچک‌تر از ۱۲ مگابایت انتخاب کنید.');
            return;
        }

        hideStepError('step1ErrorMsg');
        const reader = new FileReader();
        reader.onload = function (event) {
            const previewImage = document.getElementById('step1ImagePreviewImg');
            const previewContainer = document.getElementById('step1ImagePreviewContainer');
            if (previewImage) previewImage.src = event.target.result;
            if (previewContainer) previewContainer.style.display = 'flex';
            const bigPreview = document.getElementById('step1BigPreview');
            const uploadBoxEl = document.getElementById('photoUploadBox');
            if (bigPreview) { bigPreview.src = event.target.result; bigPreview.style.display = 'block'; }
            if (uploadBoxEl) uploadBoxEl.classList.add('has-photo');
            try {
                sessionStorage.setItem('giso_preview_dataurl', event.target.result);
            } catch (error) {
                // Preview remains available without browser storage.
            }
        };
        reader.readAsDataURL(file);
        validateSelectedPhoto(file);
    };

    function validateEvaluationForm() {
        hideStepError('step2ErrorMsg');
        const photoInput = document.getElementById('photoInput');
        const hasNewPhoto = Boolean(photoInput && photoInput.files && photoInput.files.length);
        const hasSavedPhoto = Boolean(window.GISO_PHOTO_UPLOADED);
        const currentSignature = hasNewPhoto ? getFileSignature(photoInput.files[0]) : '';
        const photoIsValid = hasSavedPhoto || (
            photoValidationState === 'valid' && currentSignature === validatedPhotoSignature
        );
        const hasType = Boolean(document.querySelector('input[name="hair_type"]:checked'));
        const length = document.querySelector('select[name="length_cm"]');
        const hasHealth = Boolean(document.querySelector('input[name="hair_health"]:checked'));
        const hasWeight = Boolean(document.querySelector('input[name="hair_weight"]:checked'));

        if (!photoIsValid) {
            showStepError('step2ErrorMsg', 'عکس باید ابتدا توسط بررسی هوشمند تأیید شود.');
            return false;
        }
        if (!hasType || !length || !length.value || !hasHealth || !hasWeight) {
            showStepError('step2ErrorMsg', 'لطفاً نوع، طول، سلامت و حجم مو را مشخص کنید.');
            return false;
        }
        disableButton(document.getElementById('btnSubmitEval'));
        return true;
    }

    /* ==================== قیمت پیشنهادی و انتخاب مسیر ==================== */
    function syncFinalFormFields() {
        const priceInput = document.getElementById('sellerExpectedPrice');
        const noteInput = document.getElementById('sellerPriceNote');
        const price = priceInput ? priceInput.value.trim() : safeStorageGet(storageKeys.proposalPrice);
        const note = noteInput ? noteInput.value.trim() : safeStorageGet(storageKeys.proposalNote);
        const path = selectedSalePath || safeStorageGet(storageKeys.salePath) || window.GISO_SALE_PATH || 'giso';

        document.querySelectorAll('.js-seller-expected-price').forEach(function (input) {
            input.value = price;
        });
        document.querySelectorAll('.js-seller-price-note').forEach(function (input) {
            input.value = note;
        });
        document.querySelectorAll('.js-sale-path-input').forEach(function (input) {
            input.value = path;
        });
    }

    function updateRegistrationForPath(path) {
        const config = salePathConfig[path] || salePathConfig.giso;
        const contactGroup = document.getElementById('contactTimeGroup');
        const contactSelect = document.getElementById('contactTime');
        const title = document.getElementById('registrationPathTitle');
        const text = document.getElementById('registrationPathText');
        const badge = document.getElementById('selectedPathBadge');
        const submit = document.getElementById('btnSubmitReg');
        const confirm = document.getElementById('btnConfirmLoggedIn');

        if (title) title.textContent = config.title;
        if (text) text.textContent = config.text;
        if (badge) badge.textContent = config.badge;
        if (submit) submit.textContent = config.submit;
        if (confirm) confirm.textContent = config.submit;

        if (contactGroup) contactGroup.hidden = !config.requiresContactTime;
        if (contactSelect) {
            contactSelect.disabled = !config.requiresContactTime;
            contactSelect.required = config.requiresContactTime;
        }
        document.querySelectorAll('.js-adaptive-number').forEach(function (number) {
            number.textContent = config.requiresContactTime ? number.dataset.direct : number.dataset.market;
        });
        const marketplacePath = path === 'marketplace' || path === 'both';
        document.querySelectorAll('.js-marketplace-consent').forEach(function (label) {
            label.hidden = !marketplacePath;
            const checkbox = label.querySelector('input[type="checkbox"]');
            if (checkbox) checkbox.required = marketplacePath;
        });
    }

    function applySalePath(path, options) {
        if (!salePathConfig[path]) path = 'giso';
        const settings = Object.assign({ persist: true, revealForm: false }, options || {});
        selectedSalePath = path;
        if (settings.persist) safeStorageSet(storageKeys.salePath, path);

        document.querySelectorAll('.giso-sale-path-card').forEach(function (card) {
            card.classList.toggle('is-selected', card.getAttribute('data-sale-card') === path);
        });
        document.querySelectorAll('.js-sale-path').forEach(function (button) {
            const selected = button.getAttribute('data-sale-path') === path;
            button.setAttribute('aria-pressed', selected ? 'true' : 'false');
            if (selected) button.closest('.giso-sale-path-card').setAttribute('aria-current', 'true');
            else button.closest('.giso-sale-path-card').removeAttribute('aria-current');
        });

        updateRegistrationForPath(path);
        syncFinalFormFields();
        if (settings.revealForm) revealDecisionForm();
    }

    function restoreState() {
        const price = safeStorageGet(storageKeys.proposalPrice);
        const note = safeStorageGet(storageKeys.proposalNote);
        const path = safeStorageGet(storageKeys.salePath) || window.GISO_SALE_PATH || '';
        const priceInput = document.getElementById('sellerExpectedPrice');
        const noteInput = document.getElementById('sellerPriceNote');
        if (priceInput && price) priceInput.value = price;
        if (noteInput && note) noteInput.value = note;
        if (path && salePathConfig[path]) applySalePath(path, { persist: false, revealForm: false });
        syncFinalFormFields();
    }

    function revealDecisionForm() {
        const elements = getElements();
        if (!selectedSalePath) applySalePath('giso', { persist: true, revealForm: false });
        if (!elements.step4 && elements.login) {
            showStep(elements.login, { scroll: true, completePrevious: elements.step3 });
            setActiveStep(4);
            return;
        }
        if (!elements.step4) return;
        syncFinalFormFields();
        showStep(elements.step4, { scroll: true, completePrevious: elements.step3 });
        setActiveStep(4);
    }

    function openProposalPanel() {
        const panel = document.getElementById('priceProposalPanel');
        const button = document.getElementById('btnDifferentPrice');
        if (!panel) return;
        panel.hidden = false;
        panel.classList.add('is-open');
        if (button) button.setAttribute('aria-expanded', 'true');
        setActiveStep(4);
        window.setTimeout(function () {
            panel.scrollIntoView({ behavior: 'smooth', block: 'center' });
            const priceInput = document.getElementById('sellerExpectedPrice');
            if (priceInput) priceInput.focus({ preventScroll: true });
        }, 60);
    }

    function submitProposal() {
        const priceInput = document.getElementById('sellerExpectedPrice');
        const noteInput = document.getElementById('sellerPriceNote');
        const price = priceInput ? priceInput.value.trim() : '';
        const note = noteInput ? noteInput.value.trim() : '';

        hideStepError('proposalErrorMsg');
        if (!price) {
            showStepError('proposalErrorMsg', 'لطفاً قیمت مورد نظر خود را وارد کنید.');
            if (priceInput) priceInput.focus();
            return;
        }

        safeStorageSet(storageKeys.proposalPrice, price);
        safeStorageSet(storageKeys.proposalNote, note);
        syncFinalFormFields();

        const message = document.getElementById('proposalSuccessMsg');
        const continueButton = document.getElementById('btnProposalContinue');
        if (message) {
            message.hidden = false;
            const detail = message.querySelector('span');
            if (detail && (selectedSalePath === 'marketplace' || selectedSalePath === 'both')) {
                detail.textContent = 'مسیر انتخاب‌شده حفظ شد؛ اکنون ثبت‌نام، ورود یا ثبت نهایی را در همان مرحله ادامه دهید.';
            }
        }
        if (continueButton) continueButton.hidden = false;
        disableButton(document.getElementById('btnSubmitProposal'));
        if (priceInput) priceInput.readOnly = true;
        if (noteInput) noteInput.readOnly = true;

        // مسیر بازارچه/هر دو از همین انتخاب ادامه پیدا می‌کند؛ ثبت‌نام یا ورود کاربر
        // مقدار sale_path را در فرم پنهان حفظ می‌کند و او را به ابتدای جریان برنمی‌گرداند.
        if (selectedSalePath === 'marketplace' || selectedSalePath === 'both') {
            if (continueButton) continueButton.hidden = true;
            window.setTimeout(revealDecisionForm, 350);
        }
    }

    function validateRegistrationForm() {
        hideStepError('step4ErrorMsg');
        const form = document.getElementById('hairRegForm');
        if (!form) return true;
        const config = salePathConfig[selectedSalePath] || salePathConfig.giso;
        const name = form.querySelector('[name="customer_name"]');
        const phone = form.querySelector('[name="customer_phone"]');
        const region = form.querySelector('[name="region"]');
        const contactTime = form.querySelector('[name="contact_time"]');
        const password = form.querySelector('[name="password"]');
        const securityQuestion = form.querySelector('[name="security_question"]');
        const securityAnswer = form.querySelector('[name="security_answer"]');
        const normalizedPhone = toEnglishDigits(phone ? phone.value : '').replace(/[^\d]/g, '');

        if (!name || !name.value.trim() || !phone || !normalizedPhone || !region || !region.value.trim() ||
            !password || !password.value || !securityQuestion || !securityQuestion.value ||
            !securityAnswer || !securityAnswer.value.trim()) {
            showStepError('step4ErrorMsg', 'لطفاً همه اطلاعات ضروری فرم را کامل کنید.');
            return false;
        }
        if (config.requiresContactTime && (!contactTime || !contactTime.value)) {
            showStepError('step4ErrorMsg', 'لطفاً ساعت مناسب تماس را انتخاب کنید.');
            return false;
        }
        if (normalizedPhone.length < 10) {
            showStepError('step4ErrorMsg', 'شماره همراه واردشده معتبر نیست.');
            return false;
        }
        var pwVal = password.value || '';
        var pwHasLetter = /[A-Za-z\u0600-\u06FF]/.test(pwVal);
        var pwHasDigit = /[0-9\u06F0-\u06F9\u0660-\u0669]/.test(pwVal);
        if (pwVal.length < 6 || !pwHasLetter || !pwHasDigit) {
            showStepError('step4ErrorMsg', 'رمز عبور باید حداقل ۶ کاراکتر و ترکیبی از حروف و عدد باشد.');
            return false;
        }
        disableButton(document.getElementById('btnSubmitReg'));
        return true;
    }

    function setupAccessiblePhotoControls() {
        const uploadBox = document.getElementById('photoUploadBox');
        const step1Preview = document.getElementById('step1ImagePreviewContainer');
        const photoInput = document.getElementById('photoInput');
        const retry = document.getElementById('btnChooseAnotherPhoto');

        [uploadBox, step1Preview].forEach(function (control) {
            if (!control) return;
            control.addEventListener('click', openPhotoPicker);
            control.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    openPhotoPicker();
                }
            });
        });
        if (retry) retry.addEventListener('click', openPhotoPicker);
        if (photoInput) {
            photoInput.addEventListener('change', function () {
                window.handleImagePreview(photoInput);
            });
        }
    }

    function setupFormListeners() {
        const evaluationForm = document.getElementById('hairEvalForm');
        if (evaluationForm) {
            evaluationForm.addEventListener('submit', function (event) {
                if (!validateEvaluationForm()) event.preventDefault();
            });
        }

        const registrationForm = document.getElementById('hairRegForm');
        if (registrationForm) {
            registrationForm.addEventListener('submit', function (event) {
                syncFinalFormFields();
                if (!validateRegistrationForm()) event.preventDefault();
            });
        }

        document.querySelectorAll('.js-final-hair-form').forEach(function (form) {
            if (form.id === 'hairRegForm') return;
            form.addEventListener('submit', syncFinalFormFields);
        });
    }

    function setupDecisionListeners() {
        const differentPrice = document.getElementById('btnDifferentPrice');
        const submitProposalButton = document.getElementById('btnSubmitProposal');
        const continueProposalButton = document.getElementById('btnProposalContinue');
        const pathGrid = document.getElementById('salePathGrid');

        document.querySelectorAll('.js-sale-path').forEach(function (button) {
            button.addEventListener('click', function () {
                const path = button.getAttribute('data-sale-path');
                const marketplacePath = path === 'marketplace' || path === 'both';
                const priceInput = document.getElementById('sellerExpectedPrice');
                const price = (priceInput ? priceInput.value : safeStorageGet(storageKeys.proposalPrice)).trim();
                applySalePath(path, { persist: true, revealForm: !marketplacePath || Boolean(price) });
                if (marketplacePath && !price) {
                    openProposalPanel();
                    showStepError('proposalErrorMsg', 'برای ثبت آگهی بازارچه، ابتدا قیمت مدنظر خود را وارد کنید.');
                }
            });
        });
        if (differentPrice) differentPrice.addEventListener('click', openProposalPanel);
        if (submitProposalButton) submitProposalButton.addEventListener('click', submitProposal);
        if (continueProposalButton) {
            continueProposalButton.addEventListener('click', function () {
                if (pathGrid) pathGrid.scrollIntoView({ behavior: 'smooth', block: 'center' });
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        if (window.GISO_SUBMITTED) {
            safeStorageClear();
            const success = document.getElementById('step5Section');
            showStep(success, { scroll: true });
            return;
        }

        if (!window.GISO_SHOW_RESULT && !window.GISO_SHOW_LOGIN) safeStorageClear();

        setupAccessiblePhotoControls();
        setupFormListeners();
        setupDecisionListeners();
        restoreState();
        setupAmountFormatting();

        const startButton = document.getElementById('btnStartStep1');
        if (startButton) {
            startButton.addEventListener('click', function (event) {
                event.preventDefault();
                revealStep1();
            });
        }

        const elements = getElements();
        if (window.GISO_SHOW_RESULT && elements.step3) {
            document.querySelectorAll('.giso-hair-hero-section, .giso-hair-trust-section, .giso-hair-intro-section').forEach(function (element) {
                element.classList.remove('giso-step-hidden');
                element.classList.add('giso-step-visible', 'giso-step-completed');
                element.style.display = 'block';
            });
            if (elements.step1) {
                elements.step1.classList.remove('giso-step-hidden');
                elements.step1.classList.add('giso-step-visible', 'giso-step-completed');
                elements.step1.style.display = 'block';
            }
            if (elements.step2) {
                elements.step2.classList.remove('giso-step-hidden');
                elements.step2.classList.add('giso-step-visible', 'giso-step-completed');
                elements.step2.style.display = 'block';
            }
            if (window.GISO_PHOTO_UPLOADED) {
                const preview = document.getElementById('step1ImagePreviewContainer');
                if (preview) {
                    preview.style.display = 'flex';
                    preview.classList.add('is-valid');
                }
                const previewStatus = document.getElementById('step1PreviewStatus');
                if (previewStatus) previewStatus.textContent = 'عکس قبلاً تأیید و برای ارزیابی ثبت شده است.';
                photoValidationState = 'valid';
            }
            if (elements.step4) hideStep(elements.step4);
            showStep(elements.step3, { scroll: !window.GISO_SHOW_LOGIN });
            setActiveStep(3);

            if (window.GISO_SHOW_LOGIN && elements.login) {
                elements.step3.classList.add('giso-step-completed');
                showStep(elements.login, { scroll: true });
                setActiveStep(4);
            }
            return;
        }

        document.querySelectorAll('.giso-hair-hero-section, .giso-hair-trust-section, .giso-hair-intro-section').forEach(function (element) {
            element.classList.remove('giso-step-hidden', 'giso-step-completed');
            element.classList.add('giso-step-visible');
            element.style.display = 'block';
        });
        hideStep(elements.step1);
        hideStep(elements.step2);
        if (elements.step3) hideStep(elements.step3);
        if (elements.step4) hideStep(elements.step4);
        setActiveStep(1);
    });
})();
