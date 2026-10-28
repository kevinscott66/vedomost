const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

// A deliberately small DOM: application handlers/renderers are real; transport
// remains deferred so each test can control the order of user actions/responses.
class Element {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.listeners = new Map();
    this.dataset = {};
    this.attributes = {};
    this.value = "";
    this.className = "";
    this.disabled = false;
    this.hidden = false;
    this.open = false;
    this.validationMessage = "";
    this.classList = {
      toggle: (name, force) => {
        const classes = new Set(this.className.split(/\s+/).filter(Boolean));
        const add = force === undefined ? !classes.has(name) : force;
        if (add) classes.add(name);
        else classes.delete(name);
        this.className = [...classes].join(" ");
      },
      contains: (name) => this.className.split(/\s+/).includes(name),
    };
  }
  set value(value) {
    this._value = String(value);
  }
  get value() {
    return this._value || "";
  }
  set textContent(value) {
    this._text = String(value);
    this.children = [];
  }
  get textContent() {
    return (
      (this._text || "") + this.children.map((c) => c.textContent).join("")
    );
  }
  append(...children) {
    this.children.push(...children);
  }
  replaceChildren(...children) {
    this._text = "";
    this.children = children;
    if (this.tagName === "SELECT") this.value = children[0]?.value || "";
  }
  addEventListener(name, handler) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(handler);
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
  setCustomValidity(message) {
    this.validationMessage = message;
  }
  querySelectorAll(selector) {
    const matches = (element) =>
      selector.split(",").some((part) => {
        const name = part.trim();
        return name.startsWith(".")
          ? element.classList.contains(name.slice(1))
          : element.tagName.toLowerCase() === name;
      });
    return this.children.flatMap((child) => [
      ...(matches(child) ? [child] : []),
      ...child.querySelectorAll(selector),
    ]);
  }
  showModal() {
    this.open = true;
  }
  close() {
    this.open = false;
  }
  reset() {
    for (const input of this.querySelectorAll("input, select"))
      input.value = "";
    // Native reset() does not clear a customError.
  }
  focus() {}
  scrollIntoView() {}
  async fire(name, { evenIfDisabled = false } = {}) {
    if (this.disabled && !evenIfDisabled) return;
    const event = { currentTarget: this, target: this, preventDefault() {} };
    const handlers = [this["on" + name], ...(this.listeners.get(name) || [])];
    return Promise.all(
      handlers.filter(Boolean).map((handler) => handler(event)),
    );
  }
}

