// Framework auth helpers for an app behind Authentik. Authentik logs the user
// in before a request ever reaches the server, so there is no login form here.
// This file:
//   * asks /api/verify who is logged in, and exposes it as window.currentUser / hjAuth.user
//   * puts the form token (X-CSRF-Token) on every POST, PUT and DELETE fetch() to this site
//   * reloads the page when a call answers 401, so Authentik can show its login
//   * fires hj:ready on window once, with e.detail.user (or null)
//
// Page hooks (all optional):
//   <button id="logout">            log out (at Authentik, for every app behind it)
//   window.addEventListener('hj:ready', e => ...)   fired once with e.detail.user (or null)

(function () {
    const TOKEN_HEADER = 'X-CSRF-Token';
    const CHANGING = ['POST', 'PUT', 'PATCH', 'DELETE'];
    let roleHierarchy = null;   // from /api/verify, for hasRole()
    let csrfToken = null;       // from /api/verify, bound to the user
    // Public pages (addPath(..., public=True)) are never reloaded on a 401:
    // Authentik lets them through without a login, so a reload wouldn't bring one.
    const publicPage = document.currentScript?.dataset.hjPage === 'public';

    window.currentUser = null;

    window.hjAuth = {
        get user() { return window.currentUser; },
        logout,
        hasRole,
    };

    const originalFetch = window.fetch.bind(window);
    // Started right away, so a POST sent before the page has loaded can wait for its token.
    const verified = verify();

    window.fetch = async function (input, init) {
        const url = typeof input === 'string' ? input : (input && input.url) || String(input);
        const method = ((init && init.method) || (input instanceof Request ? input.method : 'GET')).toUpperCase();
        if (CHANGING.includes(method) && sameOrigin(url)) {
            await verified;
            if (csrfToken) {
                const headers = new Headers((init && init.headers) || (input instanceof Request ? input.headers : undefined));
                headers.set(TOKEN_HEADER, csrfToken);
                init = { ...(init || {}), headers };
            }
        }
        const response = await originalFetch(input, init);
        if (response.status === 401 && !publicPage) { reloadForLogin(); }
        return response;
    };

    window.addEventListener('DOMContentLoaded', async function () {
        await verified;
        document.getElementById('logout')?.addEventListener('click', logout);
        window.dispatchEvent(new CustomEvent('hj:ready', { detail: { user: window.currentUser } }));
    });

    async function verify() {
        try {
            const response = await originalFetch('/api/verify', { headers: { 'Accept': 'application/json' } });
            if (response.status === 200) {
                const data = await response.json();
                window.currentUser = data.user;
                roleHierarchy = data.roleHierarchy || null;
                csrfToken = data.csrfToken || null;
            } else if (response.status === 401 && !publicPage) {
                reloadForLogin();
            }
        } catch (_) { /* not logged in on a public page, or the server is gone */ }
    }

    function sameOrigin(url) {
        try { return new URL(url, window.location.href).origin === window.location.origin; }
        catch (_) { return false; }
    }

    // Authentik shows its login when the page is loaded again. At most once
    // every 10 seconds, so a path Authentik lets through without login can't
    // make the page reload forever.
    function reloadForLogin() {
        const key = 'hj:auth-reload';
        try {
            const last = Number(sessionStorage.getItem(key) || 0);
            if (Date.now() - last < 10000) {
                console.error('auth.js: the server says no one is logged in, right after a reload. Is this path protected in Authentik?');
                return;
            }
            sessionStorage.setItem(key, String(Date.now()));
        } catch (_) { return; }
        window.location.reload();
    }

    // "this role or higher" with roleHierarchy, exact match without - same rule as the server.
    function hasRole(role) {
        const mine = window.currentUser && window.currentUser.role;
        if (!mine) { return false; }
        if (mine === role) { return true; }
        if (!roleHierarchy) { return false; }
        const rank = roleHierarchy.indexOf(mine);
        const needed = roleHierarchy.indexOf(role);
        return rank !== -1 && needed !== -1 && rank <= needed;
    }

    // GET /logout records it and sends the browser on to Authentik's sign-out.
    function logout() { window.location.href = '/logout'; }
})();
