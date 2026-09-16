/*
 * جاوااسکریپت پروژه گیسو
 */

document.addEventListener('DOMContentLoaded', function () {
    // حذف خودکار پیام‌ها
    document.querySelectorAll('.giso-flash').forEach(f => {
        setTimeout(() => {
            f.style.transition = 'opacity .4s';
            f.style.opacity = '0';
            setTimeout(() => f.remove(), 400);
        }, 5000);
    });

    // محدود کردن ورودی شماره موبایل به اعداد
    document.querySelectorAll('input[type="tel"]').forEach(inp => {
        inp.addEventListener('input', function () {
            this.value = this.value.replace(/[^\d۰-۹]/g, '');
        });
    });
});
