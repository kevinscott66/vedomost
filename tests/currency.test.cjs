const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const valid = {
  base: "UZS",
  rates: { UZS: 1, RUB: 150, USD: 12000 },
  rate_date: "2026-10-28",
  fetched_at: "2026-10-28T10:00:00Z",
  status: "fresh",
  source: "CBU",
};
function runtime(
  saved = "UZS",
  response = async () => ({ ok: true, json: async () => valid }),
) {
  const storage = new Map([["vedomost-currency", saved]]);
  const events = [];
  const listeners = {};
  const intervals = [];
  let now = 100000;
  class FakeDate extends Date {
    static now() {
      return now;
    }
  }
  const picker = { value: "", addEventListener() {} };
  const note = { textContent: "" };
  const context = {
    Intl,
    Date: FakeDate,
    Number,
    Object,
    Promise,
    AbortController,
    Event: class Event {
      constructor(type) {
        this.type = type;
      }
    },
    fetch: (...args) => response(...args),
    setTimeout: () => 1,
    clearTimeout() {},
    setInterval(fn, delay) {
      intervals.push({ fn, delay });
    },
    window: {
      i18n: {
        locale: "en-US",
        t: (key, args = {}) =>
          key === "currencyUnit"
            ? "UZS"
            : `${key}:${args.rate || ""}:${args.freshness || ""}:${args.fetchedAt || ""}`,
      },
      addEventListener(type, fn) {
        listeners[type] = fn;
      },
      dispatchEvent(event) {
        events.push(event.type);
      },
    },
    document: {
      visibilityState: "visible",
      addEventListener(type, fn) {
        listeners[`document:${type}`] = fn;
      },
      getElementById(id) {
        return id === "currency"
          ? picker
          : id === "currency-note"
            ? note
            : null;
      },
    },
    localStorage: {
      getItem: (k) => storage.get(k),
      setItem: (k, v) => storage.set(k, v),
    },
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync("app/static/currency.js", "utf8"), context);
  return {
    currency: context.window.currency,
    storage,
    events,
    note,
    picker,
    listeners,
    intervals,
    advance(ms) {
      now += ms;
    },
  };
}

test("uses dynamic UZS-base rates without changing stored amounts or currency preference", async () => {
  const { currency, storage, events } = runtime("USD");
  await new Promise((resolve) => setImmediate(resolve));
  const enteredAmount = "12000";
  assert.equal(currency.code, "USD");
  assert.equal(currency.convert(enteredAmount), 1);
  currency.set("RUB");
  assert.equal(currency.convert("150"), 1);
  assert.equal(storage.get("vedomost-currency"), "RUB");
  assert.ok(events.includes("currencychange"));
  assert.equal(enteredAmount, "12000");
});

test("coalesces overlapping refreshes and wires visible timer, online and visibility events", async () => {
  let calls = 0;
  let resolveFetch;
  const env = runtime("UZS", () => {
    calls++;
    if (calls === 1)
      return new Promise((resolve) => {
        resolveFetch = resolve;
      });
    return Promise.resolve({ ok: true, json: async () => valid });
  });
  const second = env.currency.refresh();
  assert.equal(calls, 1);
  resolveFetch({ ok: true, json: async () => valid });
  await Promise.all([second]);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(calls, 1);
  assert.equal(env.intervals[0].delay, 900000);
  env.advance(60001);
  env.listeners.online();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(calls, 2);
  env.advance(60001);
  env.listeners["document:visibilitychange"]();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(calls, 3);
  env.advance(900001);
  env.intervals[0].fn();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(calls, 4);
});

test("rejects invalid payload and keeps the prior values with an outdated notice", async () => {
  let body = valid;
  const env = runtime("UZS", async () => ({
    ok: true,
    json: async () => body,
  }));
  await new Promise((resolve) => setImmediate(resolve));
  env.currency.set("USD");
  assert.equal(env.currency.convert("12000"), 1);
  body = { ...valid, rates: { ...valid.rates, USD: Infinity } };
  await env.currency.refresh();
  assert.equal(env.currency.convert("12000"), 1);
  assert.match(env.note.textContent, /currencyStale/);
});

test("network failure retains in-memory last-good rate", async () => {
  let fail = false;
  const env = runtime("USD", async () =>
    fail
      ? Promise.reject(new Error("offline"))
      : { ok: true, json: async () => valid },
  );
  await new Promise((resolve) => setImmediate(resolve));
  fail = true;
  await env.currency.refresh();
  assert.equal(env.currency.convert("12000"), 1);
  assert.match(env.note.textContent, /currencyStale/);
});

test("initial network failure reports the seeded fallback rate", async () => {
  const env = runtime("UZS", async () => {
    throw new Error("offline");
  });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(env.currency.convert("11918.98"), 11918.98);
  assert.match(env.note.textContent, /currencyFallback/);
  assert.match(env.note.textContent, /currencyNeverFetched/);
});

test("rejects malformed dates, missing fetch timestamps and inconsistent source/status", async () => {
  for (const bad of [
    { ...valid, rate_date: "2026-02-30" },
    { ...valid, fetched_at: 42 },
    { ...valid, fetched_at: "not-a-date" },
    { ...valid, source: "reference" },
    { ...valid, status: "fallback" },
  ]) {
    const env = runtime("USD", async () => ({
      ok: true,
      json: async () => bad,
    }));
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(env.currency.convert("12000"), 12000 / 11918.98);
    assert.match(env.note.textContent, /currencyFallback/);
  }
});

test("saved currency is allowlisted", () => {
  assert.equal(runtime("__proto__").currency.code, "UZS");
  assert.equal(runtime("USD").currency.code, "USD");
});

test("refresh changes the display quote without mutating booked payment values", async () => {
  let quote = valid;
  const env = runtime("USD", async () => ({ ok: true, json: async () => quote }));
  await new Promise((resolve) => setImmediate(resolve));
  const booked = Object.freeze({ amount: "2.00", currency: "USD", base_amount: "24000.00" });
  assert.equal(env.currency.convert(booked.base_amount), 2);
  quote = { ...valid, rates: { UZS: 1, RUB: 200, USD: 16000 } };
  await env.currency.refresh();
  assert.equal(env.currency.convert(booked.base_amount), 1.5);
  assert.deepEqual(booked, { amount: "2.00", currency: "USD", base_amount: "24000.00" });
});
