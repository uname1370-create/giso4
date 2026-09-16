/* Giso Shop frontend interactions — v6. No backend contract is changed. */
(function () {
    'use strict';

    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
    const setBodyLocked = locked => { document.body.style.overflow = locked ? 'hidden' : ''; };
    const faDigits = value => String(value).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
    const formatToman = value => faDigits(Math.max(0, Number(value) || 0).toLocaleString('en-US')) + ' تومان';

    /* Cart drawer */
    const cartButton = $('#gisoCartWidget');
    const cartDrawer = $('#gisoCartDrawer');
    const cartOverlay = $('#gisoCartOverlay');
    const cartClose = $('#gisoCartClose');
    let cartReturnFocus = null;

    function openCart() {
        if (!cartDrawer) return;
        cartReturnFocus = document.activeElement;
        cartDrawer.classList.add('is-open');
        cartDrawer.setAttribute('aria-hidden', 'false');
        cartButton?.setAttribute('aria-expanded', 'true');
        if (cartOverlay) cartOverlay.hidden = false;
        setBodyLocked(true);
        cartDrawer.focus({ preventScroll: true });
    }
    function closeCart() {
        if (!cartDrawer) return;
        cartDrawer.classList.remove('is-open', 'open');
        cartDrawer.setAttribute('aria-hidden', 'true');
        cartButton?.setAttribute('aria-expanded', 'false');
        if (cartOverlay) cartOverlay.hidden = true;
        setBodyLocked(false);
        if (cartReturnFocus && typeof cartReturnFocus.focus === 'function') cartReturnFocus.focus({ preventScroll: true });
    }
    cartButton?.addEventListener('click', openCart);
    cartClose?.addEventListener('click', closeCart);
    cartOverlay?.addEventListener('click', closeCart);

    /* Mobile filters */
    const filters = $('#gisoShopSidebar');
    const filtersButton = $('#gisoFiltersBtn');
    const filtersClose = $('#gisoFiltersClose');
    const filtersOverlay = $('#gisoFiltersOverlay');
    function openFilters() {
        if (!filters) return;
        filters.classList.add('is-open', 'open');
        filters.setAttribute('aria-hidden', 'false');
        filtersButton?.setAttribute('aria-expanded', 'true');
        if (filtersOverlay) filtersOverlay.hidden = false;
        if (window.matchMedia('(max-width: 780px)').matches) setBodyLocked(true);
        filtersClose?.focus({ preventScroll: true });
    }
    function closeFilters() {
        if (!filters) return;
        filters.classList.remove('is-open', 'open');
        filtersButton?.setAttribute('aria-expanded', 'false');
        if (filtersOverlay) filtersOverlay.hidden = true;
        setBodyLocked(false);
    }
    filtersButton?.addEventListener('click', openFilters);
    filtersClose?.addEventListener('click', closeFilters);
    filtersOverlay?.addEventListener('click', closeFilters);
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') { closeCart(); closeFilters(); }
    });

    /* Search, filters and section chips */
    const mainGrid = $('#shopGrid');
    const searchInput = $('#shopSearch');
    const searchResult = $('#shopSearchResults');
    const searchCount = $('#shopSearchCount');
    const emptyState = $('#shopEmptyFilter');
    const filterInputs = $$('.giso-f-cat, .giso-f-price, .giso-f-stock, .giso-f-tag');
    const sortChips = $$('.giso-sort-chip[data-sort]');
    const catalogSections = $$('.giso-product-section[data-slot]');
    let activeSection = 'all';

    function checkedValues(selector) { return $$(`${selector}:checked`).map(input => input.value); }
    function filterState() {
        return {
            query: (searchInput?.value || '').trim().toLocaleLowerCase('fa'),
            categories: checkedValues('.giso-f-cat'),
            prices: checkedValues('.giso-f-price'),
            stocks: checkedValues('.giso-f-stock'),
            tags: checkedValues('.giso-f-tag')
        };
    }
    function priceMatches(price, ranges) {
        if (!ranges.length) return true;
        return ranges.some(range => {
            const [minimum, maximum] = range.split('-').map(Number);
            return price >= (minimum || 0) && price < (maximum || Number.MAX_SAFE_INTEGER);
        });
    }
    function cardMatches(card, state) {
        const category = card.dataset.cat || '';
        const searchable = `${card.dataset.name || ''} ${card.dataset.desc || ''}`.toLocaleLowerCase('fa');
        const price = Number(card.dataset.price || 0);
        const stock = card.dataset.stock || (card.classList.contains('is-out-of-stock') ? 'out' : 'in');
        const tags = (card.dataset.tags || '').split(',').map(item => item.trim()).filter(Boolean);
        const categoryMatch = !state.categories.length || state.categories.includes('all') || state.categories.includes(category);
        const queryMatch = !state.query || searchable.includes(state.query);
        const stockMatch = !state.stocks.length || state.stocks.includes(stock);
        const tagMatch = !state.tags.length || state.tags.some(tag => tags.includes(tag));
        return categoryMatch && queryMatch && stockMatch && tagMatch && priceMatches(price, state.prices);
    }
    function resetFilters() {
        filterInputs.forEach(input => { input.checked = false; });
        const allCategory = $('.giso-f-cat[value="all"]');
        if (allCategory) allCategory.checked = true;
        if (searchInput) searchInput.value = '';
        activeSection = 'all';
        sortChips.forEach(chip => chip.classList.toggle('is-active', chip.dataset.sort === 'all'));
        applyCatalogState();
    }
    function applyCatalogState() {
        if (!mainGrid) return;
        const state = filterState();
        const filtering = Boolean(state.query || state.prices.length || state.stocks.length || state.tags.length || (state.categories.length && !state.categories.includes('all')));
        let visible = 0;
        $$('.giso-product-card', mainGrid).forEach(card => {
            const matches = cardMatches(card, state);
            card.hidden = !matches;
            if (matches) visible += 1;
        });

        catalogSections.forEach(section => {
            const slot = section.dataset.slot;
            if (slot === 'recommended') {
                if (filtering || activeSection !== 'all') section.hidden = true;
                return;
            }
            if (state.query || filtering) section.hidden = slot !== 'all';
            else if (activeSection === 'all') section.hidden = false;
            else section.hidden = slot !== activeSection;
        });
        if (searchResult) {
            searchResult.hidden = !state.query;
            if (searchCount) searchCount.textContent = faDigits(visible);
        }
        if (emptyState) emptyState.hidden = visible !== 0 || (activeSection !== 'all' && !filtering);
    }
    searchInput?.addEventListener('input', applyCatalogState);
    filterInputs.forEach(input => input.addEventListener('change', () => {
        if (input.classList.contains('giso-f-cat')) {
            const all = $('.giso-f-cat[value="all"]');
            if (input.value === 'all' && input.checked) $$('.giso-f-cat').forEach(item => { if (item !== input) item.checked = false; });
            else if (input.checked && all) all.checked = false;
            if (!checkedValues('.giso-f-cat').length && all) all.checked = true;
        }
        applyCatalogState();
    }));
    sortChips.forEach(chip => chip.addEventListener('click', () => {
        activeSection = chip.dataset.sort || 'all';
        sortChips.forEach(item => item.classList.toggle('is-active', item === chip));
        applyCatalogState();
        $('.giso-catalog-main')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }));
    $$('.giso-filter-clear').forEach(button => button.addEventListener('click', () => { resetFilters(); closeFilters(); }));
    $('#shopEmptyReset')?.addEventListener('click', resetFilters);

    /* Existing recommendation API: analysis state and real recommended products */
    const hero = $('#gisoSmartHero');
    const heroGuest = $('#gisoHeroGuest');
    const heroNoAnalysis = $('#gisoHeroNoAnalysis');
    const heroPersonalized = $('#gisoHeroPersonalized');
    const heroPersonalizedText = $('#gisoHeroPersonalizedText');
    const needsBox = $('#gisoAnalysisNeeds');
    const recommendationSection = $('#gisoRecommendedSection');
    const recommendationGrid = $('#gisoRecommendedGrid');
    const recommendationLoading = $('#gisoRecommendationLoading');

    function setHeroState(state) {
        if (heroGuest) heroGuest.hidden = state !== 'guest';
        if (heroNoAnalysis) heroNoAnalysis.hidden = state !== 'no-analysis';
        if (heroPersonalized) heroPersonalized.hidden = state !== 'personalized';
    }
    function recommendationReason(result) {
        const profile = result.profile || {};
        const concern = Array.isArray(profile.concerns) ? profile.concerns.find(Boolean) : '';
        if (result.match_source === 'analysis_concerns' && concern) return `مرتبط با نیاز «${concern}» در آخرین آنالیز شما`;
        if (result.match_source === 'hair_profile' && profile.hair_type) return `متناسب با مشخصات موی ${profile.hair_type} ثبت‌شده برای شما`;
        if (result.match_source === 'analysis_type') return 'براساس نوع آخرین آنالیز ثبت‌شده شما';
        return 'براساس اطلاعات واقعی آخرین آنالیز شما';
    }
    function markRecommendedCards(items, reason) {
        const ids = new Set(items.map(item => String(item.product_id)));
        $$('.giso-product-card').forEach(card => {
            if (!ids.has(String(card.dataset.id))) return;
            card.classList.add('is-ai-recommended');
            const badge = $('.giso-ai-badge', card);
            if (badge) badge.hidden = false;
            const reasonBox = $('.giso-recommendation-reason', card);
            const reasonText = $('.giso-recommendation-reason-text', card);
            if (reasonBox && reasonText) { reasonText.textContent = reason; reasonBox.hidden = false; }
        });
    }
    function safeStaticUrl(path) {
        const clean = String(path || '').replace(/^\/+/, '').split('/').map(encodeURIComponent).join('/');
        return clean ? `/static/${clean}` : '';
    }
    function csrfValue() { return $('input[name="csrf_token"]')?.value || $('meta[name="csrf-token"]')?.content || ''; }
    function buildRecommendationCard(item, reason) {
        const card = document.createElement('article');
        card.className = 'giso-product-card giso-card is-ai-recommended';
        card.dataset.id = String(item.product_id);
        card.dataset.cat = item.category || '';
        card.dataset.name = item.name || '';
        card.dataset.desc = item.short_description || item.description || '';
        card.dataset.price = String(item.price || 0);
        card.dataset.stock = 'in';
        card.dataset.tags = 'پیشنهاد هوشمند';

        const media = document.createElement('div');
        media.className = 'giso-product-media';
        const imageLink = document.createElement('a');
        imageLink.className = 'giso-product-image';
        imageLink.href = `/shop/product/${encodeURIComponent(item.product_id)}`;
        imageLink.setAttribute('aria-label', `مشاهده ${item.name || 'محصول'}`);
        const imageUrl = safeStaticUrl(item.image_path);
        if (imageUrl) {
            const image = document.createElement('img');
            image.src = imageUrl; image.alt = item.name || 'محصول گیسو'; image.loading = 'lazy'; image.decoding = 'async';
            imageLink.appendChild(image);
        } else {
            const placeholder = document.createElement('span');
            placeholder.className = 'giso-product-placeholder';
            const bloom = document.createElement('span'); bloom.className = 'giso-placeholder-bloom'; bloom.innerHTML = '<i class="fas fa-leaf" aria-hidden="true"></i>';
            const brand = document.createElement('strong'); brand.textContent = 'گیسو';
            const note = document.createElement('small'); note.textContent = 'تصویر محصول به‌زودی';
            placeholder.append(bloom, brand, note); imageLink.appendChild(placeholder);
        }
        const badge = document.createElement('span'); badge.className = 'giso-ai-badge'; badge.innerHTML = '<i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i> پیشنهاد هوشمند';
        media.append(imageLink, badge);

        const content = document.createElement('div'); content.className = 'giso-product-content';
        const title = document.createElement('h3'); title.className = 'giso-product-title';
        const titleLink = document.createElement('a'); titleLink.href = imageLink.href; titleLink.textContent = item.name || 'محصول گیسو'; title.appendChild(titleLink);
        const desc = document.createElement('p'); desc.className = 'giso-product-desc'; desc.textContent = item.short_description || item.description || 'محصول مرتبط با نیاز ثبت‌شده شما';
        const reasonBox = document.createElement('p'); reasonBox.className = 'giso-recommendation-reason';
        const reasonIcon = document.createElement('i'); reasonIcon.className = 'fas fa-wand-sparkles'; reasonIcon.setAttribute('aria-hidden', 'true');
        const reasonSpan = document.createElement('span'); reasonSpan.className = 'giso-recommendation-reason-text'; reasonSpan.textContent = reason; reasonBox.append(reasonIcon, reasonSpan);
        const priceRow = document.createElement('div'); priceRow.className = 'giso-product-price-row';
        const price = document.createElement('div'); price.className = 'giso-product-price'; const priceStrong = document.createElement('strong'); priceStrong.textContent = formatToman(item.price); price.appendChild(priceStrong);
        const details = document.createElement('a'); details.className = 'giso-product-details-link'; details.href = imageLink.href; details.textContent = 'مشاهده جزئیات ←'; priceRow.append(price, details);
        const actions = document.createElement('div'); actions.className = 'giso-product-actions';
        const form = document.createElement('form'); form.method = 'POST'; form.action = `/shop/cart/add/${encodeURIComponent(item.product_id)}`;
        const csrf = document.createElement('input'); csrf.type = 'hidden'; csrf.name = 'csrf_token'; csrf.value = csrfValue();
        const button = document.createElement('button'); button.type = 'submit'; button.className = 'giso-btn giso-btn-primary giso-btn-block'; button.innerHTML = '<i class="fas fa-basket-shopping" aria-hidden="true"></i> افزودن به سبد'; form.append(csrf, button); actions.appendChild(form);
        content.append(title, desc, reasonBox, priceRow, actions); card.append(media, content);
        return card;
    }
    function renderRecommendations(result) {
        const items = Array.isArray(result.recommendations) ? result.recommendations : [];
        const exactMatch = result.analysis_based && result.match_source && result.match_source !== 'general';
        if (!exactMatch || !items.length || !recommendationGrid || !recommendationSection) {
            if (recommendationSection && !recommendationGrid?.children.length) recommendationSection.hidden = true;
            return;
        }
        const reason = recommendationReason(result);
        recommendationGrid.innerHTML = '';
        items.forEach(item => {
            const existing = $(`.giso-product-card[data-id="${CSS.escape(String(item.product_id))}"]`);
            if (existing) {
                const clone = existing.cloneNode(true);
                clone.hidden = false;
                const cloneBadge = $('.giso-ai-badge', clone); if (cloneBadge) cloneBadge.hidden = false;
                const cloneReason = $('.giso-recommendation-reason', clone); const cloneText = $('.giso-recommendation-reason-text', clone);
                if (cloneReason && cloneText) { cloneReason.hidden = false; cloneText.textContent = reason; }
                clone.classList.add('is-ai-recommended'); recommendationGrid.appendChild(clone);
            } else recommendationGrid.appendChild(buildRecommendationCard(item, reason));
        });
        recommendationSection.hidden = false;
        markRecommendedCards(items, reason);
    }
    async function loadRecommendations() {
        const authenticated = hero?.dataset.authenticated === '1';
        if (!hero) return;
        if (!authenticated) { setHeroState('guest'); return; }
        setHeroState('no-analysis');
        if (recommendationLoading) recommendationLoading.hidden = false;
        try {
            const response = await fetch('/api/recommendations?limit=4', { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
            if (!response.ok) throw new Error('recommendation request failed');
            const result = await response.json();
            if (result.status !== 'ok') throw new Error('recommendation service unavailable');
            if (result.analysis_based) {
                setHeroState('personalized');
                const concerns = Array.isArray(result.profile?.concerns) ? result.profile.concerns.filter(Boolean).slice(0, 5) : [];
                if (needsBox) {
                    needsBox.innerHTML = '';
                    concerns.forEach(concern => { const chip = document.createElement('span'); chip.textContent = concern; needsBox.appendChild(chip); });
                    if (result.profile?.hair_type) { const chip = document.createElement('span'); chip.textContent = `نوع مو: ${result.profile.hair_type}`; needsBox.appendChild(chip); }
                }
                if (result.match_source === 'general') {
                    if (heroPersonalizedText) heroPersonalizedText.textContent = 'آنالیز شما ثبت شده است؛ هنوز محصولی با تطبیق دقیق پیدا نشد و کاتالوگ عمومی نمایش داده می‌شود.';
                    if (recommendationSection && !recommendationGrid?.children.length) recommendationSection.hidden = true;
                } else {
                    if (heroPersonalizedText) heroPersonalizedText.textContent = 'محصولات پیشنهادی براساس اطلاعات واقعی آخرین آنالیز شما انتخاب شده‌اند.';
                    renderRecommendations(result);
                }
            } else setHeroState('no-analysis');
        } catch (error) {
            setHeroState('no-analysis');
            if (recommendationSection && !recommendationGrid?.children.length) recommendationSection.hidden = true;
        } finally { if (recommendationLoading) recommendationLoading.hidden = true; }
    }

    /* Quantity controls keep server-side forms authoritative */
    $$('[data-qty-form]').forEach(form => form.addEventListener('click', event => {
        const button = event.target.closest('.giso-qty-step');
        if (!button) return;
        event.preventDefault();
        const input = $('input[name="qty"]', form);
        if (!input) return;
        const next = Math.max(1, Math.min(99, Number(input.value || 1) + Number(button.dataset.step || 0)));
        input.value = String(next);
        if (form.requestSubmit) form.requestSubmit(); else form.submit();
    }));

    /* Guest wishlist remains local; authenticated wishlist stays server-side */
    const wishlistKey = 'giso_wishlist';
    function localWishlist() { try { return JSON.parse(localStorage.getItem(wishlistKey) || '[]'); } catch (_) { return []; } }
    function paintWishlist() {
        const list = localWishlist().map(String);
        $$('[data-wishlist]').forEach(button => button.classList.toggle('active', list.includes(String(button.dataset.wishlist))));
    }
    document.addEventListener('click', event => {
        const button = event.target.closest('[data-wishlist]');
        if (!button) return;
        event.preventDefault();
        const id = String(button.dataset.wishlist);
        const list = localWishlist().map(String);
        const index = list.indexOf(id);
        if (index < 0) list.push(id); else list.splice(index, 1);
        try { localStorage.setItem(wishlistKey, JSON.stringify(list)); } catch (_) { /* storage unavailable */ }
        paintWishlist();
    });
    paintWishlist();

    /* Cart count from the real server cart */
    const cartCount = $('#gisoCartCount');
    function updateCartCount(value) { if (cartCount) cartCount.textContent = faDigits(Number(value) || 0); }
    if (cartCount) fetch('/api/cart-count', { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
        .then(response => response.ok ? response.json() : Promise.reject())
        .then(data => updateCartCount(data.count)).catch(() => {});

    /* Thank-you widget uses only real recent order data */
    const smartWidget = $('#gisoSmartWidget');
    if (smartWidget) {
        const close = $('#gisoSmartClose');
        close?.addEventListener('click', () => { smartWidget.hidden = true; });
        if (smartWidget.dataset.justOrdered === '1') {
            let orders = [];
            try { orders = JSON.parse(smartWidget.dataset.orders || '[]'); } catch (_) { orders = []; }
            const ids = orders.map(order => order.id).join(',');
            let seen = '';
            try { seen = localStorage.getItem('giso_thanks_seen') || ''; } catch (_) { seen = ''; }
            if (orders.length && seen !== ids) {
                const body = $('#gisoSmartBody'); if (body) body.textContent = 'سفارش شما ثبت شد؛ فاکتور و مسیر پیگیری در پنل کاربر در دسترس است.';
                const orderBox = $('#gisoSmartOrders');
                if (orderBox) orders.forEach(order => {
                    const row = document.createElement('div'); row.className = 'giso-smart-order';
                    const name = document.createElement('span'); name.textContent = `🛍 ${order.pname || `سفارش #${order.id}`}`;
                    const status = document.createElement('b'); status.textContent = ({ pending: 'در حال بررسی', approved: 'تأیید شد', shipped: 'ارسال شد', completed: 'تکمیل شد' })[order.status] || order.status || 'ثبت شد';
                    row.append(name, status); orderBox.appendChild(row);
                });
                smartWidget.hidden = false;
                try { localStorage.setItem('giso_thanks_seen', ids); } catch (_) { /* ignore */ }
            }
        }
    }

    applyCatalogState();
    loadRecommendations();
})();
