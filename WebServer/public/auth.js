// Framework login overlay. The session lives in an HttpOnly cookie set by the
// server, so this file never sees or stores the token. It:
//   * renders the login form when the server says we're not authenticated
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
    let config = { title: 'Access Restricted', message: 'Please log in to continue.', logo: null, rememberMe: true, minPasswordLength: 8 };

    window.currentUser = null;

    window.hjAuth = {
        get user() { return window.currentUser; },
        logout,
        logoutEverywhere,
        changePassword,
        showChangePassword: () => showOverlay('change'),
        showLogin: () => showOverlay('login'),
    };

    // Wrap fetch so auth failures from a protected route bring the right form back.
    const originalFetch = window.fetch.bind(window);
    window.fetch = async function (input, init) {
        const response = await originalFetch(input, init);
        const url = typeof input === 'string' ? input : (input && input.url) || '';
        if (url.includes('/api/login') || url.includes('/api/change-password')) { return response; }
        if (response.status === 401) {
            showOverlay('login');
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
            if (data.user && data.user.mustChangePassword) {
                showOverlay('change', true);
            } else {
                hideOverlay();
            }
        } else {
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

    async function logout() {
        try { await originalFetch('/api/logout', { method: 'POST' }); }
        catch (error) { console.error('Logout request failed:', error); }
        window.location.reload();
    }

    async function logoutEverywhere() {
        try { await originalFetch('/api/logout-all', { method: 'POST' }); }
        catch (error) { console.error('Logout request failed:', error); }
        window.location.reload();
    }

    // ------------------------------------------------------------------ UI

    function updateLoginState() {
        const username = document.getElementById('username')?.value.trim();
        const password = document.getElementById('password')?.value;
        const submitBtn = document.getElementById('login-btn');
        if (submitBtn) { submitBtn.disabled = !(username && password); }
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
        (mode === 'login' ? document.getElementById('username') : document.getElementById('current-password'))?.focus();
    }

    function hideOverlay() {
        const overlay = document.getElementById('login-overlay');
        if (overlay) { overlay.style.display = 'none'; }
    }

    function createOverlay() {
        if (document.getElementById('login-overlay')) { return; }
        const style = document.createElement('style');
        style.textContent = `
            #login-overlay {
                position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
                background-color: rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(5px);
                display: none; justify-content: center; align-items: center;
                z-index: 9999;
            }
            .login-box {
                background-color: white; border-radius: 10px; text-align: center;
                box-shadow: 0 4px 15px rgba(0,0,0,0.5);
                width: clamp(300px, 30vw, 400px);
            }
            .login-box .headerLine {
                width: 100%; height: 1vh; background-color: #153e2c; border-radius: 10px 10px 0 0;
            }
            .login-box img.logo { max-height: 60px; max-width: 80%; margin: 16px auto 0; display: block; }
            .login-box form { display: flex; flex-direction: column; padding: 20px; }
            .login-box h2 { margin: 0 0 10px; font-size: clamp(1.5rem, 1.5vw, 2rem); }
            .login-box p { margin: 0 0 20px; color: #555; font-size: clamp(0.9rem, 0.9vw, 1.1rem); }
            .login-box input[type="text"], .login-box input[type="password"] {
                display: block; width: 100%; box-sizing: border-box; margin-bottom: 15px;
                border: 1px solid #E3EDF3; border-radius: 10px; padding: 10px; font-size: 1em;
            }
            .login-box input:focus { outline: none; border-color: #00563B; }
            .login-box label.remember {
                display: flex; align-items: center; gap: 8px; margin: -5px 0 15px;
                font-size: 0.9em; color: #555; text-align: left;
            }
            .login-box button {
                background-color: #00563B; color: white; border: none; border-radius: 10px;
                padding: 10px; font-size: 1em; cursor: pointer;
            }
            .login-box button:disabled { background-color: #E3EDF3; color: #2C3531; cursor: not-allowed; }
            .login-box button.secondary { background: none; color: #00563B; margin-top: 8px; }
        `;
        document.head.appendChild(style);

        const overlay = document.createElement('div');
        overlay.id = 'login-overlay';
        overlay.innerHTML = `
            <div class="login-box">
                <div class="headerLine"></div>
                ${config.logo ? '<img class="logo" alt="">' : ''}
                <form id="login-form">
                    <h2></h2>
                    <p></p>
                    <input type="text" id="username" placeholder="Username" autocomplete="username">
                    <input type="password" id="password" placeholder="Password" autocomplete="current-password">
                    ${config.rememberMe ? '<label class="remember"><input type="checkbox" id="remember-me"> Remember me</label>' : ''}
                    <button id="login-btn" disabled type="submit">Sign In</button>
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
        document.getElementById('username').addEventListener('input', updateLoginState);
        document.getElementById('password').addEventListener('input', updateLoginState);

        const changeForm = document.getElementById('change-form');
        changeForm.addEventListener('submit', submitChangePassword);
        changeForm.addEventListener('keydown', (e) => { if (e.key === 'Enter') { submitChangePassword(e); } });
        document.getElementById('change-cancel').addEventListener('click', hideOverlay);
    }
})();
