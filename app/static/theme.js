// Apply the saved preference before the first paint; storage may be disabled.
try {
  const savedTheme = localStorage.getItem("vedomost-theme");
  if (savedTheme === "light" || savedTheme === "dark") {
    document.documentElement.dataset.theme = savedTheme;
  }
} catch {}
try {
  const queryLanguage = new URLSearchParams(location.search).get("lang");
  const savedLanguage = localStorage.getItem("vedomost-language");
  const language = ["ru", "uz", "en"].includes(queryLanguage)
    ? queryLanguage
    : savedLanguage;
  if (["ru", "uz", "en"].includes(language)) {
    document.documentElement.dataset.language = language;
    document.documentElement.lang = language === "uz" ? "uz-Latn" : language;
  }
} catch {}
