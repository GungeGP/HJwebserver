// Calendar - a month view that fills its container (100% width and height)
// where the user picks two dates, a start and an end, and sends them to an
// endpoint. Injected on every page; does nothing unless the page has a
// <div data-calendar="/api/..."></div>.
//
//   POST <endpoint>   {"start": "2026-11-03", "end": "2026-11-12"}
//
// Whatever the endpoint answers (JSON) comes back in the 'calendar:select'
// event, so the page can use it:
//
//   el.addEventListener('calendar:select', e => console.log(e.detail));   // {start, end, response}
//
// Styling lives in css/calender.css (overridable like every framework asset -
// see WebServer/core/assets.py).

let _calStylesReady = null;

/** Adds the stylesheet once; resolves when it has loaded (or failed). */
function _ensureCalendarStyles() {
    if (_calStylesReady) return _calStylesReady;
    let link = document.getElementById('calendar-styles');
    if (!link) {
        link = document.createElement('link');
        link.id = 'calendar-styles';
        link.rel = 'stylesheet';
        link.href = '/css/calender.css';
        document.head.appendChild(link);
    }
    _calStylesReady = new Promise(resolve => {
        if (link.sheet) { resolve(); return; }
        link.addEventListener('load', resolve);
        link.addEventListener('error', resolve);
    });
    return _calStylesReady;
}

// --- dates -------------------------------------------------------------------
// Dates are local midnight Date objects inside the calendar; the server gets
// and sends YYYY-MM-DD, the user sees DD-MM-YYYY (same as TableViewer).

const _calPad = n => String(n).padStart(2, '0');
const _calIso = d => `${d.getFullYear()}-${_calPad(d.getMonth() + 1)}-${_calPad(d.getDate())}`;
const _calDisplay = d => (d ? `${_calPad(d.getDate())}-${_calPad(d.getMonth() + 1)}-${d.getFullYear()}` : '–');
const _calToday = () => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), d.getDate()); };
const _calSameDay = (a, b) => !!a && !!b && a.getTime() === b.getTime();

class Calendar {
    /**
     * el:      the element to draw into
     * options: endpoint     URL the dates are POSTed to (default: el.dataset.calendar)
     *          confirmText  text of the send button (default 'Send')
     *          clearText    text of the clear button (default 'Clear')
     *          locale       language of month/weekday names (default: <html lang>)
     */
    constructor(el, options = {}) {
        this.el = el;
        this.endpoint = options.endpoint || el.dataset.calendar;
        this.confirmText = options.confirmText || el.dataset.calendarConfirm || 'Send';
        this.clearText = options.clearText || el.dataset.calendarClear || 'Clear';
        this.locale = options.locale || document.documentElement.lang || undefined;

        const today = _calToday();
        this.currentDate = new Date(today.getFullYear(), today.getMonth(), 1);   // month shown
        this.start = null;
        this.end = null;
        this.hover = null;   // previews the range while only the start is picked
        this.sending = false;
    }

    async init() {
        await _ensureCalendarStyles();
        this.build();
        this.render();
    }

    build() {
        this.el.classList.add('calendar-wrap');
        this.el.textContent = '';

        const header = document.createElement('div');
        header.className = 'calendar-header';

        this.prevBtn = this.button('‹', 'calendar-nav', () => this.shiftMonth(-1));
        this.prevBtn.setAttribute('aria-label', 'Previous month');
        this.nextBtn = this.button('›', 'calendar-nav', () => this.shiftMonth(1));
        this.nextBtn.setAttribute('aria-label', 'Next month');
        this.titleEl = document.createElement('h2');
        this.titleEl.className = 'calendar-title';
        const todayBtn = this.button('Today', 'calendar-btn', () => {
            const t = _calToday();
            this.currentDate = new Date(t.getFullYear(), t.getMonth(), 1);
            this.render();
        });
        header.append(this.prevBtn, this.titleEl, this.nextBtn, todayBtn);

        // Monday first. 2024-01-01 was a Monday, so its week gives the names.
        const weekdays = document.createElement('div');
        weekdays.className = 'calendar-weekdays';
        const fmt = new Intl.DateTimeFormat(this.locale, { weekday: 'short' });
        for (let i = 0; i < 7; i++) {
            const w = document.createElement('div');
            w.className = 'calendar-weekday';
            w.textContent = fmt.format(new Date(2024, 0, 1 + i));
            weekdays.appendChild(w);
        }

        this.gridEl = document.createElement('div');
        this.gridEl.className = 'calendar-grid';
        this.gridEl.addEventListener('mouseleave', () => {
            if (this.hover) { this.hover = null; this.paint(); }
        });

        const footer = document.createElement('div');
        footer.className = 'calendar-footer';
        this.summaryEl = document.createElement('div');
        this.summaryEl.className = 'calendar-summary';
        this.clearBtn = this.button(this.clearText, 'calendar-btn', () => {
            this.start = this.end = this.hover = null;
            this.paint();
        });
        this.confirmBtn = this.button(this.confirmText, 'calendar-btn calendar-confirm', () => this.send());
        footer.append(this.summaryEl, this.clearBtn, this.confirmBtn);

        this.el.append(header, weekdays, this.gridEl, footer);
    }

