"use strict";
(() => {
  const base = "/demos/vedomost";
  const nativeFetch = window.fetch.bind(window);
  const sessionUrl = `${base}/session`;

  // Start the visitor session before the application can issue any API request.
  const sessionReady = nativeFetch(sessionUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
    credentials: "same-origin",
  }).then((response) => {
    if (!response.ok) throw new Error("The demo session could not be started.");
    return response.json();
  });

  sessionReady.catch(() => {});

  function isAppRequest(input) {
    const raw = typeof input === "string" ? input : input?.url;
    if (typeof raw !== "string") return false;
    const url = new URL(raw, window.location.href);
    return (
      url.origin === window.location.origin &&
      /^\/(?:students(?:\/[^/]+(?:\/payments)?)?|payments|debtors|exchange-rates)$/.test(url.pathname) &&
      !url.pathname.startsWith(`${base}/`) &&
      !url.pathname.startsWith("/static/")
    );
  }

  window.fetch = async (input, init) => {
    if (!isAppRequest(input)) return nativeFetch(input, init);
    await sessionReady;
    const raw = typeof input === "string" ? input : input.url;
    const url = new URL(raw, window.location.href);
    const prefixed = `${base}${url.pathname}${url.search}${url.hash}`;
    if (typeof input === "string") return nativeFetch(prefixed, init);
    return nativeFetch(new Request(prefixed, input), init);
  };

  const labels = {
    ru: "Демо · вымышленные данные · сеанс на 24 часа.",
    uz: "Demo · xayoliy ma’lumotlar · seans 24 soat.",
    en: "Demo · fictional data · 24-hour session.",
  };
  function addNotice() {
    if (document.querySelector(".demo-notice")) return;
    const notice = document.createElement("p");
    notice.className = "demo-notice";
    notice.setAttribute("role", "note");
    const update = () => {
      notice.textContent = labels[window.i18n?.language] || labels.ru;
    };
    update();
    document.querySelector("main")?.prepend(notice);
    window.addEventListener("languagechange", update);
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", addNotice, { once: true });
  else addNotice();

  sessionReady.catch((error) => {
    const showError = () => {
      const target = document.getElementById("global-error");
      if (!target) return;
      target.hidden = false;
      target.textContent =
        window.i18n?.language === "uz"
          ? "Demo seansini boshlash imkoni bo‘lmadi. Sahifani qayta yuklang."
          : window.i18n?.language === "en"
            ? "Could not start the demo session. Reload the page to try again."
            : "Не удалось начать демосеанс. Перезагрузите страницу и попробуйте снова.";
    };
    if (document.readyState === "loading")
      document.addEventListener("DOMContentLoaded", showError, { once: true });
    else showError();
    console.error(error);
  });
})();
