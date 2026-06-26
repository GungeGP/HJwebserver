window.onload = function() {
    console.log("Initializing authentication overlay...");
    createLoginOverlay();
    showLoginOverlay();
    verifySession();

    document.getElementById('username')?.addEventListener('input', function() {
        const submitBtn = document.getElementById('login-btn');
        if (this.value.length >= 1) {
            submitBtn.disabled = false;
        } else {
            submitBtn.disabled = true;
        }
    });

    document.getElementById('logout')?.addEventListener('click', () => {
        localStorage.removeItem("credentials");
        document.getElementById("login-btn").disabled = true;
        showLoginOverlay();
    });
};

async function verifySession() {
    const token = localStorage.getItem("credentials");
    if (!token) { return; }
    try {
        const response = await fetch("/api/verify", {
            method: "GET",
            headers: { "Authorization": `Bearer ${token}` }
        });

        if (response.status === 200) {
            hideLoginOverlay();
        } else { localStorage.removeItem("credentials"); }
    } catch (error) {
        console.error("Server connection failed:", error);
    }
}

document.addEventListener("keypress", function(event) {
    if (event.key === "Enter") {
        const loginOverlay = document.getElementById("login-overlay");
        if (loginOverlay?.style.display !== "none") { login(); }
    }
});

async function login() {
    if (event) { event.preventDefault(); }

    const userField = document.getElementById("username");
    const passField = document.getElementById("password");

    const username = userField?.value;
    const password = passField?.value;

    if (!username) {
        Notify("Username cannot be empty.", "error");
        return;
    }

    try {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ username: username, password: password })
        });

        if (response.status === 200) {
            const data = await response.json();
            localStorage.setItem("credentials", data.token);
            hideLoginOverlay();
            userField.value = "";
            passField.value = "";
        } else {
            Notify("Invalid username or password.", "error");
        }
    } catch (error) {
        console.error("Login request failed:", error);
        Notify("Could not connect to the server.", "error");
    }
}

function showLoginOverlay() {
    const overlay = document.getElementById("login-overlay");
    if (overlay) { overlay.style.display = "flex"; }
}
function hideLoginOverlay() {
    const overlay = document.getElementById("login-overlay");
    if (overlay) { overlay.style.display = "none"; }
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
            display: flex; 
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
                <button id="login-btn" disabled onclick="login()" type="submit">Sign In</button>
            </form>
        </div>
    `;

    document.body.appendChild(overlay);
}
