"use strict";
(() => {
  const dictionaries = window.VEDOMOST_TRANSLATIONS;
  const locales = {
    ru: "ru-RU",
    uz: Intl.NumberFormat.supportedLocalesOf("uz-UZ").length
      ? "uz-UZ"
      : "ru-RU",
    en: "en-US",
  };
  let language = document.documentElement.dataset.language || "ru";
  if (!locales[language]) language = "ru";
  const t = (key, values = {}) =>
    (dictionaries[language][key] || key).replace(/\{(\w+)\}/g, (token, name) =>
      Object.hasOwn(values, name) ? String(values[name]) : token,
    );
  function apply() {
    document.documentElement.lang = language === "uz" ? "uz-Latn" : language;
    document.documentElement.dataset.language = language;
    document
      .querySelectorAll("[data-i18n]")
      .forEach((el) => (el.textContent = t(el.dataset.i18n)));
    for (const [data, attribute] of [
      ["i18nAria", "aria-label"],
      ["i18nPlaceholder", "placeholder"],
    ])
      document
        .querySelectorAll(
          `[data-${data.replace(/[A-Z]/g, (x) => "-" + x.toLowerCase())}]`,
        )
        .forEach((el) => el.setAttribute(attribute, t(el.dataset[data])));
    document
      .querySelectorAll("[data-status-key]")
      .forEach((el) => (el.textContent = t(el.dataset.statusKey)));
    const picker = document.getElementById("language");
    if (picker) picker.value = language;
    document.title = t("appTitle");
    syncTheme();
  }
  function syncTheme() {
    const light = document.documentElement.dataset.theme === "light";
    const button = document.getElementById("theme-toggle");
    if (button) {
      button.setAttribute(
        "aria-label",
        t(light ? "enableDark" : "enableLight"),
      );
      document.getElementById("theme-label").textContent = t(
        light ? "darkTheme" : "lightTheme",
      );
      document.getElementById("theme-icon").src = light
        ? "/static/icons/moon.svg"
        : "/static/icons/sun.svg";
    }
  }
  window.i18n = {
    t,
    get language() {
      return language;
    },
    get locale() {
      return locales[language];
    },
    formatMonth(value) {
      const [year, month] = value.split("-");
      const names = {
        ru: [
          "январь",
          "февраль",
          "март",
          "апрель",
          "май",
          "июнь",
          "июль",
          "август",
          "сентябрь",
          "октябрь",
          "ноябрь",
          "декабрь",
        ],
        en: [
          "January",
          "February",
          "March",
          "April",
          "May",
          "June",
          "July",
          "August",
          "September",
          "October",
          "November",
          "December",
        ],
        uz: [
          "yanvar",
          "fevral",
          "mart",
          "aprel",
          "may",
          "iyun",
          "iyul",
          "avgust",
          "sentabr",
          "oktabr",
          "noyabr",
          "dekabr",
        ],
      };
      return language === "uz"
        ? `${year}-yil ${names.uz[Number(month) - 1]}`
        : `${names[language][Number(month) - 1]} ${year}`;
    },
    apply,
    keyFor(text) {
      return Object.keys(dictionaries.ru).find((key) =>
        Object.values(dictionaries).some((dict) => dict[key] === text),
      );
    },
    setLanguage(value) {
      if (!locales[value]) return;
      language = value;
      try {
        localStorage.setItem("vedomost-language", value);
      } catch {}
      apply();
      window.dispatchEvent(new Event("languagechange"));
    },
  };
  document
    .getElementById("language")
    ?.addEventListener("change", (e) =>
      window.i18n.setLanguage(e.target.value),
    );
  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    const theme =
      document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("vedomost-theme", theme);
    } catch {}
    syncTheme();
  });
  document.addEventListener(
    "invalid",
    (e) => {
      if (e.target.setCustomValidity)
        e.target.setCustomValidity(t("invalidField"));
    },
    true,
  );
  document.addEventListener("input", (e) => {
    if (e.target.setCustomValidity) e.target.setCustomValidity("");
  });
  apply();
})();