const tick = () => new Promise((resolve) => setImmediate(resolve));
const people = [
  {
    id: 1,
    name: "Alpha",
    phone: "123",
    group: "A",
    monthly_fee: "100.00",
    start_month: "2026-01",
  },
  {
    id: 2,
    name: "Beta",
    phone: "456",
    group: "B",
    monthly_fee: "200.00",
    start_month: "2026-01",
  },
];
function report(month, name = "Alpha") {
  const student = people.find((person) => person.name === name);
  return {
    month,
    total_debt: student.monthly_fee,
    debtors: [{ ...student, paid: "0.00", debt: student.monthly_fee }],
  };
}
async function runtime() {
  const ids = new Map();
  const element = (id) => {
    if (!ids.has(id)) ids.set(id, new Element());
    return ids.get(id);
  };
  const html = fs.readFileSync("app/static/index.html", "utf8");
  for (const match of html.matchAll(/<([a-z]+)\b[^>]*\bid="([^"]+)"/g))
    ids.set(match[2], new Element(match[1]));
  for (const [form, controls] of [
    ["payment-form", ["pay-student", "pay-amount", "pay-date", "save-payment"]],
    [
      "student-form",
      [
        "student-id",
        "student-name",
        "student-phone",
        "student-group",
        "student-fee",
        "student-start",
        "save-student",
      ],
    ],
  ])
    element(form).append(...controls.map(element));
  element("students-view").hidden = true;
  const events = new Element();
  const requests = [];
  const context = {
    Intl,
    Date,
    Event,
    crypto: { randomUUID: () => "test-key-" + requests.length },
    Option: function (text, value) {
      const option = new Element("option");
      option.textContent = text;
      option.value = String(value);
      return option;
    },
    document: {
      getElementById: element,
      createElement: (tag) => new Element(tag),
      createTextNode: (text) => {
        const node = new Element();
        node.textContent = text;
        return node;
      },
      querySelector: () => element("main"),
      querySelectorAll: (selector) =>
        [...ids.values()].flatMap((node) => node.querySelectorAll(selector)),
    },
    fetch: (path, options) =>
      new Promise((resolve, reject) =>
        requests.push({ path, options, resolve, reject }),
      ),
    window: {
      i18n: {
        locale: "en-US",
        t: (key, values) => key + (values ? JSON.stringify(values) : ""),
        keyFor: () => null,
        formatMonth: (value) => value,
      },
      currency: { convert: Number, unit: "UZS", code: "UZS" },
      addEventListener: (...args) => events.addEventListener(...args),
    },
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync("app/static/calendar.js", "utf8"), context);
  vm.runInContext(fs.readFileSync("app/static/app.js", "utf8"), context);
  const respond = async (request, body, status = 200) => {
    request.resolve({ ok: status < 400, status, json: async () => body });
    await tick();
  };
  await respond(requests[0], people);
  await respond(requests[1], report(element("month").value));
  return {
    element,
    context,
    requests,
    respond,
    display: (name) => events.fire(name),
    payButtons: () => element("debt-list").querySelectorAll("button"),
    studentButtons: () => element("students-list").querySelectorAll("button"),
  };
}

test("Pay and student editor clear custom validation after programmatic population", async () => {
  const app = await runtime();
  for (const id of ["pay-student", "pay-amount", "pay-date"])
    app.element(id).setCustomValidity("invalidField");
  await app.payButtons()[0].fire("click");
  for (const id of ["pay-student", "pay-amount", "pay-date"])
    assert.equal(app.element(id).validationMessage, "", id);
  for (const id of [
    "student-name",
    "student-phone",
    "student-group",
    "student-fee",
    "student-start",
  ])
    app.element(id).setCustomValidity("invalidField");
  app.element("pay-date").setCustomValidity("invalidField");
  app.element("pay-student").value = "2";
  await app.element("pay-student").fire("change");
  assert.equal(app.element("pay-date").validationMessage, "");
  await app.studentButtons()[1].fire("click");
  for (const id of [
    "student-name",
    "student-phone",
    "student-group",
    "student-fee",
    "student-start",
  ])
    assert.equal(app.element(id).validationMessage, "", id);
});

test("pending payment protects its draft and row actions through display rerenders", async () => {
  const app = await runtime();
  await app.payButtons()[0].fire("click");
  const original = ["pay-student", "pay-amount", "pay-date"].map(
    (id) => app.element(id).value,
  );
  const submission = app.element("payment-form").fire("submit");
  const payment = app.requests.at(-1);
  assert.equal(payment.path, "/payments");
  for (const event of ["languagechange", "currencychange"]) {
    await app.display(event);
    assert.equal(app.payButtons()[0].disabled, true, event);
    // Also exercise the action guard, independently of native disabled clicks.
    app.element("pay-amount").value = "77.00";
    await app.payButtons()[0].fire("click", { evenIfDisabled: true });
    assert.equal(app.element("pay-amount").value, "77.00");
  }
  assert.equal(app.element("pay-student").value, original[0]);
  await app.respond(payment, { detail: "retry" }, 503);
  await submission;
  assert.equal(app.payButtons()[0].disabled, false);
});

