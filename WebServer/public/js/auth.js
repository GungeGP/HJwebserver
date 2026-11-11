// Framework login overlay. The session lives in an HttpOnly cookie set by the
// server, so this file never sees or stores the token. It:
//   * renders the login form when the server says we're not authenticated
//     (username-first when the app uses Microsoft login: the server decides
//     whether a typed name goes to Microsoft or gets a password field)
//   * renders a change-password form when the server requires it (or on request)
//   * reloads the page after a successful login (so protected content is served)
//   * watches every fetch() for 401/403 and re-shows the right form
//   * exposes window.currentUser and window.hjAuth for your own page code
//
// Page hooks (all optional):
//   <button id="logout">            log out this browser
//   <button id="logout-all">        log out everywhere
//   <button id="change-password">   open the change-password form
//   window.addEventListener('hj:ready', e => ...)   fired once with e.detail.user (or null)

(function () {
    let config = { title: 'Access Restricted', message: 'Please log in to continue.', logo: null, rememberMe: true, minPasswordLength: 8,
                   ssoEnabled: false, ssoOnly: false };
    let roleHierarchy = null;   // from /api/verify, for hasRole()
    // Username-first form (ssoEnabled): 'name' until the server answers, then 'password' for local accounts.
    let stage = 'name';
    // Public pages (addPath(..., public=True)) never show the login form on
    // their own - only when the page asks for it with hjAuth.showLogin().
    const publicPage = document.currentScript?.dataset.hjPage === 'public';

    window.currentUser = null;

    window.hjAuth = {
        get user() { return window.currentUser; },
        logout,
        logoutEverywhere,
        changePassword,
        showChangePassword: () => showOverlay('change'),
        showLogin: () => showOverlay('login'),
        hasRole,
    };

    // Wrap fetch so auth failures from a protected route bring the right form back.
    const originalFetch = window.fetch.bind(window);
    window.fetch = async function (input, init) {
        const response = await originalFetch(input, init);
        const url = typeof input === 'string' ? input : (input && input.url) || '';
        if (url.includes('/api/login') || url.includes('/api/change-password')) { return response; }
        if (response.status === 401) {
            if (!publicPage) { showOverlay('login'); }
        } else if (response.status === 403) {
            try {
                const data = await response.clone().json();
                if (data && data.error === 'password_change_required') { showOverlay('change', true); }
            } catch (_) { /* not JSON */ }
        }
        return response;
    };

    window.addEventListener('DOMContentLoaded', async function () {
        const [cfg, session] = await Promise.all([loadConfig(), originalFetch('/api/verify')]);
        if (cfg) { config = { ...config, ...cfg }; }
        createOverlay();

        document.getElementById('logout')?.addEventListener('click', logout);
        document.getElementById('logout-all')?.addEventListener('click', logoutEverywhere);
        document.getElementById('change-password')?.addEventListener('click', () => showOverlay('change'));

        if (session.status === 200) {
            const data = await session.json();
            window.currentUser = data.user;
            roleHierarchy = data.roleHierarchy || null;
            if (data.user && data.user.source === 'microsoft') {
                // Their password lives at Microsoft.
                const button = document.getElementById('change-password');
                if (button) { button.style.display = 'none'; }
            }
            if (data.user && data.user.mustChangePassword) {
                showOverlay('change', true);
            } else {
                hideOverlay();
            }
        } else if (!publicPage) {
            showOverlay('login');
        }
        window.dispatchEvent(new CustomEvent('hj:ready', { detail: { user: window.currentUser } }));
    });

    async function loadConfig() {
        try {
            const r = await originalFetch('/api/login-config');
            return r.ok ? await r.json() : null;
        } catch (_) { return null; }
    }

    // ------------------------------------------------------------------ actions

    async function login(event) {
        if (event) { event.preventDefault(); }
        if (config.ssoEnabled && stage === 'name') { return startLogin(); }
        const userField = document.getElementById('username');
        const passField = document.getElementById('password');
        const remember = document.getElementById('remember-me');
        const username = userField?.value.trim();
        const password = passField?.value;

        if (!username || !password) {
            Notify('Username and password are required.', 'error');
            return;
        }

        try {
            const response = await originalFetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password, rememberMe: !!(remember && remember.checked) })
            });

            if (response.status === 200) {
                // The cookie is set; reload so the server serves the protected page.
                window.location.reload();
                return;
            }
            passField.value = '';
            updateLoginState();
            let message = 'Invalid username or password.';
            try { const data = await response.json(); if (data.error) { message = data.error; } } catch (_) { }
            Notify(message, 'error');
        } catch (error) {
            console.error('Login request failed:', error);
            Notify('Could not connect to the server.', 'error');
        }
    }

    // Username-first: ask the server where this name signs in.
    async function startLogin() {
        const userField = document.getElementById('username');
        const remember = document.getElementById('remember-me');
        const username = userField?.value.trim();
        if (!username) { Notify('Enter your username or work email.', 'error'); return; }

        document.getElementById('login-btn').disabled = true;
        let data = {};
        let response;
        try {
            response = await originalFetch('/api/login/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, next: location.pathname + location.search,
                                       rememberMe: !!(remember && remember.checked) })
            });
            try { data = await response.json(); } catch (_) { }
        } catch (error) {
            console.error('Login request failed:', error);
            Notify('Could not connect to the server.', 'error');
            updateLoginState();
            return;
        }

        if (response.ok && data.method === 'microsoft') {
            setStatus('Taking you to Microsoft sign-in…');
            userField.disabled = true;
            window.location.href = data.redirect;
        } else if (response.ok && data.method === 'password') {
            showPasswordStage();
        } else {
            Notify(data.error || 'Could not sign in.', 'error');
            updateLoginState();
        }
    }

    function showPasswordStage() {
        stage = 'password';
        document.getElementById('password').style.display = '';
        const remember = document.querySelector('.login-box label.remember');
        if (remember) { remember.style.display = ''; }
        document.getElementById('login-btn').textContent = 'Sign in';
        updateLoginState();
        document.getElementById('password').focus();
    }

    // Back to "type your name": any edit of the name after it was resolved.
    function resetToNameStage() {
        if (!config.ssoEnabled || stage === 'name') { return; }
        stage = 'name';
        const pass = document.getElementById('password');
        pass.value = '';
        pass.style.display = 'none';
        const remember = document.querySelector('.login-box label.remember');
        if (remember) { remember.style.display = 'none'; }
        document.getElementById('login-btn').textContent = 'Continue';
        setStatus('');
    }

    function setStatus(text) {
        const status = document.getElementById('login-status');
        if (status) { status.textContent = text; status.style.display = text ? '' : 'none'; }
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

    async function changePassword(currentPassword, newPassword) {
        const response = await originalFetch('/api/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ currentPassword, newPassword })
        });
        let data = {};
        try { data = await response.json(); } catch (_) { }
        return { ok: response.status === 200, error: data.error || null };
    }

    async function submitChangePassword(event) {
        if (event) { event.preventDefault(); }
        const current = document.getElementById('current-password');
        const next = document.getElementById('new-password');
        const confirm = document.getElementById('confirm-password');

        if (!current.value || !next.value) { Notify('All fields are required.', 'error'); return; }
        if (next.value !== confirm.value) { Notify('New passwords do not match.', 'error'); return; }
        if (next.value.length < config.minPasswordLength) {
            Notify(`Password must be at least ${config.minPasswordLength} characters.`, 'error'); return;
        }

        const result = await changePassword(current.value, next.value);
        if (result.ok) {
            Notify('Password changed.', 'info');
            window.location.reload();
        } else {
            current.value = '';
            Notify(result.error || 'Could not change password.', 'error');
        }
    }

    async function logout() { await endSession('/api/logout'); }

    async function logoutEverywhere() { await endSession('/api/logout-all'); }

    // A Microsoft user also gets signed out at Microsoft (microsoftLogout):
    // the server answers with where to go for that.
    async function endSession(url) {
        let redirect = null;
        try {
            const response = await originalFetch(url, { method: 'POST' });
            try { redirect = (await response.json()).redirect || null; } catch (_) { }
        } catch (error) { console.error('Logout request failed:', error); }
        if (redirect) { window.location.href = redirect; } else { window.location.reload(); }
    }

    // ------------------------------------------------------------------ UI

    function updateLoginState() {
        const username = document.getElementById('username')?.value.trim();
        const password = document.getElementById('password')?.value;
        const submitBtn = document.getElementById('login-btn');
        const needsPassword = !config.ssoEnabled || stage === 'password';
        if (submitBtn) { submitBtn.disabled = !(username && (password || !needsPassword)); }
    }

    function showOverlay(mode, forced) {
        const overlay = document.getElementById('login-overlay');
        if (!overlay) { return; }
        overlay.style.display = 'flex';
        overlay.dataset.mode = mode;
        document.getElementById('login-form').style.display = mode === 'login' ? 'flex' : 'none';
        document.getElementById('change-form').style.display = mode === 'change' ? 'flex' : 'none';
        const cancel = document.getElementById('change-cancel');
        if (cancel) { cancel.style.display = forced ? 'none' : ''; }
        const note = document.getElementById('change-note');
        if (note) { note.textContent = forced ? 'You must set a new password before continuing.' : 'Choose a new password.'; }
        if (mode === 'login') { resetToNameStage(); }
        (mode === 'login' ? document.getElementById('username') : document.getElementById('current-password'))?.focus();
    }

    function hideOverlay() {
        const overlay = document.getElementById('login-overlay');
        if (overlay) { overlay.style.display = 'none'; }
    }

    function createOverlay() {
        if (document.getElementById('login-overlay')) { return; }
        // Styling lives in the sibling css/auth.css (served/overridable the
        // same way as this file - see WebServer/__init__.py's serve_auth_css).
        if (!document.getElementById('auth-styles')) {
            const link = document.createElement('link');
            link.id = 'auth-styles';
            link.rel = 'stylesheet';
            link.href = '/css/auth.css';
            document.head.appendChild(link);
        }

        const overlay = document.createElement('div');
        overlay.id = 'login-overlay';
        overlay.innerHTML = `
            <div class="login-box">
                <div class="headerLine"></div>
                ${config.logo ? '<img class="logo" alt="">' : ''}
                <form id="login-form">
                    <h2></h2>
                    <p></p>
                    <input type="text" id="username" placeholder="${config.ssoEnabled ? 'Username or work email' : 'Username'}" autocomplete="username">
                    <input type="password" id="password" placeholder="Password" autocomplete="current-password"${config.ssoEnabled ? ' style="display:none"' : ''}>
                    ${config.rememberMe ? `<label class="remember"${config.ssoEnabled ? ' style="display:none"' : ''}><input type="checkbox" id="remember-me"> Remember me</label>` : ''}
                    <p id="login-status" class="status" style="display:none"></p>
                    <button id="login-btn" disabled type="submit">${config.ssoEnabled ? 'Continue' : 'Sign In'}</button>
                </form>
                <form id="change-form" style="display:none">
                    <h2>Change password</h2>
                    <p id="change-note"></p>
                    <input type="password" id="current-password" placeholder="Current password" autocomplete="current-password">
                    <input type="password" id="new-password" placeholder="New password" autocomplete="new-password">
                    <input type="password" id="confirm-password" placeholder="Repeat new password" autocomplete="new-password">
                    <button id="change-btn" type="submit">Change password</button>
                    <button id="change-cancel" type="button" class="secondary">Cancel</button>
                </form>
            </div>
        `;
        document.body.appendChild(overlay);

        // Text is set via textContent so server-provided strings are never parsed as HTML.
        overlay.querySelector('#login-form h2').textContent = config.title;
        overlay.querySelector('#login-form p').textContent = config.message;
        if (config.logo) { overlay.querySelector('img.logo').src = config.logo; }

        const loginForm = document.getElementById('login-form');
        loginForm.addEventListener('submit', login);
        // Explicit Enter handling; preventDefault stops the implicit submit so login() runs once.
        loginForm.addEventListener('keydown', (e) => { if (e.key === 'Enter') { login(e); } });
        document.getElementById('username').addEventListener('input', () => { resetToNameStage(); updateLoginState(); });
        document.getElementById('password').addEventListener('input', updateLoginState);

        const changeForm = document.getElementById('change-form');
        changeForm.addEventListener('submit', submitChangePassword);
        changeForm.addEventListener('keydown', (e) => { if (e.key === 'Enter') { submitChangePassword(e); } });
        document.getElementById('change-cancel').addEventListener('click', hideOverlay);
    }
})();