    button(text, className, onClick) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = className;
        b.textContent = text;
        b.addEventListener('click', onClick);
        return b;
    }

    shiftMonth(delta) {
        this.currentDate = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth() + delta, 1);
        this.render();
    }

    /** Rebuilds the 6x7 day grid for the month shown. */
    render() {
        const year = this.currentDate.getFullYear();
        const month = this.currentDate.getMonth();
        const title = new Intl.DateTimeFormat(this.locale, { month: 'long', year: 'numeric' }).format(this.currentDate);
        this.titleEl.textContent = title.charAt(0).toUpperCase() + title.slice(1);

        const offset = (new Date(year, month, 1).getDay() + 6) % 7;   // Monday = 0
        const today = _calToday();
        this.gridEl.textContent = '';
        this.days = [];
        for (let i = 0; i < 42; i++) {
            const date = new Date(year, month, 1 - offset + i);
            const cell = document.createElement('button');
            cell.type = 'button';
            cell.className = 'calendar-day';
            if (date.getMonth() !== month) cell.classList.add('calendar-outside');
            if (_calSameDay(date, today)) cell.classList.add('calendar-today');
            cell.textContent = date.getDate();
            cell.setAttribute('aria-label', _calDisplay(date));
            cell.addEventListener('click', () => this.pick(date));
            cell.addEventListener('mouseenter', () => {
                if (this.start && !this.end) { this.hover = date; this.paint(); }
            });
            this.gridEl.appendChild(cell);
            this.days.push({ date, cell });
        }
        this.paint();
    }

    /** First click picks the start, second the end; a third starts over. */
    pick(date) {
        if (!this.start || this.end) {
            this.start = date;
            this.end = null;
        } else if (date < this.start) {
            this.end = this.start;
            this.start = date;
        } else {
            this.end = date;
        }
        this.hover = null;
        this.paint();
    }

    /** Marks the selection on the existing cells and updates the footer. */
    paint() {
        const other = this.end || this.hover;
        let lo = this.start, hi = other;
        if (lo && hi && hi < lo) [lo, hi] = [hi, lo];

        for (const { date, cell } of this.days) {
            const isStart = _calSameDay(date, lo);
            const isEnd = _calSameDay(date, hi || lo);
            cell.classList.toggle('calendar-start', isStart);
            cell.classList.toggle('calendar-end', isEnd);
            cell.classList.toggle('calendar-in-range', !!(lo && hi && date > lo && date < hi));
            cell.classList.toggle('calendar-preview', !this.end && !!hi);
            cell.setAttribute('aria-pressed', String(isStart || isEnd));
        }

        if (this.start && this.end) {
            const days = Math.round((this.end - this.start) / 86400000) + 1;
            this.summaryEl.textContent = `${_calDisplay(this.start)}  →  ${_calDisplay(this.end)}  (${days} ${days === 1 ? 'day' : 'days'})`;
        } else if (this.start) {
            this.summaryEl.textContent = `${_calDisplay(this.start)}  →  pick the end date`;
        } else {
            this.summaryEl.textContent = 'Pick a start date';
        }
        this.clearBtn.disabled = !this.start || this.sending;
        this.confirmBtn.disabled = !(this.start && this.end) || this.sending || !this.endpoint;
    }

    /** POSTs {start, end} to the endpoint and fires 'calendar:select' with the answer. */
    async send() {
        if (!this.start || !this.end || this.sending) return;
        const start = _calIso(this.start);
        const end = _calIso(this.end);
        this.sending = true;
        this.paint();
        try {
            const res = await fetch(this.endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ start, end }),
            });
            const response = await res.json().catch(() => null);
            if (!res.ok) {
                Notify((response && response.error) || `Could not send the dates (${res.status})`, 'error');
                return;
            }
            this.el.dispatchEvent(new CustomEvent('calendar:select', { bubbles: true, detail: { start, end, response } }));
        } catch (err) {
            Notify('Could not reach the server', 'error');
        } finally {
            this.sending = false;
            this.paint();
        }
    }
}

// Declarative mounting: <div data-calendar="/api/cal"></div> needs no JS from
// the consumer at all.
//   data-calendar-confirm="Send"  - text of the send button
//   data-calendar-clear="Clear"   - text of the clear button
function _calendarInit(root = document) {
    root.querySelectorAll('[data-calendar]').forEach(el => {
        if (el.dataset.calendarReady) return;
        el.dataset.calendarReady = 'true';
        el.calendar = new Calendar(el);
        el.calendar.init();
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => _calendarInit());
} else {
    _calendarInit();
}
