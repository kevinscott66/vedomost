const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
function harness() {
  const elements = new Map(), listeners = {}, calls = [];
  const node = (tag, text, cls) => ({tag, text, cls, children: [], append(...items) { this.children.push(...items); }, replaceChildren(...items) { this.children = items; }});
  const $ = id => { if (!elements.has(id)) elements.set(id, node("div")); return elements.get(id); };
  let language = "en";
  const context = { $, node, button: (text, onclick) => ({text, onclick}), empty: text => ({text}), t: key => `${language}:${key}`, paymentNumber: (amount, currency) => `${amount} ${currency}`, Intl, Date,
    request: path => new Promise((resolve, reject) => calls.push({path, resolve, reject})),
    window: {i18n: {locale: "en", formatMonth: value => value}, addEventListener: (name, fn) => {listeners[name] = fn;}},
  };
  vm.runInNewContext(fs.readFileSync("app/static/activity.js", "utf8"), context);
  return { $, calls, journal: context.window.activityJournal, language(value) { language = value; listeners.languagechange(); } };
}
const entry = (id, action = "payment.add") => ({ id, action, created_at: "2026-10-29T12:00:00Z", student_name: `Student ${id}`, detail: action.startsWith("payment.") ? {payment: {id, amount:"10.00", currency:"USD", base_amount:"120000.00", date:"2026-10-29", ...(action === "payment.void" ? {void_reason:"Duplicate"} : {})}} : {after: {name:"Alice", phone:"000", group:"A2", monthly_fee:"100000", start_month:"2026-10"}} });
test("activity pagination retains order and uses the latest cursor", async () => {
  const h = harness();
  const first = h.journal.load();
  assert.equal(h.$("activity-refresh").disabled, true);
  h.calls[0].resolve({items:[entry(3), entry(2)], next_before:2}); await first;
  const next = h.$("activity-more").onclick();
  assert.equal(h.calls[1].path, "/activity?before=2");
  h.calls[1].resolve({items:[entry(1)], next_before:null}); await next;
  assert.equal(h.$("activity-list").children.length, 3);
  assert.deepEqual(h.$("activity-list").children.map(item => item.children[1].text), ["Student 3", "Student 2", "Student 1"]);
  assert.equal(h.$("activity-more").hidden, true);
  assert.equal(h.$("activity-refresh").disabled, false);
});
test("superseded activity responses cannot replace a newer refresh", async () => {
  const h = harness(), old = h.journal.load(), latest = h.journal.load();
  h.calls[1].resolve({items:[entry(2)], next_before:null}); await latest;
  h.calls[0].resolve({items:[entry(1)], next_before:1}); await old;
  assert.equal(h.$("activity-list").children[0].children[1].text, "Student 2");
  assert.equal(h.$("activity-more").hidden, true);
});
test("failed activity load unlocks controls and retry recovers", async () => {
  const h = harness(), initial = h.journal.load();
  h.calls[0].reject(new Error("Offline")); await initial;
  assert.equal(h.$("activity-refresh").disabled, false);
  const retry = h.$("activity-list").children.at(-1).onclick();
  h.calls[1].resolve({items:[entry(1)], next_before:null}); await retry;
  assert.equal(h.$("activity-list").children.length, 1);
  assert.equal(h.$("activity-list").children[0].children[1].text, "Student 1");
});
test("all activity actions relocalize without losing payment snapshots", async () => {
  const h = harness(), loading = h.journal.load();
  h.calls[0].resolve({items:["student.add", "student.update", "student.delete", "payment.add", "payment.void"].map((action,i) => entry(i+1,action)), next_before:null}); await loading;
  for (const lang of ["ru", "uz", "en"]) {
    h.language(lang);
    const rows = h.$("activity-list").children;
    assert.equal(rows.length, 5);
    assert.ok(rows.every(row => row.children[0].children[0].text.startsWith(lang + ":event")));
    assert.ok(rows[3].children.some(child => child.text?.includes("10.00 USD")));
    assert.ok(rows[4].children.some(child => child.text === "Duplicate"));
  }
});
