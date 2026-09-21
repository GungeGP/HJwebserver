// Framework login overlay. The session lives in an HttpOnly cookie set by the
// server, so this file never sees or stores the token. It only:
//   * renders the login form when the server says we're not authenticated
//   * reloads the page after a successful login (so protected content is served)
//   * watches every fetch() for a 401 and re-shows the form when a session expires

(function () {
    // Wrap fetch so any 401 from a protected route brings the login form back.
    const originalFetch = window.fetch.bind(window);
    window.fetch = async function (input, init) {
        const response = await originalFetch(input, init);
        const url = typeof input === 'string' ? input : (input && input.url) || '';
        if (response.status === 401 && !url.includes('/api/login')) {
            showLoginOverlay();
        }
        return response;
    };

    window.addEventListener('DOMContentLoaded', function () {
        createLoginOverlay();
        verifySession();

        const form = document.getElementById('login-form');
        form?.addEventListener('submit', login);
        // Explicit Enter handling; preventDefault stops the implicit submit so login() runs once.
        form?.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') { login(event); }
        });
        document.getElementById('username')?.addEventListener('input', updateSubmitState);
        document.getElementById('password')?.addEventListener('input', updateSubmitState);

        // Optional: any element with id="logout" on the page becomes a logout button.
        document.getElementById('logout')?.addEventListener('click', logout);
    });
})();

async function verifySession() {
    try {
        const response = await fetch('/api/verify');
        if (response.status === 200) {
            hideLoginOverlay();
        } else {
            showLoginOverlay();
        }
    } catch (error) {
        console.error('Server connection failed:', error);
    }
}

async function login(event) {
    if (event) { event.preventDefault(); }

    const userField = document.getElementById('username');
    const passField = document.getElementById('password');
    const username = userField?.value.trim();
    const password = passField?.value;

    if (!username || !password) {
        Notify('Username and password are required.', 'error');
        return;
    }

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        if (response.status === 200) {
            // The cookie is set; reload so the server serves the protected page.
            window.location.reload();
        } else {
            passField.value = '';
            updateSubmitState();
            Notify('Invalid username or password.', 'error');
        }
    } catch (error) {
        console.error('Login request failed:', error);
        Notify('Could not connect to the server.', 'error');
    }
}

async function logout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
    } catch (error) {
        console.error('Logout request failed:', error);
    }
    window.location.reload();
}

function updateSubmitState() {
    const username = document.getElementById('username')?.value.trim();
    const password = document.getElementById('password')?.value;
    const submitBtn = document.getElementById('login-btn');
    if (submitBtn) { submitBtn.disabled = !(username && password); }
}

function showLoginOverlay() {
    const overlay = document.getElementById('login-overlay');
    if (overlay) {
        overlay.style.display = 'flex';
        document.getElementById('username')?.focus();
    }
}
function hideLoginOverlay() {
    const overlay = document.getElementById('login-overlay');
    if (overlay) { overlay.style.display = 'none'; }
}

function createLoginOverlay() {
    if (document.getElementById('login-overlay')) { return; }
    const style = document.createElement('style');
    style.textContent = `
        /* The full-screen background */
        #login-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background-color: rgba(0, 0, 0, 0.5); /* Dark, slightly transparent background */
            /* blur background */
            backdrop-filter: blur(5px);

            /* Flexbox centers the login box perfectly in the middle of the screen */
            display: none;
            justify-content: center;
            align-items: center;

            z-index: 9999; /* Ensures it sits on top of absolutely everything else */
        }
        /* The white box in the middle */
        .login-box {
            background-color: white;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            width: clamp(300px, 30vw, 400px);
        }
        .login-box input {
            display: block;
            width: 100%;
            margin-bottom: 15px;
            padding: 10px;
            box-sizing: border-box;
        }
        .headerLine {
            width: 100%;
            height: 1vh;
            background-color: #153e2c;
            border-radius: 10px 10px 0px 0px;
        }
        #login-form {
            display: flex;
            flex-direction: column;
            padding: 20px;
        }
        #login-form h2 {
            margin-top: 0;
            margin-bottom: 10px;
            font-size: clamp(1.5rem, 1.5vw, 2rem);
        }
        #login-form p {
            margin-top: 0;
            margin-bottom: 20px;
            color: #555;
            font-size: clamp(0.9rem, 0.9vw, 1.1rem);
        }

        #login-form input[type="text"],
        #login-form input[type="password"] {
        border: 1px solid #E3EDF3;
        border-radius: 10px;
        padding: 10px;
        font-size: 1em;
        }
        #login-form input[type="text"]:focus,
        #login-form input[type="password"]:focus {
        outline: none;
        border-color: #00563B;
        }

        #login-form button {
        background-color: #00563B;
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px;
        font-size: 1em;
        cursor: pointer;
        }
        #login-form button:disabled {
        background-color: #E3EDF3;
        color: #2C3531;
        cursor: not-allowed;
        }
    `;
    document.head.appendChild(style);

    const overlay = document.createElement('div');
    overlay.id = 'login-overlay';
    overlay.innerHTML = `
        <div class="login-box">
            <div class="headerLine"></div>
            <form id="login-form">
                <h2>Access Restricted</h2>
                <p>Please log in to continue.</p>
                <input type="text" id="username" placeholder="Username" autocomplete="username">
                <input type="password" id="password" placeholder="Password" autocomplete="current-password">
                <button id="login-btn" disabled type="submit">Sign In</button>
            </form>
        </div>
    `;

    document.body.appendChild(overlay);
}
