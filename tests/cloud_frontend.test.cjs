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

function setup(nativeFetch) {
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
    addEventListener: (event, callback) => {
      listeners[event] = callback;
    },
  };
  vm.runInNewContext(source, {
    window,
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
