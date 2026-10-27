// Styling lives in css/TableViewer.css (served/overridable the same way as
// this file - see WebServer/core/assets.py).
let _tvStylesLoaded = false;
let _tvStylesReady = null;

/** Adds the stylesheet once; resolves when it has loaded (or failed). */
function _ensureTableViewerStyles() {
    let link = document.getElementById('tableviewer-styles');
    if (!link) {
        link = document.createElement('link');
        link.id = 'tableviewer-styles';
        link.rel = 'stylesheet';
        link.href = '/css/TableViewer.css';
        document.head.appendChild(link);
    }
    if (!_tvStylesReady) {
        _tvStylesReady = new Promise(resolve => {
            if (link.sheet) { resolve(); return; }
            link.addEventListener('load', resolve);
            link.addEventListener('error', resolve);
        }).then(() => { _tvStylesLoaded = true; });
    }
    return _tvStylesReady;
}

// Trash can for the delete button; stroke follows the button's (red) text colour.
const _TV_TRASH_ICON = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" '
    + 'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    + '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/>'
    + '<path d="M10 11v6"/><path d="M14 11v6"/></svg>';

// --- value formatting -------------------------------------------------------
// The server sends dates and times as ISO strings ("2025-11-10T07:30:00").
// Display is DD-MM-YYYY / HH:MM; the browser's pickers want YYYY-MM-DD / HH:MM.

const _tvPad = n => String(n).padStart(2, '0');

function _tvParts(value) {
    const s = String(value);
    const d = /(\d{4})-(\d{2})-(\d{2})/.exec(s);
    const t = /(\d{2}):(\d{2})/.exec(d ? s.slice(d.index + 10) : s);
    return {
        date: d ? d[0] : '',
        displayDate: d ? `${d[3]}-${d[2]}-${d[1]}` : '',
        time: t ? `${t[1]}:${t[2]}` : '',
    };
}

function _tvDisplay(value, kind) {
    if (value === null || value === undefined || value === '') return null;
    const p = _tvParts(value);
    if (kind === 'date') return p.displayDate || String(value);
    if (kind === 'time') return p.time || String(value);
    if (kind === 'datetime') return p.displayDate ? `${p.displayDate} ${p.time}`.trim() : String(value);
    if (kind === 'bool') return value === true || value === 1 || value === '1' ? 'Yes' : 'No';
    return String(value);
}

function _tvInputValue(value, kind) {
    if (value === null || value === undefined) return '';
    const p = _tvParts(value);
    if (kind === 'date') return p.date;
    if (kind === 'time') return p.time;
    if (kind === 'datetime') return p.date && p.time ? `${p.date}T${p.time}` : '';
    return String(value);
}

function _tvWordMatch(label, query) {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    const l = String(label).toLowerCase();
    return l.startsWith(q) || l.split(/\s+/).some(w => w.startsWith(q));
}

class TableViewer {
    /**
     * @param {HTMLElement} container
     * @param {object} [options]
     * @param {string} [options.url] - server endpoint (see WebServer.addTableViewer).
     *   Omit it to use setData(rows) for a plain, unpaginated table instead.
     * @param {string[]|null} [options.columns] - restrict displayed columns
     *   (default: every column the server/data returns)
     * @param {number} [options.limit] - rows per page requested from the server
     */
    constructor(container, { url = null, columns = null, limit = null } = {}) {
        this.container = container;
        this.url = url || container.dataset.tableviewer || null;
        this.filterColumns = columns || (container.dataset.tableviewerColumns
            ? container.dataset.tableviewerColumns.split(',').map(c => c.trim())
            : null);
        this.limit = limit || parseInt(container.dataset.tableviewerLimit || '', 10) || 40;

        this.page = 1;
        this.search = '';
        this.sort = null;
        this.sortDir = 'asc';
        this.rows = [];
        this.columns = [];
        this.columnsMeta = {};
        this.filters = [];
        this.filterValues = null;   // null until the server has told us the defaults
        this.total = 0;
        this.totalPages = 1;
        this.primaryKey = [];
        this.canEdit = false;
        this.canDelete = false;
        this._searchTimer = null;
        this._paginated = Boolean(this.url);
        this._loadToken = 0;
        this._hasRendered = false;

        _ensureTableViewerStyles();
        this._buildShell();
    }

