// Frontend accessibility helpers for sadeghiai
(function () {
    function getNavLinks() {
        return document.getElementById('navLinks');
    }

    function setMenuState(button, isOpen) {
        const navLinks = getNavLinks();
        if (!navLinks || !button) return;
        navLinks.classList.toggle('active', isOpen);
        button.setAttribute('aria-expanded', String(isOpen));
        button.setAttribute('aria-label', isOpen ? 'بستن منوی اصلی' : 'باز کردن منوی اصلی');
    }

    window.toggleMobileNav = function (button) {
        const navLinks = getNavLinks();
        if (!navLinks || !button) return;
        setMenuState(button, !navLinks.classList.contains('active'));
    };

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape') return;
        const button = document.querySelector('.menu-toggle[aria-controls="navLinks"]');
        const navLinks = getNavLinks();
        if (button && navLinks && navLinks.classList.contains('active')) {
            setMenuState(button, false);
            button.focus();
        }
    });

    document.addEventListener('click', function (event) {
        const button = document.querySelector('.menu-toggle[aria-controls="navLinks"]');
        const navLinks = getNavLinks();
        if (!button || !navLinks || !navLinks.classList.contains('active')) return;
        if (button.contains(event.target) || navLinks.contains(event.target)) return;
        setMenuState(button, false);
    });
})();
