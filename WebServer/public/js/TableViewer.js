// Styling lives in css/TableViewer.css (served/overridable the same way as
// this file - see WebServer/__init__.py's serve_table_viewer_css).
function _ensureTableViewerStyles() {
    if (document.getElementById('tableviewer-styles')) return;
    const link = document.createElement('link');
    link.id = 'tableviewer-styles';
    link.rel = 'stylesheet';
    link.href = '/css/TableViewer.css';
    document.head.appendChild(link);
}

class TableViewer {
    /**
     * @param {HTMLElement} container
     * @param {object} [options]
     * @param {string} [options.url] - server endpoint returning
     *   {rows, columns, page, limit, total, totalPages, sort, sortDir}.
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
        this.total = 0;
        this.totalPages = 1;
        this.primaryKey = [];
        this._searchTimer = null;
        this._paginated = Boolean(this.url);

        _ensureTableViewerStyles();
        this._buildShell();
    }

    _buildShell() {
        this.container.classList.add('tableviewer-wrap');
        this.container.innerHTML = '';

        if (this._paginated) {
            const toolbar = document.createElement('div');
            toolbar.className = 'tableviewer-toolbar';
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
            toolbar.appendChild(search);
            this.container.appendChild(toolbar);
        }

        this.errorEl = document.createElement('div');
        this.errorEl.className = 'tableviewer-error';
        this.errorEl.hidden = true;
        this.container.appendChild(this.errorEl);

        const scroll = document.createElement('div');
        scroll.className = 'tableviewer-scroll';
        this.tableEl = document.createElement('table');
        this.tableEl.className = 'tableviewer';
        scroll.appendChild(this.tableEl);
        this.scrollEl = scroll;
        this.container.appendChild(scroll);

        if (this._paginated) {
            this.paginationEl = document.createElement('div');
            this.paginationEl.className = 'tableviewer-pagination';
            this.container.appendChild(this.paginationEl);
        }
    }

    /** Fetch the current page/search/sort from the server (only when constructed with a url). */
    async load() {
        if (!this.url) return this;

        const params = new URLSearchParams({ page: this.page, limit: this.limit });
        if (this.search) params.set('search', this.search);
        if (this.sort) { params.set('sort', this.sort); params.set('dir', this.sortDir); }
        const separator = this.url.includes('?') ? '&' : '?';

        try {
            const res = await fetch(`${this.url}${separator}${params}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            this.rows = data.rows || [];
            this.columns = this.filterColumns || data.columns || (this.rows.length ? Object.keys(this.rows[0]) : []);
            this.total = data.total ?? this.rows.length;
            this.totalPages = data.totalPages ?? 1;
            this.page = data.page ?? this.page;
            this.primaryKey = data.primaryKey || [];

            this.errorEl.hidden = true;
            this.scrollEl.hidden = false;
            this._render();
        } catch (err) {
            this.errorEl.textContent = `Failed to load table: ${err.message}`;
            this.errorEl.hidden = false;
            this.scrollEl.hidden = true;
            if (this.paginationEl) this.paginationEl.replaceChildren();
        }
        return this;
    }

    /** Render a static, unpaginated array of rows directly (no server round-trip). */
    setData(rows) {
        this.rows = Array.isArray(rows) ? rows : [];
        this.columns = this.filterColumns || (this.rows.length ? Object.keys(this.rows[0]) : []);
        this.total = this.rows.length;
        this.totalPages = 1;
        this.errorEl.hidden = true;
        this.scrollEl.hidden = false;
        this._render();
        return this;
    }

    _render() {
        this._renderTable();
        if (this.paginationEl) this._renderPagination();
    }

    _renderTable() {
        this.tableEl.innerHTML = '';

        const headRow = this.tableEl.createTHead().insertRow();
        this.columns.forEach(name => {
            const th = document.createElement('th');
            th.textContent = name;
            if (this._paginated) {
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
        const actionsHead = document.createElement('th');
        actionsHead.className = 'tableviewer-actions-col';
        actionsHead.textContent = 'Actions';
        headRow.appendChild(actionsHead);

        const body = this.tableEl.createTBody();
        if (!this.rows.length) {
            const td = body.insertRow().insertCell();
            td.colSpan = this.columns.length + 1;
            td.className = 'tableviewer-empty';
            td.textContent = 'No rows found.';
            return;
        }

        const canEdit = this._paginated && this.primaryKey.length > 0;

        this.rows.forEach(row => {
            const tr = body.insertRow();
            this.columns.forEach(name => {
                const value = row[name];
                const cell = tr.insertCell();
                cell.textContent = value === null || value === undefined ? '' : String(value);
                cell.dataset.column = name;
            });

            const actionCell = tr.insertCell();
            actionCell.className = 'tableviewer-actions-col';
            const editBtn = document.createElement('button');
            editBtn.type = 'button';
            editBtn.className = 'tableviewer-edit-btn';
            editBtn.textContent = 'Edit';
            editBtn.disabled = !canEdit;
            if (!canEdit && this._paginated) {
                editBtn.title = "This table has no primary key, so rows can't be edited safely.";
            }
            if (canEdit) {
                editBtn.addEventListener('click', () => this._beginRowEdit(tr, row));
            }
            actionCell.appendChild(editBtn);
        });
    }

    /** Swap one row into edit mode: text cells become inputs, Edit becomes Save/Cancel. */
    _beginRowEdit(tr, row) {
        const cells = Array.from(tr.cells);
        const inputs = {};

        this.columns.forEach((name, i) => {
            if (this.primaryKey.includes(name)) return; // the key itself isn't editable
            const cell = cells[i];
            const value = row[name];
            cell.textContent = '';
            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'tableviewer-edit-input';
            input.value = value === null || value === undefined ? '' : String(value);
            input.addEventListener('keydown', e => {
                if (e.key === 'Enter') { e.preventDefault(); save(); }
                if (e.key === 'Escape') { e.preventDefault(); this._renderTable(); }
            });
            cell.appendChild(input);
            inputs[name] = input;
        });

        const actionCell = cells[cells.length - 1];
        actionCell.innerHTML = '';
        const saveBtn = document.createElement('button');
        saveBtn.type = 'button';
        saveBtn.className = 'tableviewer-edit-btn tableviewer-save-btn';
        saveBtn.textContent = 'Save';
        const cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'tableviewer-edit-btn tableviewer-cancel-btn';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.addEventListener('click', () => this._renderTable());

        const save = () => this._saveRowEdit(row, inputs, saveBtn, cancelBtn);
        saveBtn.addEventListener('click', save);

        actionCell.append(saveBtn, cancelBtn);
        Object.values(inputs)[0]?.focus();
    }

    async _saveRowEdit(row, inputs, saveBtn, cancelBtn) {
        saveBtn.disabled = true;
        cancelBtn.disabled = true;

        const pk = {};
        this.primaryKey.forEach(name => { pk[name] = row[name]; });
        const values = {};
        Object.entries(inputs).forEach(([name, input]) => { values[name] = input.value; });

        try {
            const res = await fetch(this.url, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pk, values }),
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
