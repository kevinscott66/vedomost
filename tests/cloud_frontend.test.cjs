"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(
  path.join(__dirname, "../cloud/frontend.js"),
  "utf8",
);

function response(ok = true) {
  return { ok, json: async () => ({}) };
}

function setup(nativeFetch, navigator = { locks: { request: (_name, _options, callback) => callback() } }, timers = { setTimeout, clearTimeout }) {
  const listeners = {};
  const main = { prepend: () => {} };
  const document = {
    readyState: "complete",
    querySelector: (selector) => (selector === "main" ? main : null),
    getElementById: () => null,
    addEventListener: () => {},
    createElement: () => ({ setAttribute: () => {}, textContent: "" }),
  };
  const window = {
    location: { href: "https://demo.example/demos/vedomost/", origin: "https://demo.example" },
    fetch: nativeFetch,
    navigator,
    addEventListener: (event, callback) => {
      listeners[event] = callback;
    },
  };
  vm.runInNewContext(source, {
    window,
    AbortController,
    setTimeout: timers.setTimeout,
    clearTimeout: timers.clearTimeout,
    document,
    URL,
    Promise,
    console: { error: () => {} },
  });
  return window;
}

test("cloud session bootstrap retries after failure and shares concurrent retries", async () => {
  const calls = [];
  let releaseRetry;
  let sessionAttempts = 0;
  const window = setup((input, init) => {
    calls.push({ input, init });
    if (input === "/demos/vedomost/session") {
      sessionAttempts += 1;
      if (sessionAttempts === 1) return Promise.reject(new Error("offline"));
      return new Promise((resolve) => {
        releaseRetry = () => resolve(response());
      });
    }
    return Promise.resolve(response());
  });

  await assert.rejects(window.fetch("/students"), /offline/);
  assert.equal(sessionAttempts, 1);

  const first = window.fetch("/students");
  const second = window.fetch("/debtors?month=2026-10");
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(sessionAttempts, 2, "concurrent calls share one retry");
  releaseRetry();
  await Promise.all([first, second]);

  assert.deepEqual(
    calls.filter(({ input }) => typeof input === "string").map(({ input }) => input),
    [
      "/demos/vedomost/session",
      "/demos/vedomost/session",
      "/demos/vedomost/students",
      "/demos/vedomost/debtors?month=2026-10",
    ],
  );
});

test("cloud fetch leaves external and static requests untouched", async () => {
  const calls = [];
  const window = setup((input, init) => {
    calls.push({ input, init });
    return Promise.resolve(response());
  });
  const externalInit = { method: "GET" };
  const staticInit = { method: "GET" };

  await window.fetch("https://cdn.example/library.js", externalInit);
  await window.fetch("/static/style.css", staticInit);

  assert.deepEqual(calls.filter(({ input }) => input !== "/demos/vedomost/session"), [
    { input: "https://cdn.example/library.js", init: externalInit },
    { input: "/static/style.css", init: staticInit },
  ]);
});


test("cloud statement requests retain their month and use the demo session path", async () => {
  const calls = [];
  const window = setup((input) => {
    calls.push(input);
    return Promise.resolve(response());
  });
  await window.fetch("/students/3/statement?month=2026-10");
  assert.deepEqual(calls, [
    "/demos/vedomost/session",
    "/demos/vedomost/students/3/statement?month=2026-10",
  ]);
});


test("first bootstrap in two tabs is serialized until cookie installation", async () => {
  let tail = Promise.resolve();
  const navigator = { locks: { request: (_name, _options, callback) => {
    const current = tail.then(callback);
    tail = current.catch(() => {});
    return current;
  } } };
  let cookie = null;
  let creations = 0;
  let release;
  const seen = [];
  const fetch = async (url) => {
    if (url.endsWith("/session")) {
      if (!cookie) {
        creations++;
        await new Promise(resolve => { release = resolve; });
        cookie = "shared-session";
      }
    } else seen.push(cookie);
    return response();
  };
  const a = setup(fetch, navigator);
  const b = setup(fetch, navigator);
  const requests = [a.fetch("/students"), b.fetch("/students")];
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(creations, 1);
  release();
  await Promise.all(requests);
  assert.equal(creations, 1);
  assert.deepEqual(seen, ["shared-session", "shared-session"]);
});

test("without Web Locks bootstrap requires an existing session", async () => {
  let headers;
  const window = setup(async (url, init) => {
    if (url.endsWith("/session")) headers = init.headers;
    return response();
  }, {});
  await window.fetch("/students");
  assert.equal(headers["X-Demo-Require-Session"], "1");
});

test("activity and cancellation stay within the visitor's demo session", async () => {
  const calls = [];
  const window = setup((input) => { calls.push(input); return Promise.resolve(response()); });
  await window.fetch("/activity?before=51");
  await window.fetch("/payments/3/void", {method: "POST", body: JSON.stringify({reason: "Wrong currency"})});
  assert.deepEqual(calls, ["/demos/vedomost/session", "/demos/vedomost/activity?before=51", "/demos/vedomost/payments/3/void"]);
});

for (const stalled of ["fetch", "body", "lock"]) {
  test(`session startup deadline recovers from a stalled ${stalled} and shares retries`, async () => {
    const pendingTimers = new Set();
    const timers = {
      setTimeout: callback => { pendingTimers.add(callback); return callback; },
      clearTimeout: callback => pendingTimers.delete(callback),
    };
    const calls = [];
    let attempts = 0, lockAttempts = 0, oldSignal;
    const navigator = { locks: { request: (_name, {signal}, callback) => {
      lockAttempts++;
      if (stalled === "lock" && lockAttempts === 1) {
        oldSignal = signal;
        return new Promise((_, reject) => signal.addEventListener("abort", () => reject(new Error("aborted lock"))));
      }
      return callback();
    } } };
    const window = setup((url, init) => {
      calls.push(url);
      if (url.endsWith("/session")) {
        attempts++;
        if (attempts === 1 && stalled !== "lock") {
          oldSignal = init.signal;
          if (stalled === "fetch") return new Promise(() => {});
          return Promise.resolve({ok: true, json: () => new Promise(() => {})});
        }
      }
      return Promise.resolve(response());
    }, navigator, timers);
    const first = window.fetch("/students");
    // Attach rejection before advancing the deadline.
    const failure = assert.rejects(first, /timed out|aborted lock/);
    await new Promise(resolve => setImmediate(resolve));
    for (const expire of [...pendingTimers]) expire();
    await failure;
    assert.equal(oldSignal.aborted, true);
    await Promise.all([window.fetch("/students"), window.fetch("/activity")]);
    assert.equal(lockAttempts, 2);
    assert.equal(attempts, stalled === "lock" ? 1 : 2);
    assert.equal(pendingTimers.size, 0);
    assert.deepEqual(calls.slice(-2), ["/demos/vedomost/students", "/demos/vedomost/activity"]);
  });
}
