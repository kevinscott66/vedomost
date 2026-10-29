const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

class Element {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.listeners = {};
    this.dataset = {};
    this.value = "";
    this.validationMessage = "";
    this.disabled = false;
    this.required = false;
    this.hidden = false;
  }
  append(...children) {
    this.children.push(...children);
    if (this.tagName === "SELECT" && !this.value)
      this.value = children[0]?.value || "";
  }
  replaceChildren(...children) {
    this.children = children;
  }
  addEventListener(name, handler) {
    (this.listeners[name] ||= []).push(handler);
  }
  setAttribute() {}
  setCustomValidity(message) {
    this.validationMessage = message;
  }
  async fire(name) {
    for (const handler of this.listeners[name] || [])
      await handler({ preventDefault() {} });
  }
  async requestSubmit(controls) {
    if (
      controls.some(
        (control) =>
          !control.disabled &&
          (control.validationMessage || (control.required && !control.value)),
      )
    )
      return false;
    await this.fire("submit");
    return true;
  }
}

function runtime(fetchImpl) {
  const elements = new Map();
  const inputs = [];
  const forms = [];
  const getElement = (id) => {
    if (!elements.has(id)) elements.set(id, new Element("div"));
    return elements.get(id);
  };
  const requests = [];
  const timers = new Map();
  const context = {
    AbortController,
    setTimeout: (callback, delay) => {
      const id = Symbol();
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
    document: {
      body: { dataset: { document: "docs" } },
      getElementById: getElement,
      createElement(tag) {
        const element = new Element(tag);
        if (tag === "input") inputs.push(element);
        if (tag === "form") forms.push(element);
        return element;
      },
      querySelectorAll: () => [],
      title: "",
    },
    window: {
      i18n: { language: "en", t: (key) => key },
      VEDOMOST_LEGAL: {},
      addEventListener() {},
    },
    Option: function (text, value) {
      const option = new Element("option");
      option.textContent = text;
      option.value = value;
      return option;
    },
    fetch: async (path, options) => {
      requests.push({ path, options });
      return fetchImpl ? fetchImpl(path, options) : { status: 200, text: async () => "[]" };
    },
    Date,
    URLSearchParams,
    encodeURIComponent,
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync("app/static/document.js", "utf8"), context);

  const form = forms[0];
  const route = form.children.find((child) => child.tagName === "LABEL")
    .children[0];
  const [id, month] = inputs;
  return { form, route, id, month, requests, timers,
    language: getElement("language"),
    submit: form.children.find(child => child.tagName === "BUTTON"),
    output: getElement("document-content").children.at(-1).children.at(-1),
  };
}

test("API console clears and disables stale ID/month validation after route changes", async () => {
  const { form, route, id, month, requests } = runtime();

  route.value = "GET /students/{id}";
  await route.fire("change");
  assert.equal(id.disabled, false);
  assert.equal(id.required, true);
  id.setCustomValidity("invalidField");
  assert.equal(await form.requestSubmit([id, month]), false);
  route.value = "GET /students";
  await route.fire("change");
  assert.equal(id.disabled, true);
  assert.equal(id.validationMessage, "");
  assert.equal(await form.requestSubmit([id, month]), true);

  route.value = "GET /debtors";
  await route.fire("change");
  assert.equal(month.disabled, false);
  assert.equal(month.required, true);
  month.setCustomValidity("invalidField");
  assert.equal(await form.requestSubmit([id, month]), false);
  route.value = "GET /students";
  await route.fire("change");
  assert.equal(month.disabled, true);
  assert.equal(month.validationMessage, "");
  assert.equal(await form.requestSubmit([id, month]), true);
  assert.deepEqual(
    requests.map((request) => request.path),
    ["/students", "/students"],
  );
});

for (const stall of ["fetch", "body"]) {
  test(`API console bounds stalled ${stall}, releases controls and never retries a mutation`, async () => {
    let complete;
    const stalled = new Promise(resolve => { complete = resolve; });
    const app = runtime(() => stall === "fetch" ? stalled : { status: 200, text: () => stalled });
    app.route.value = "POST /payments";
    await app.route.fire("change");
    const submission = app.form.fire("submit");
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(app.submit.disabled, true);
    assert.equal(app.language.disabled, true);
    await app.form.fire("submit");
    assert.equal(app.requests.length, 1);
    assert.equal(app.requests[0].options.signal.aborted, false);
    const timer = [...app.timers.values()][0];
    assert.equal(timer.delay, 20000);
    timer.callback();
    await submission;
    assert.equal(app.requests[0].options.signal.aborted, true);
    assert.equal(app.submit.disabled, false);
    assert.equal(app.language.disabled, false);
    assert.equal(app.output.textContent, "requestTimeout");
    assert.equal(app.timers.size, 0);
    complete(stall === "fetch" ? { status: 200, text: async () => "late result" } : "late result");
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(app.requests.length, 1);
    assert.equal(app.output.textContent, "requestTimeout");
  });
}

test("API console clears its deadline after success or transport failure", async () => {
  for (const fail of [false, true]) {
    const app = runtime(() => fail ? Promise.reject(new Error("offline")) : { status: 201, text: async () => '{"id":1}' });
    await app.form.fire("submit");
    assert.equal(app.timers.size, 0);
    assert.equal(app.submit.disabled, false);
    assert.equal(app.language.disabled, false);
    assert.equal(app.output.textContent, fail ? "requestError" : 'HTTP 201\n{\n  "id": 1\n}');
  }
});