    _buildShell() {
        this.container.classList.add('tableviewer-wrap');
        this.container.innerHTML = '';

        if (this._paginated) {
            const toolbar = document.createElement('div');
            toolbar.className = 'tableviewer-toolbar';
            this.filterBarEl = document.createElement('div');
            this.filterBarEl.className = 'tableviewer-filters';
            const search = document.createElement('input');
            search.type = 'search';
            search.placeholder = 'Search…';
            search.className = 'tableviewer-search';
            search.addEventListener('input', () => {
                clearTimeout(this._searchTimer);
                this._searchTimer = setTimeout(() => {
                    this.search = search.value;
                    this.page = 1;
                    this.load();
                }, 300);
            });
            toolbar.append(this.filterBarEl, search);
            this.container.appendChild(toolbar);
        }

        this.errorEl = document.createElement('div');
        this.errorEl.className = 'tableviewer-error';
        this.errorEl.hidden = true;
        this.container.appendChild(this.errorEl);

        const scroll = document.createElement('div');
        scroll.className = 'tableviewer-scroll';
        this.progressEl = document.createElement('div');
        this.progressEl.className = 'tableviewer-progress';
        this.progressEl.hidden = true;
        this.tableEl = document.createElement('table');
        this.tableEl.className = 'tableviewer';
        scroll.append(this.progressEl, this.tableEl);
        this.scrollEl = scroll;
        this.container.appendChild(scroll);

        if (this._paginated) {
            this.paginationEl = document.createElement('div');
            this.paginationEl.className = 'tableviewer-pagination';
            this.container.appendChild(this.paginationEl);
        }
    }

