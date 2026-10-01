// doit.js
// -----------------------------------------------------------------------
// Pure helpers for the "Do it" overview tiles: how far away a deadline is,
// worded for a person, from today's date. No DOM, no clock of its own (the
// caller passes `now`), so it runs under Node for tests too.
//
//   window.DoIt.relativeDue("2025-11-14", new Date())
//     -> { days: 5, text: "Due in 5 days", state: "future" }
//   window.DoIt.dueDateText("2025-11-14", "17:00", new Date())
//     -> "Fri 14 Nov, 5 pm"       (", 2025" added when it is not this year)
//
// Dates are calendar days in the reader's own timezone; a due time only
// changes the wording of the date, never the day count.
// -----------------------------------------------------------------------
(function () {
  "use strict";

  const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const DAY_MS = 86400000;

  // "YYYY-MM-DD" -> {y, m, d} or null (rejects impossible dates such as 2025-02-30).
  function parseIso(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ""));
    if (!m) return null;
    const y = +m[1], mo = +m[2], d = +m[3];
    const t = new Date(Date.UTC(y, mo - 1, d));
    if (t.getUTCFullYear() !== y || t.getUTCMonth() !== mo - 1 || t.getUTCDate() !== d) return null;
    return { y, m: mo, d, utcDay: Math.round(t.getTime() / DAY_MS), weekday: t.getUTCDay() };
  }

  // Whole calendar days from today to the date (negative once it has passed).
  function daysUntil(iso, now) {
    const p = parseIso(iso);
    if (!p) return null;
    const n = now || new Date();
    const today = Math.round(Date.UTC(n.getFullYear(), n.getMonth(), n.getDate()) / DAY_MS);
    return p.utcDay - today;
  }

  function relativeDue(iso, now) {
    const days = daysUntil(iso, now);
    if (days == null) return null;
    if (days === 0) return { days, text: "Due today", state: "today" };
    if (days === 1) return { days, text: "Due tomorrow", state: "future" };
    if (days > 1) return { days, text: `Due in ${days} days`, state: "future" };
    const late = -days;
    return { days, text: `Overdue by ${late} day${late === 1 ? "" : "s"}`, state: "overdue" };
  }

  // "17:00" -> "5 pm", "09:30" -> "9:30 am", "00:00" -> "12 am". null if not HH:MM.
  function clockText(time) {
    const m = /^([01]?\d|2[0-3]):([0-5]\d)$/.exec(String(time || ""));
    if (!m) return null;
    const h = +m[1];
    const mins = m[2];
    const h12 = h % 12 === 0 ? 12 : h % 12;
    return `${h12}${mins === "00" ? "" : ":" + mins} ${h < 12 ? "am" : "pm"}`;
  }

  function dueDateText(iso, time, now) {
    const p = parseIso(iso);
    if (!p) return "";
    const n = now || new Date();
    let s = `${DAYS[p.weekday]} ${p.d} ${MONTHS[p.m - 1]}`;
    if (p.y !== n.getFullYear()) s += ` ${p.y}`;
    const c = clockText(time);
    return c ? `${s}, ${c}` : s;
  }

  window.DoIt = { parseIso, daysUntil, relativeDue, clockText, dueDateText };
})();
