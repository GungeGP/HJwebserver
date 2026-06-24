// default.js
// This file is served by the framework at /default.js
// and automatically injected into HTML pages.

console.log('default.js loaded: shared client script is running');

// Example shared behavior:
// Add a small on-page badge to prove the file loaded successfully.
const defaultScriptBadge = document.createElement('div');
defaultScriptBadge.textContent = 'Shared default.js loaded';
defaultScriptBadge.style.position = 'fixed';
defaultScriptBadge.style.bottom = '10px';
defaultScriptBadge.style.right = '10px';
defaultScriptBadge.style.padding = '8px 12px';
defaultScriptBadge.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
defaultScriptBadge.style.color = '#fff';
defaultScriptBadge.style.fontSize = '12px';
defaultScriptBadge.style.borderRadius = '4px';
defaultScriptBadge.style.zIndex = '9999';
if (document.body) {
    document.body.appendChild(defaultScriptBadge);
} else {
    window.addEventListener('DOMContentLoaded', () => document.body.appendChild(defaultScriptBadge));
}