    /** Fetch the current page/search/sort/filters from the server (only when constructed with a url). */
    async load() {
        if (!this.url) return this;

        const params = new URLSearchParams({ page: this.page, limit: this.limit });
        if (this.search) params.set('search', this.search);
        if (this.sort) { params.set('sort', this.sort); params.set('dir', this.sortDir); }
        if (this.filterValues) {
            Object.entries(this.filterValues).forEach(([k, v]) => params.set(k, v ?? ''));
        }
        const separator = this.url.includes('?') ? '&' : '?';

        // Only the newest request may update the table: clicking the day arrow
        // twice quickly must not let a slow first answer overwrite the second.
        const token = ++this._loadToken;
        let slow = null;
        if (this._hasRendered) {
            // Fast answers show no loader at all, so quick clicks don't flicker.
            slow = setTimeout(() => { if (token === this._loadToken) this._setLoading(true); }, 150);
        } else {
            this._setLoading(true);
        }

        try {
            const res = await fetch(`${this.url}${separator}${params}`);
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                // Not logged in (or a password change is pending): auth.js is
                // showing its form, and the page reloads after login. Keep the
                // placeholder rows (or the rows already shown) underneath it
                // rather than an error message.
                if (res.status === 401 || data.error === 'password_change_required') return this;
                throw new Error(data.error || `HTTP ${res.status}`);
            }
            const data = await res.json();
            if (token !== this._loadToken) return this;

            this.rows = data.rows || [];
            this.columns = this.filterColumns || data.columns
                || (this.rows.length ? Object.keys(this.rows[0]).filter(k => k !== '__meta') : []);
            this.columnsMeta = {};
            (data.columnsMeta || []).forEach(m => { this.columnsMeta[m.key] = m; });
            this.total = data.total ?? this.rows.length;
            this.totalPages = data.totalPages ?? 1;
            this.page = data.page ?? this.page;
            this.primaryKey = data.primaryKey || [];
            // The server's starting order (sort=), so the header shows its arrow.
            if (!this.sort && data.sort) { this.sort = data.sort; this.sortDir = data.sortDir || 'asc'; }
            this.canEdit = Boolean(data.canEdit);
            this.canDelete = Boolean(data.canDelete) && typeof globalThis.hjDialog === 'object';
            if (!data.columnsMeta && this.canEdit) {
                // Older/hand-written endpoints: every non-key column edits as text.
                this.columns.forEach(c => {
                    this.columnsMeta[c] = { key: c, kind: 'text', editable: !this.primaryKey.includes(c) };
                });
            }
            this.filters = data.filters || [];
            this.filterValues = {};
            this.filters.forEach(f => { this.filterValues[f.key] = f.value ?? ''; });

            this.errorEl.hidden = true;
            this.scrollEl.hidden = false;
            this._render();
        } catch (err) {
            if (token !== this._loadToken) return this;
            this.errorEl.textContent = `Failed to load table: ${err.message}`;
            this.errorEl.hidden = false;
            this.scrollEl.hidden = true;
            if (this.paginationEl) this.paginationEl.replaceChildren();
        } finally {
            clearTimeout(slow);
            if (token === this._loadToken) this._setLoading(false);
        }
        return this;
    }

    // --- loading state ------------------------------------------------------

    /** Before the first answer: placeholder rows. After that: dim the current
     *  rows and run a progress bar, so the table doesn't jump around. */
    _setLoading(on) {
        this._loading = on;
        this.scrollEl.setAttribute('aria-busy', on ? 'true' : 'false');
        this.progressEl.hidden = !on;
        if (on && !this._hasRendered) {
            this._renderSkeleton();
            return;
        }
        this.scrollEl.classList.toggle('tableviewer-busy', on);
    }

    _renderSkeleton() {
        this.tableEl.innerHTML = '';
        const columns = this.columns.length || 4;
        const widths = [70, 45, 85, 55, 65, 40];
        const bar = width => {
            const span = document.createElement('span');
            span.className = 'tableviewer-skeleton';
            span.style.width = `${width}%`;
            return span;
        };
        const head = this.tableEl.createTHead().insertRow();
        for (let c = 0; c < columns; c++) {
            const th = document.createElement('th');
            th.append(bar(40 + (c * 17) % 40));
            head.append(th);
        }
        const body = this.tableEl.createTBody();
        const addRow = r => {
            const tr = body.insertRow();
            for (let c = 0; c < columns; c++) tr.insertCell().append(bar(widths[(r + c) % widths.length]));
            return tr;
        };

        // Fill the visible area: measure one row, then add as many as fit.
        // Never more than a page holds, so the ghost matches what's coming.
        const rowHeight = addRow(0).offsetHeight;
        const space = this.scrollEl.clientHeight - this.tableEl.tHead.offsetHeight;
        const fits = rowHeight > 0 && space > 0 ? Math.floor(space / rowHeight) : 8;
        for (let r = 1; r < Math.max(1, Math.min(this.limit, fits)); r++) addRow(r);

        // Measured before the stylesheet applied? Redraw once it has - also
        // when the skeleton stays up behind the login form after a 401.
        if (!_tvStylesLoaded) {
            _ensureTableViewerStyles().then(() => {
                if (!this._hasRendered && !this.scrollEl.hidden) this._renderSkeleton();
            });
        }
    }

    /** Render a static, unpaginated array of rows directly (no server round-trip). */
    setData(rows) {
        this.rows = Array.isArray(rows) ? rows : [];
        this.columns = this.filterColumns || (this.rows.length ? Object.keys(this.rows[0]).filter(k => k !== '__meta') : []);
        this.columnsMeta = {};
        this.total = this.rows.length;
        this.totalPages = 1;
        this.canEdit = false;
        this.canDelete = false;
        this.errorEl.hidden = true;
        this.scrollEl.hidden = false;
        this._render();
        return this;
    }

    _render() {
        this._hasRendered = true;
        this._renderFilters();
        this._renderTable();
        if (this.paginationEl) this._renderPagination();
    }

    // --- filters ------------------------------------------------------------

    _renderFilters() {
        if (!this.filterBarEl) return;
        if (this._filtersBuilt) {
            this.filters.forEach(f => {
                const input = this._filterInputs[f.key];
                if (input && document.activeElement !== input) input.value = f.value ?? '';
            });
            return;
        }
        this._filtersBuilt = true;
        this._filterInputs = {};
        this.filterBarEl.replaceChildren();

        this.filters.forEach(f => {
            const wrap = document.createElement('label');
            wrap.className = 'tableviewer-filter';
            const caption = document.createElement('span');
            caption.className = 'tableviewer-filter-label';
            caption.textContent = f.label;
            const row = document.createElement('span');
            row.className = 'tableviewer-filter-row';

            let input;
            if (f.kind === 'date') {
                input = document.createElement('input');
                input.type = 'date';
                input.value = f.value || '';
                input.addEventListener('change', () => this._setFilter(f.key, input.value));
                if (f.arrows) {
                    row.append(this._arrowButton('←', 'Previous day', () => this._shiftDay(f.key, input, -1)));
                    row.append(input);
                    row.append(this._arrowButton('→', 'Next day', () => this._shiftDay(f.key, input, 1)));
                } else {
                    row.append(input);
                }
            } else {
                input = document.createElement('select');
                const all = document.createElement('option');
                all.value = '';
                all.textContent = f.allLabel || 'All';
                input.append(all);
                (f.options || []).forEach(o => {
                    const opt = document.createElement('option');
                    opt.value = o.value;
                    opt.textContent = o.label;
                    input.append(opt);
                });
                input.value = f.value ?? '';
                input.addEventListener('change', () => this._setFilter(f.key, input.value));
                row.append(input);
            }
            input.classList.add('tableviewer-filter-input');
            this._filterInputs[f.key] = input;
            wrap.append(caption, row);
            this.filterBarEl.append(wrap);
        });
    }

    _arrowButton(text, label, onClick) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'tableviewer-page-btn';
        btn.textContent = text;
        btn.setAttribute('aria-label', label);
        btn.addEventListener('click', onClick);
        return btn;
    }

    _shiftDay(key, input, delta) {
        const day = input.value ? new Date(`${input.value}T00:00:00`) : new Date();
        day.setDate(day.getDate() + delta);
        input.value = `${day.getFullYear()}-${_tvPad(day.getMonth() + 1)}-${_tvPad(day.getDate())}`;
        this._setFilter(key, input.value);
    }

    _setFilter(key, value) {
        this.filterValues = this.filterValues || {};
        this.filterValues[key] = value;
        this.page = 1;
        this.load();
    }

    // --- table --------------------------------------------------------------

    _cellText(row, key) {
        const meta = this.columnsMeta[key] || {};
        const labels = (row.__meta && row.__meta.labels) || {};
        if (key in labels) return labels[key] === null || labels[key] === undefined ? null : String(labels[key]);
        return _tvDisplay(row[key], meta.kind);
    }

    _fillCell(cell, row, key) {
        const text = this._cellText(row, key);
        if (text === null) {
            cell.textContent = '–';
            cell.classList.add('tableviewer-null');
        } else {
            cell.textContent = text;
            cell.classList.remove('tableviewer-null');
        }
        // One-word values (dates, CPR, numbers) would otherwise break at "-".
        cell.classList.toggle('tableviewer-nowrap', text === null || !/\s/.test(text));
    }

    _renderTable() {
        this.tableEl.innerHTML = '';

        const headRow = this.tableEl.createTHead().insertRow();
        this.columns.forEach(name => {
            const th = document.createElement('th');
            th.textContent = name;
            const sortable = (this.columnsMeta[name] || {}).sortable !== false;
            if (this._paginated && sortable) {
                th.classList.add('tableviewer-sortable');
                if (this.sort === name) {
                    th.classList.add(this.sortDir === 'desc' ? 'tableviewer-sort-desc' : 'tableviewer-sort-asc');
                }
                th.addEventListener('click', () => {
                    if (this.sort === name) this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
                    else { this.sort = name; this.sortDir = 'asc'; }
                    this.page = 1;
                    this.load();
                });
            }
            headRow.appendChild(th);
        });
        // No Actions column at all for viewers who can't edit or delete - a disabled
        // button there would just be dead weight for them, not a real affordance.
        const hasActions = this.canEdit || this.canDelete;
        if (hasActions) {
            const actionsHead = document.createElement('th');
            actionsHead.className = 'tableviewer-actions-col';
            actionsHead.textContent = 'Actions';
            headRow.appendChild(actionsHead);
        }

        const body = this.tableEl.createTBody();
        if (!this.rows.length) {
            const td = body.insertRow().insertCell();
            td.colSpan = this.columns.length + (hasActions ? 1 : 0);
            td.className = 'tableviewer-empty';
            td.textContent = 'No rows found.';
            return;
        }

        this.rows.forEach(row => {
            const tr = body.insertRow();
            this.columns.forEach(name => {
                const cell = tr.insertCell();
                cell.dataset.column = name;
                this._fillCell(cell, row, name);
            });

            if (hasActions) {
                const actionCell = tr.insertCell();
                actionCell.className = 'tableviewer-actions-col';
                if (this.canEdit) {
                    const editBtn = document.createElement('button');
                    editBtn.type = 'button';
                    editBtn.className = 'tableviewer-edit-btn';
                    editBtn.textContent = 'Edit';
                    editBtn.addEventListener('click', () => this._beginRowEdit(tr, row));
                    actionCell.appendChild(editBtn);
                }
                if (this.canDelete) {
                    const deleteBtn = document.createElement('button');
                    deleteBtn.type = 'button';
                    deleteBtn.className = 'tableviewer-edit-btn tableviewer-delete-btn';
                    deleteBtn.title = 'Delete';
                    deleteBtn.setAttribute('aria-label', 'Delete row');
                    deleteBtn.innerHTML = _TV_TRASH_ICON;
                    deleteBtn.addEventListener('click', () => this._deleteRow(row));
                    actionCell.appendChild(deleteBtn);
                }
            }
        });

        // Columns where every value fits on one line (CPR, dates, amounts)
        // shrink to their content; columns of wrapping text take the rest.
        Array.from(headRow.cells).forEach((th, i) => {
            if (i >= this.columns.length) return;
            const tight = Array.from(body.rows).every(r => r.cells[i].classList.contains('tableviewer-nowrap'));
            th.classList.toggle('tableviewer-tight', tight);
        });
    }

    // --- editing ------------------------------------------------------------

    /** Swap one row into edit mode: editable cells become fields matching their type. */
    _beginRowEdit(tr, row) {
        const cells = Array.from(tr.cells);
        const editors = {};
        const save = () => this._saveRowEdit(row, editors, saveBtn, cancelBtn);
        tr.classList.add('tableviewer-editing');

        this.columns.forEach((key, i) => {
            const meta = this.columnsMeta[key] || {};
            if (!meta.editable) return;
            const editor = this._editor(meta, key, row);
            cells[i].textContent = '';
            cells[i].classList.remove('tableviewer-null');
            cells[i].appendChild(editor.el);
            editors[key] = editor;
        });

        tr.addEventListener('keydown', e => {
            if (e.defaultPrevented || e.target.tagName === 'BUTTON') return;
            if (e.key === 'Enter') { e.preventDefault(); save(); }
            if (e.key === 'Escape') { e.preventDefault(); this._renderTable(); }
        });

        const actionCell = cells[cells.length - 1];
        actionCell.innerHTML = '';
        const saveBtn = document.createElement('button');
        saveBtn.type = 'button';
        saveBtn.className = 'tableviewer-edit-btn tableviewer-save-btn';
        saveBtn.textContent = 'Save';
        saveBtn.addEventListener('click', save);
        const cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'tableviewer-edit-btn tableviewer-cancel-btn';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.addEventListener('click', () => this._renderTable());
        actionCell.append(saveBtn, cancelBtn);

        const first = Object.values(editors)[0];
        if (first) first.focus();
    }

    /** One editing field. Returns {el, get(), changed(), focus()}. */
    _editor(meta, key, row) {
        const value = row[key];
        const lookup = meta.lookup;

        if (lookup && lookup.mode !== 'select') {
            const labels = (row.__meta && row.__meta.labels) || {};
            return this._combobox(meta, key, value, labels[key]);
        }

        if (lookup) {
            const select = document.createElement('select');
            select.className = 'tableviewer-edit-input';
            const none = document.createElement('option');
            none.value = '';
            none.textContent = '–';
            select.append(none);
            (lookup.options || []).forEach(o => {
                const opt = document.createElement('option');
                opt.value = o.value;
                opt.textContent = o.label;
                select.append(opt);
            });
            const original = value === null || value === undefined ? '' : String(value);
            select.value = original;
            return {
                el: select,
                get: () => (select.value === '' ? null : select.value),
                changed: () => select.value !== original,
                focus: () => select.focus(),
            };
        }

        if (meta.kind === 'bool') {
            const box = document.createElement('input');
            box.type = 'checkbox';
            box.className = 'tableviewer-edit-check';
            const original = value === true || value === 1 || value === '1';
            box.checked = original;
            return { el: box, get: () => box.checked, changed: () => box.checked !== original, focus: () => box.focus() };
        }

        const input = document.createElement('input');
        input.className = 'tableviewer-edit-input';
        input.type = { date: 'date', time: 'time', datetime: 'datetime-local', number: 'number' }[meta.kind] || 'text';
        if (meta.kind === 'number') input.step = 'any';
        // The calendar icon is hidden to keep the row narrow (TableViewer.css),
        // so clicking the field opens the calendar instead.
        if (meta.kind === 'date') {
            input.addEventListener('click', () => { try { input.showPicker(); } catch (e) { /* unsupported */ } });
        }
        const original = _tvInputValue(value, meta.kind);
        input.value = original;
        return {
            el: input,
            // Untouched fields aren't sent at all, so saving never rounds away
            // precision (seconds, 7-digit fractions) the picker can't show.
            get: () => (meta.kind === 'text' ? input.value : (input.value === '' ? null : input.value)),
            changed: () => input.value !== original,
            focus: () => input.focus(),
        };
    }

    /** Searchable field for bigger lookups: shows names, saves the id. */
    _combobox(meta, key, value, label) {
        const wrap = document.createElement('div');
        wrap.className = 'tableviewer-combo';
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'tableviewer-edit-input';
        input.placeholder = 'Search…';
        input.autocomplete = 'off';
        input.value = label ?? '';
        const list = document.createElement('div');
        list.className = 'tableviewer-combo-list';
        list.hidden = true;
        wrap.append(input, list);

        const original = value === null || value === undefined ? null : String(value);
        let selected = original;
        let selectedLabel = label ?? '';
        let shown = [];
        let timer = null;
        let requestId = 0;

        const close = () => { list.hidden = true; };
        const pick = option => {
            selected = String(option.value);
            selectedLabel = option.label;
            input.value = option.label;
            close();
        };
        const show = (options, totalText) => {
            shown = options.slice(0, 8);
            list.replaceChildren();
            shown.forEach(o => {
                const item = document.createElement('div');
                item.className = 'tableviewer-combo-item';
                if (String(o.value) === selected) item.classList.add('tableviewer-combo-current');
                item.textContent = o.label;
                item.addEventListener('mousedown', e => { e.preventDefault(); pick(o); });
                list.append(item);
            });
            const info = document.createElement('div');
            info.className = 'tableviewer-combo-info';
            info.textContent = totalText;
            list.append(info);
            list.hidden = false;
        };
        const search = query => {
            if (meta.lookup.mode === 'local') {
                const matches = (meta.lookup.options || []).filter(o => _tvWordMatch(o.label, query));
                show(matches, matches.length ? `Showing ${Math.min(8, matches.length)} of ${matches.length} matches` : 'No matches');
                return;
            }
            const id = ++requestId;
            clearTimeout(timer);
            timer = setTimeout(async () => {
                try {
                    const params = new URLSearchParams({ column: key, search: query });
                    const res = await fetch(`${this.url.split('?')[0].replace(/\/$/, '')}/options?${params}`);
                    const data = await res.json();
                    if (id !== requestId) return;
                    const options = data.options || [];
                    show(options, options.length ? 'Type more to narrow it down' : 'No matches');
                } catch (err) {
                    if (id === requestId) show([], 'Could not load options');
                }
            }, 200);
        };

        input.addEventListener('focus', () => { input.select(); search(''); });
        input.addEventListener('input', () => search(input.value));
        input.addEventListener('blur', () => {
            close();
            if (input.value.trim() !== '') input.value = selectedLabel;
        });
        input.addEventListener('keydown', e => {
            if (list.hidden) return;
            if (e.key === 'Enter' && shown.length) { e.preventDefault(); pick(shown[0]); }
            if (e.key === 'Escape') { e.preventDefault(); close(); }
        });

        return {
            el: wrap,
            get: () => (input.value.trim() === '' ? null : selected),
            changed: () => (input.value.trim() === '' ? null : selected) !== original,
            focus: () => input.focus(),
        };
    }

    async _saveRowEdit(row, editors, saveBtn, cancelBtn) {
        const values = {};
        Object.entries(editors).forEach(([key, editor]) => {
            if (editor.changed()) values[key] = editor.get();
        });
        if (!Object.keys(values).length) { this._renderTable(); return; }

        saveBtn.disabled = true;
        cancelBtn.disabled = true;
        const keys = (row.__meta && row.__meta.keys) || { base: Object.fromEntries(this.primaryKey.map(k => [k, row[k]])) };

        try {
            const res = await fetch(this.url.split('?')[0], {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ keys, pk: keys.base, values, filters: this.filterValues || {} }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

            this.errorEl.hidden = true;
            await this.load(); // refresh this page from the server
        } catch (err) {
            this.errorEl.textContent = `Could not save: ${err.message}`;
            this.errorEl.hidden = false;
            this._renderTable(); // revert this row back to display mode
        }
    }

    /** Ask for a reason (hjDialog, js/Dialog.js), then delete the row on the server. */
    async _deleteRow(row) {
        const keys = (row.__meta && row.__meta.keys) || { base: Object.fromEntries(this.primaryKey.map(k => [k, row[k]])) };
        const summary = this.columns.slice(0, 2).map(c => this._cellText(row, c)).filter(Boolean).join(' · ');
        const reason = await hjDialog.open({
            type: 'textarea',
            title: 'Delete row',
            message: `${summary ? `"${summary}"` : 'This row'} will be deleted permanently.`,
            label: 'Reason',
            placeholder: 'Why is this row being deleted?',
            maxLength: 500,
            confirmText: 'Delete',
            danger: true,
            onConfirm: async text => {
                const res = await fetch(`${this.url.split('?')[0].replace(/\/$/, '')}/delete`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ keys, reason: text }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
            },
        });
        if (reason === null) return;   // cancelled
        this.errorEl.hidden = true;
        await this.load();
    }

    _renderPagination() {
        this.paginationEl.innerHTML = '';

        const info = document.createElement('span');
        info.className = 'tableviewer-page-info';
        info.textContent = this.total
            ? `Page ${this.page} of ${this.totalPages} (${this.total} rows)`
            : 'No rows';

        const prev = document.createElement('button');
        prev.type = 'button';
        prev.className = 'tableviewer-page-btn';
        prev.textContent = 'Prev';
        prev.disabled = this.page <= 1;
        prev.addEventListener('click', () => { this.page -= 1; this.load(); });

        const next = document.createElement('button');
        next.type = 'button';
        next.className = 'tableviewer-page-btn';
        next.textContent = 'Next';
        next.disabled = this.page >= this.totalPages;
        next.addEventListener('click', () => { this.page += 1; this.load(); });

        this.paginationEl.append(prev, info, next);
    }
}

// Declarative mounting: <div data-tableviewer="/api/worktime"></div> needs no
// JS from the consumer at all.
//   data-tableviewer-columns="A,B"  - restrict which columns are shown
//   data-tableviewer-limit="40"     - rows per page (still capped server-side)
function _tableviewerInit(root = document) {
    root.querySelectorAll('[data-tableviewer]').forEach(el => {
        if (el.dataset.tableviewerReady) return;
        el.dataset.tableviewerReady = 'true';
        new TableViewer(el).load();
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => _tableviewerInit());
} else {
    _tableviewerInit();
}
