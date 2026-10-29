"use strict";
(() => {
  const base = "/demos/vedomost";
  const nativeFetch = window.fetch.bind(window);
  const sessionUrl = `${base}/session`;

  // Share each in-flight session request; clear failures so a later app retry can try again.
  let sessionReady = null;
  function ensureSession() {
    if (!sessionReady) {
      let tracked;
      tracked = Promise.resolve()
        .then(() =>
          nativeFetch(sessionUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: "{}",
            credentials: "same-origin",
          }),
        )
        .then((response) => {
          if (!response.ok)
            throw new Error("The demo session could not be started.");
          return response.json();
        })
        .catch((error) => {
          if (sessionReady === tracked) sessionReady = null;
          throw error;
        });
      sessionReady = tracked;
      tracked.catch(() => {});
    }
    return sessionReady;
  }

  function isAppRequest(input) {
    const raw = typeof input === "string" ? input : input?.url;
    if (typeof raw !== "string") return false;
    const url = new URL(raw, window.location.href);
    return (
      url.origin === window.location.origin &&
      /^\/(?:students(?:\/[^/]+(?:\/(?:payments|statement))?)?|payments|debtors|exchange-rates)$/.test(url.pathname) &&
      !url.pathname.startsWith(`${base}/`) &&
      !url.pathname.startsWith("/static/")
    );
  }

  window.fetch = async (input, init) => {
    if (!isAppRequest(input)) return nativeFetch(input, init);
    await ensureSession();
    const raw = typeof input === "string" ? input : input.url;
    const url = new URL(raw, window.location.href);
    const prefixed = `${base}${url.pathname}${url.search}${url.hash}`;
    if (typeof input === "string") return nativeFetch(prefixed, init);
    return nativeFetch(new Request(prefixed, input), init);
  };

  const labels = {
    ru: "Демо · вымышленные данные.",
    uz: "Demo · xayoliy ma’lumotlar.",
    en: "Demo · fictional data.",
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

  ensureSession().catch((error) => {
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
