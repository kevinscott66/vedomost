const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
function translationRuntime() {
  const root = { dataset: { language: "ru", theme: "dark" } };
  const context = {
    window: { dispatchEvent() {} },
    document: {
      documentElement: root,
      querySelectorAll() {
        return [];
      },
      getElementById() {
        return null;
      },
      addEventListener() {},
    },
    localStorage: { setItem() {} },
    Event,
    Intl,
  };
  vm.createContext(context);
  for (const file of ["translations.js", "i18n.js", "legal-content.js"])
    vm.runInContext(fs.readFileSync("app/static/" + file, "utf8"), context);
  return context;
}
test("API path placeholders survive localisation in every language", () => {
  const c = translationRuntime();
  for (const lang of ["ru", "uz", "en"]) {
    c.window.i18n.setLanguage(lang);
    assert.match(c.window.i18n.t("apiStudentsText"), /\/students\/\{id\}/);
    assert.match(
      c.window.i18n.t("apiPaymentsText"),
      /\/students\/\{id\}\/payments/,
    );
    assert.ok(c.window.i18n.t("payFor", { name: "Demo" }).endsWith("Demo"));
  }
});
test("Uzbek month names do not depend on browser CLDR data", () => {
  const c = translationRuntime();
  c.window.i18n.setLanguage("uz");
  assert.equal(c.window.i18n.formatMonth("2026-10"), "2026-yil oktabr");
  assert.equal(c.document.documentElement.lang, "uz-Latn");
  c.window.i18n.setLanguage("en");
  assert.equal(c.window.i18n.formatMonth("2026-12"), "December 2026");
  c.window.i18n.setLanguage("ru");
  assert.equal(c.window.i18n.formatMonth("2027-01"), "январь 2027");
});
test("all keys and regional notices exist; unsupported language is ignored", () => {
  const c = translationRuntime(),
    d = c.window.VEDOMOST_TRANSLATIONS;
  for (const lang of ["ru", "uz", "en"]) {
    assert.deepEqual(Object.keys(d[lang]).sort(), Object.keys(d.ru).sort());
    for (const page of ["privacy", "terms", "rights"])
      assert.ok(
        c.window.VEDOMOST_LEGAL[lang][page].every(
          (s) =>
            s.length === 2 && s.every((x) => typeof x === "string" && x.length),
        ),
      );
  }
  c.window.i18n.setLanguage("unknown");
  assert.equal(c.window.i18n.language, "ru");
});
