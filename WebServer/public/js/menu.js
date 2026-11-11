// Side menu (app.menu in main.py). Injected only once the app has a menu.
// The server draws the menu right after <body> and puts its items in the page
// as JSON (see WebServer/menu.py); this file:
//   * exposes the items the user may see as window.hjMenu.items
//   * folds the menu to its narrow form and back with the «/» button, and
//     remembers the choice in localStorage between pages
//   * folds sub-items in and out with the arrow next to their item
//   * fetches each item's count address after the page is shown, and shows
//     the number; an address that fails or answers anything but a number shows nothing
//
// hjMenu.items is set before DOMContentLoaded (and so before hj:ready):
//   [{title, url, desc, short, count, active, disabled, items: [...]}, ...]
//
// Styling lives in css/menu.css, linked by the server next to the menu
// (overridable like every framework asset - see WebServer/core/assets.py).

(function () {
    const COLLAPSED_KEY = 'hj:menu-collapsed';   // same key as WebServer/menu.py

    let items = [];
    try {
        const data = document.getElementById('hj-menu-data');
        if (data) { items = JSON.parse(data.textContent) || []; }
    } catch (_) { items = []; }
    window.hjMenu = { items };

    const nav = document.getElementById('hj-menu');
    if (!nav) { return; }   // app.menu(sidebar=False), or a page with menu=False

    // --- folding the whole menu ----------------------------------------------

    const toggle = nav.querySelector('.hj-menu-toggle');

    function setCollapsed(collapsed) {
        nav.classList.toggle('collapsed', collapsed);
        if (toggle) {
            const label = collapsed ? 'Fold menuen ud' : 'Klap menuen sammen';
            toggle.textContent = collapsed ? '»' : '«';   // » / «
            toggle.title = label;
            toggle.setAttribute('aria-label', label);
            toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        }
    }

    let stored = false;
    try { stored = localStorage.getItem(COLLAPSED_KEY) === '1'; } catch (_) { /* storage blocked */ }
    setCollapsed(stored);

    toggle?.addEventListener('click', function () {
        const collapsed = !nav.classList.contains('collapsed');
        setCollapsed(collapsed);
        try { localStorage.setItem(COLLAPSED_KEY, collapsed ? '1' : '0'); } catch (_) { /* storage blocked */ }
    });

    // --- sub-items -----------------------------------------------------------

    for (const arrow of nav.querySelectorAll('.hj-menu-arrow')) {
        arrow.addEventListener('click', function () {
            const item = arrow.closest('.hj-menu-item');
            const open = !item.classList.contains('open');
            item.classList.toggle('open', open);
            arrow.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
    }

    // --- counts --------------------------------------------------------------

    const byUrl = new Map();
    for (const el of nav.querySelectorAll('[data-hj-count]')) {
        const url = el.dataset.hjCount;
        if (!byUrl.has(url)) { byUrl.set(url, []); }
        byUrl.get(url).push(el);
    }

    async function loadCount(url, elements) {
        try {
            const response = await fetch(url, { headers: { 'Accept': 'application/json' } });
            if (!response.ok) { return; }
            const value = await response.json();
            if (typeof value !== 'number' || !Number.isFinite(value)) { return; }
            for (const el of elements) {
                el.textContent = String(value);
                el.hidden = false;
            }
        } catch (_) { /* no answer, or not JSON: no number */ }
    }

    function loadCounts() {
        for (const [url, elements] of byUrl) { loadCount(url, elements); }
    }

    // After the page is shown, so the counts never hold it up.
    if (document.readyState === 'complete') { loadCounts(); }
    else { window.addEventListener('load', loadCounts, { once: true }); }
})();
