const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const c = { window: {} };
vm.createContext(c);
vm.runInContext(fs.readFileSync("app/static/calendar.js", "utf8"), c);
test("calendar boundaries preserve early years, leap rules and final month", () => {
  for (const [month, last] of [
    ["0001-02", "28"],
    ["0099-02", "28"],
    ["1900-02", "28"],
    ["2000-02", "29"],
    ["2024-02", "29"],
    ["2026-09", "30"],
    ["9999-12", "31"],
  ]) {
    assert.equal(c.window.ledgerCalendar.bounds(month).min, month + "-01");
    assert.equal(c.window.ledgerCalendar.bounds(month).max, month + "-" + last);
  }
  for (const invalid of ["0000-01", "2026-13", "2026-1", "10000-01"])
    assert.throws(() => c.window.ledgerCalendar.bounds(invalid));
});
