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

test("API console clears and disables stale ID/month validation after route changes", async () => {
  const elements = new Map();
  const inputs = [];
  const forms = [];
  const getElement = (id) => {
    if (!elements.has(id)) elements.set(id, new Element("div"));
    return elements.get(id);
  };
  const requests = [];
  const context = {
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
      return { status: 200, text: async () => "[]" };
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