for (const outcome of ["success", "error"]) {
  test(`old student ${outcome} cannot close or annotate a reopened editor`, async () => {
    const app = await runtime();
    await app.studentButtons()[1].fire("click");
    const submission = app.element("student-form").fire("submit");
    const mutation = app.requests.at(-1);
    assert.equal(mutation.options.method, "PUT");
    await app.element("close-student").fire("click");
    await app.element("new-student").fire("click");
    app.element("student-name").value = "New draft";
    const before = app.requests.length;
    await app.element("student-form").fire("submit", { evenIfDisabled: true });
    assert.equal(
      app.requests.length,
      before,
      "global pending guard blocks resubmission",
    );
    await app.respond(
      mutation,
      outcome === "success" ? people[0] : { detail: "failure" },
      outcome === "success" ? 200 : 500,
    );
    assert.equal(app.element("student-dialog").open, true);
    assert.equal(app.element("student-name").value, "New draft");
    assert.equal(app.element("student-message").textContent, "");
    // A successful mutation may refresh behind the newer modal.
    for (const request of app.requests.slice(before))
      await app.respond(
        request,
        request.path === "/students"
          ? people
          : report(app.element("month").value),
      );
    await submission;
    assert.equal(app.element("save-student").disabled, false);
  });
}

for (const outcome of ["success", "error"]) {
  test(`old delete ${outcome} cannot close or annotate a newer confirmation`, async () => {
    const app = await runtime();
    await app.studentButtons()[2].fire("click");
    const submission = app.element("confirm-delete").fire("click");
    const mutation = app.requests.at(-1);
    assert.equal(mutation.path, "/students/1");
    await app.element("cancel-delete").fire("click");
    await app.studentButtons()[5].fire("click");
    assert.equal(app.element("delete-description").textContent, "Beta");
    const before = app.requests.length;
    await app.element("confirm-delete").fire("click", { evenIfDisabled: true });
    assert.equal(
      app.requests.length,
      before,
      "global pending guard blocks a second deletion",
    );
    await app.respond(
      mutation,
      { detail: "failure" },
      outcome === "success" ? 204 : 500,
    );
    assert.equal(app.element("delete-dialog").open, true);
    assert.equal(app.element("delete-description").textContent, "Beta");
    assert.equal(app.element("delete-message").textContent, "");
    for (const request of app.requests.slice(before))
      await app.respond(
        request,
        request.path === "/students"
          ? people
          : report(app.element("month").value),
      );
    await submission;
    assert.equal(app.element("confirm-delete").disabled, false);
  });
}

test("month refresh removes old reports immediately, including display changes and failure", async () => {
  const app = await runtime();
  assert.match(app.element("debt-list").textContent, /Alpha/);
  app.element("month").value = "2027-02";
  const refresh = app.element("month").fire("change");
  const pending = app.requests.slice(-2);
  assert.doesNotMatch(app.element("debt-list").textContent, /Alpha/);
  assert.equal(app.payButtons().length, 0);
  assert.equal(app.element("total").textContent, "—");
  for (const event of ["languagechange", "currencychange"]) {
    await app.display(event);
    assert.doesNotMatch(app.element("debt-list").textContent, /Alpha/);
    assert.equal(app.payButtons().length, 0);
  }
  await app.respond(pending[0], people);
  await app.respond(pending[1], { detail: "failed" }, 500);
  await refresh;
  for (const event of ["languagechange", "currencychange"]) {
    await app.display(event);
    assert.match(app.element("debt-list").textContent, /loadError/);
    assert.equal(app.payButtons().length, 0);
  }
  const retry = app.context.refresh();
  const next = app.requests.slice(-2);
  await app.respond(next[0], people);
  await app.respond(next[1], report("2027-02", "Beta"));
  await retry;
  assert.match(app.element("debt-list").textContent, /Beta/);
  assert.doesNotMatch(app.element("debt-list").textContent, /Alpha/);
});

test("payment period notice follows language without reviving a cleared notice", async () => {
  const app = await runtime();
  await app.payButtons()[0].fire("click");
  app.context.window.i18n.formatMonth = (value) => `translated ${value}`;
  await app.display("languagechange");
  assert.match(app.element("payment-message").textContent, /translated/);
  assert.equal(
    app.element("payment-message").classList.contains("error"),
    false,
  );
  await app.element("pay-student").fire("change");
  await app.display("languagechange");
  assert.equal(app.element("payment-message").textContent, "");
});
