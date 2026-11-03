// hjDialog - one modal dialog for the whole site: confirm, text, textarea,
// select or alert, centred on the screen. Injected on every page.
//
//   const reason = await hjDialog.open({ type: 'textarea', title: 'Delete row', danger: true });
//   if (reason === null) return;   // cancelled
//
// Styling lives in css/Dialog.css (overridable like every framework asset -
// see WebServer/core/assets.py).

let _dlgStylesReady = null;

/** Adds the stylesheet once; resolves when it has loaded (or failed). */
function _ensureDialogStyles() {
    if (_dlgStylesReady) return _dlgStylesReady;
    let link = document.getElementById('hj-dialog-styles');
    if (!link) {
        link = document.createElement('link');
        link.id = 'hj-dialog-styles';
        link.rel = 'stylesheet';
        link.href = '/css/Dialog.css';
        document.head.appendChild(link);
    }
    _dlgStylesReady = new Promise(resolve => {
        if (link.sheet) { resolve(); return; }
        link.addEventListener('load', resolve);
        link.addEventListener('error', resolve);
    });
    return _dlgStylesReady;
}

const _DLG_TYPES = ['confirm', 'alert', 'text', 'textarea', 'select'];

/**
 * Open a dialog and wait for the answer.
 *
 * options:
 *   type         'confirm' (default) - OK/Cancel buttons only
 *                'alert'             - one OK button
 *                'text'              - single-line text field
 *                'textarea'          - multi-line text field (Ctrl+Enter confirms)
 *                'select'            - dropdown of `options`
 *   title        heading
 *   message      text under the heading (plain text, never HTML)
 *   label        caption above the field
 *   placeholder  field placeholder
 *   value        initial field value
 *   options      for 'select': ['a', 'b'] or [{ value, label }]
 *   required     field must be non-empty before confirming (default true)
 *   maxLength    longest allowed text
 *   confirmText  confirm button text (default 'OK')
 *   cancelText   cancel button text (default 'Cancel')
 *   danger       red confirm button, for destructive actions
 *   onConfirm    async function(value); throw to show the error in the dialog
 *                and keep it open (e.g. when the server refuses)
 *
 * Resolves to the field's value (text/textarea/select), true (confirm/alert),
 * or null when cancelled (Cancel, Escape or a click outside the box).
 */
async function _dlgOpen(options = {}) {
    const type = _DLG_TYPES.includes(options.type) ? options.type : 'confirm';
    const hasField = ['text', 'textarea', 'select'].includes(type);
    const required = options.required !== false;
    await _ensureDialogStyles();

    return new Promise(resolve => {
        const previousFocus = document.activeElement;
        const dialog = document.createElement('dialog');
        dialog.className = 'hj-dialog' + (options.danger ? ' hj-dialog-danger' : '');

        const form = document.createElement('form');
        form.className = 'hj-dialog-box';
        form.noValidate = true;
        dialog.appendChild(form);

        if (options.title) {
            const title = document.createElement('h2');
            title.className = 'hj-dialog-title';
            title.id = `hj-dialog-title-${Date.now()}`;
            title.textContent = options.title;
            form.appendChild(title);
            dialog.setAttribute('aria-labelledby', title.id);
        }
        if (options.message) {
            const message = document.createElement('p');
            message.className = 'hj-dialog-message';
            message.textContent = options.message;
            form.appendChild(message);
        }

        let field = null;
        if (hasField) {
            const wrap = document.createElement('label');
            wrap.className = 'hj-dialog-field';
            if (options.label) {
                const caption = document.createElement('span');
                caption.className = 'hj-dialog-label';
                caption.textContent = options.label;
                wrap.appendChild(caption);
            }
            if (type === 'select') {
                field = document.createElement('select');
                (options.options || []).forEach(o => {
                    const opt = document.createElement('option');
                    opt.value = typeof o === 'object' ? o.value : o;
                    opt.textContent = typeof o === 'object' ? (o.label ?? o.value) : o;
                    field.appendChild(opt);
                });
            } else {
                field = document.createElement(type === 'textarea' ? 'textarea' : 'input');
                if (type === 'text') field.type = 'text';
                if (type === 'textarea') field.rows = 4;
                if (options.placeholder) field.placeholder = options.placeholder;
                if (options.maxLength) field.maxLength = options.maxLength;
            }
            if (options.value !== undefined && options.value !== null) field.value = String(options.value);
            field.className = 'hj-dialog-input';
            wrap.appendChild(field);
            form.appendChild(wrap);
        }

        const error = document.createElement('p');
        error.className = 'hj-dialog-error';
        error.hidden = true;
        form.appendChild(error);

        const buttons = document.createElement('div');
        buttons.className = 'hj-dialog-buttons';
        let cancelBtn = null;
        if (type !== 'alert') {
            cancelBtn = document.createElement('button');
            cancelBtn.type = 'button';
            cancelBtn.className = 'hj-dialog-btn hj-dialog-cancel';
            cancelBtn.textContent = options.cancelText || 'Cancel';
            buttons.appendChild(cancelBtn);
        }
        const confirmBtn = document.createElement('button');
        confirmBtn.type = 'submit';
        confirmBtn.className = 'hj-dialog-btn hj-dialog-confirm';
        confirmBtn.textContent = options.confirmText || 'OK';
        buttons.appendChild(confirmBtn);
        form.appendChild(buttons);

        let busy = false;
        let done = false;
        const value = () => (field ? (type === 'select' ? field.value : field.value.trim()) : true);
        const empty = () => hasField && required && value() === '';
        const refresh = () => { confirmBtn.disabled = busy || empty(); };

        const finish = result => {
            if (done) return;
            done = true;
            dialog.close();
            dialog.remove();
            if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus();
            resolve(result);
        };
        const cancel = () => { if (!busy) finish(null); };

        form.addEventListener('submit', async e => {
            e.preventDefault();
            if (busy || empty()) return;
            const result = value();
            if (typeof options.onConfirm === 'function') {
                busy = true;
                refresh();
                if (cancelBtn) cancelBtn.disabled = true;
                error.hidden = true;
                try {
                    await options.onConfirm(result);
                } catch (err) {
                    error.textContent = err && err.message ? err.message : String(err);
                    error.hidden = false;
                    busy = false;
                    if (cancelBtn) cancelBtn.disabled = false;
                    refresh();
                    return;
                }
            }
            busy = false;
            finish(result);
        });
        if (cancelBtn) cancelBtn.addEventListener('click', cancel);
        // Escape: the browser fires 'cancel' on the dialog.
        dialog.addEventListener('cancel', e => { e.preventDefault(); cancel(); });
        // A click on the dialog element itself is a click on the backdrop.
        dialog.addEventListener('mousedown', e => { if (e.target === dialog) cancel(); });
        if (field) {
            field.addEventListener('input', refresh);
            if (type === 'textarea') {
                field.addEventListener('keydown', e => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); form.requestSubmit(); }
                });
            }
        }

        refresh();
        document.body.appendChild(dialog);
        dialog.showModal();
        (field || confirmBtn).focus();
    });
}

globalThis.hjDialog = {
    open: _dlgOpen,
    /** OK/Cancel. Resolves true, or null when cancelled. */
    confirm: (message, options = {}) => _dlgOpen({ ...options, type: 'confirm', message }),
    /** One OK button. Resolves true once closed with OK, null with Escape. */
    alert: (message, options = {}) => _dlgOpen({ ...options, type: 'alert', message }),
    /** A text field (options.type 'textarea' for several lines). Resolves the text, or null. */
    prompt: (message, options = {}) => _dlgOpen({ type: 'text', ...options, message }),
};
