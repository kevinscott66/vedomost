const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
function runtime(saved = "UZS") {
  const storage = new Map([["vedomost-currency", saved]]);
  const context = {
    Intl,
    Event,
    window: {
      i18n: {
        locale: "en-US",
        t: (key) => (key === "currencyUnit" ? "UZS" : "Indicative conversion"),
      },
      addEventListener() {},
      dispatchEvent() {},
    },
    document: {
      getElementById() {
        return null;
      },
    },
    localStorage: {
      getItem: (k) => storage.get(k),
      setItem: (k, v) => storage.set(k, v),
    },
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync("app/static/currency.js", "utf8"), context);
  return { currency: context.window.currency, storage };
}
test("display conversion uses a single UZS base without changing stored amounts", () => {
  const { currency, storage } = runtime();
  const amount = "11918.98";
  assert.equal(currency.convert(amount), 11918.98);
  currency.set("USD");
  assert.equal(currency.convert(amount), 1);
  assert.equal(currency.unit, "$");
  currency.set("RUB");
  assert.equal(currency.convert("148.04"), 1);
  assert.equal(currency.unit, "₽");
  assert.equal(storage.get("vedomost-currency"), "RUB");
  currency.set("EUR");
  assert.equal(currency.code, "RUB");
  currency.set("UZS");
  assert.equal(currency.convert(amount), 11918.98);
  assert.equal(amount, "11918.98");
});
test("saved currency is allowlisted; unsupported saved values fall back to UZS", () => {
  assert.equal(runtime("USD").currency.code, "USD");
  assert.equal(runtime("__proto__").currency.code, "UZS");
});
