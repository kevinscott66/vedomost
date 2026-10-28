"use strict";
(() => {
  const page = document.body.dataset.document;
  const t = (key) => window.i18n.t(key);
  function el(tag, text, cls) {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  }
  function link(text, href) {
    const a = el("a", text);
    a.href = href;
    return a;
  }
  const lawLinks = {
    ru: [["152-ФЗ", "https://mintrud.gov.ru/docs/laws/130"]],
    uz: [["O‘RQ-547", "https://www.lex.uz/uz/docs/-4396419"]],
    en: [
      ["GDPR", "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng"],
      ["CCPA / CPRA", "https://oag.ca.gov/privacy/ccpa"],
    ],
  };
  function apiConsole(root) {
    const section = el("section", undefined, "api-console");
    section.append(el("h2", t("tryApi")));
    const form = el("form"),
      endpoint = el("select"),
      id = el("input"),
      month = el("input"),
      body = el("textarea"),
      output = el("pre", t("response")),
      submit = el("button", t("execute"), "primary");
    const now = new Date();
    const localDay = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    const routes = [
      "GET /students",
      "POST /students",
      "GET /students/{id}",
      "PUT /students/{id}",
      "DELETE /students/{id}",
      "POST /payments",
      "GET /students/{id}/payments",
      "GET /debtors",
    ];
    routes.forEach((route) => endpoint.append(new Option(route, route)));
    id.type = "number";
    id.min = "1";
    id.step = "1";
    id.value = "1";
    month.type = "month";
    month.value = localDay.slice(0, 7);
    body.rows = 7;
    body.spellcheck = false;
    submit.type = "submit";
    output.setAttribute("aria-live", "polite");
    function field(text, control) {
      const label = el("label", text);
      label.append(control);
      form.append(label);
      return label;
    }
    field(t("endpoint"), endpoint);
    const idField = field(t("studentId"), id),
      monthField = field(t("month"), month),
      bodyField = field(t("requestBody"), body);
    const note = el("p", t("apiWriteNote"), "small");
    form.append(note, submit);
    section.append(form, output);
    root.append(section);
    function configure() {
      const [method, path] = endpoint.value.split(" ");
      idField.hidden = !path.includes("{id}");
      monthField.hidden = path !== "/debtors";
      bodyField.hidden = !["POST", "PUT"].includes(method);
      id.required = !idField.hidden;
      month.required = !monthField.hidden;
      body.value = JSON.stringify(
        path === "/payments"
          ? {
              student_id: 1,
              amount: "200000.00",
              date: localDay,
            }
          : {
              name: "Demo student",
              phone: "+7 000 000-00-00",
              group: "A2",
              monthly_fee: "800000.00",
            },
        null,
        2,
      );
    }
    endpoint.addEventListener("change", configure);
    configure();
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const [method, template] = endpoint.value.split(" ");
      if (
        !idField.hidden &&
        (!Number.isSafeInteger(Number(id.value)) || Number(id.value) < 1)
      ) {
        output.textContent = t("invalidId");
        return;
      }
      let payload;
      if (!bodyField.hidden) {
        try {
          payload = JSON.stringify(JSON.parse(body.value));
        } catch {
          output.textContent = t("invalidJson");
          return;
        }
      }
      const path =
        template.replace("{id}", String(Number(id.value))) +
        (template === "/debtors"
          ? "?month=" + encodeURIComponent(month.value)
          : "");
      submit.disabled = true;
      document.getElementById("language").disabled = true;
      output.textContent = t("loading");
      try {
        const result = await fetch(path, {
          method,
          headers: { "Content-Type": "application/json" },
          body: payload,
        });
        const text = await result.text();
        let formatted = text;
        try {
          formatted = JSON.stringify(JSON.parse(text), null, 2);
        } catch {}
        output.textContent = "HTTP " + result.status + "\n" + formatted;
      } catch {
        output.textContent = t("requestError");
      } finally {
        submit.disabled = false;
        document.getElementById("language").disabled = false;
      }
    });
  }
  function render() {
    const key = page === "docs" ? "apiDocs" : page;
    document.getElementById("document-title").textContent = t(key);
    document.title = t(key) + " — " + t("brand");
    document.getElementById("document-region").textContent =
      page === "docs" ? t("context") : t("region");
    document.getElementById("document-updated").textContent =
      page === "docs"
        ? t("technicalNote")
        : t("updated") + " · " + t("legalScope");
    const root = document.getElementById("document-content");
    root.replaceChildren();
    if (page === "docs") {
      root.append(el("p", t("apiIntro"), "document-lead"));
      for (const [title, body] of [
        ["apiStudents", "apiStudentsText"],
        ["apiPayments", "apiPaymentsText"],
        ["apiDebtors", "apiDebtorsText"],
        ["apiErrors", "apiErrorsText"],
        ["apiRules", "apiRuleText"],
      ]) {
        const section = el("section");
        section.append(el("h2", t(title)), el("p", t(body)));
        root.append(section);
      }
      const samples = [
        {
          name: "Demo student",
          phone: "+7 000 000-00-00",
          group: "A2",
          monthly_fee: "800000.00",
        },
        { student_id: 1, amount: "200000.00", date: "2026-10-28" },
      ];
      root.append(el("h2", t("example")));
      for (const sample of samples)
        root.append(el("pre", JSON.stringify(sample, null, 2)));
      root.append(link(t("openapi"), "/openapi.json"));
      apiConsole(root);
    } else {
      for (const [title, text] of window.VEDOMOST_LEGAL[window.i18n.language][
        page
      ]) {
        const section = el("section");
        section.append(el("h2", title), el("p", text));
        root.append(section);
      }
      const resources = el("div", undefined, "document-resources");
      if (page === "rights") {
        resources.append(
          link(t("licenseFile"), "/license.txt"),
          link(t("thirdParty"), "/third-party-notices.txt"),
          link(t("sourceCode"), "https://github.com/kevinscott66/vedomost"),
        );
      } else {
        for (const [label, url] of lawLinks[window.i18n.language])
          resources.append(link(label, url));
      }
      resources.append(
        link("hello@dobropalm.tech", "mailto:hello@dobropalm.tech"),
      );
      root.append(resources);
    }
    document.querySelectorAll(".document-nav a").forEach((a) => {
      if (a.getAttribute("href") === "/" + page)
        a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
  }
  window.addEventListener("languagechange", render);
  render();
})();
