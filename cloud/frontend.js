"use strict";
(() => {
  const base = "/demos/vedomost";
  const nativeFetch = window.fetch.bind(window);
  const sessionUrl = `${base}/session`;

  async function startSession() {
    const locks = window.navigator?.locks;
    const controller = new AbortController();
    let timer;
    const deadline = new Promise((_, reject) => {
      timer = setTimeout(() => {
        controller.abort();
        reject(new Error("Demo session startup timed out."));
      }, 15000);
    });
    const request = async () => {
      const response = await Promise.race([nativeFetch(sessionUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // Without cross-tab locking, only renew an existing cookie; never race to create one.
          ...(!locks?.request ? { "X-Demo-Require-Session": "1" } : {}),
        },
        body: "{}",
        credentials: "same-origin",
        signal: controller.signal,
      }), deadline]);
      if (!response.ok) {
        const error = new Error("The demo session could not be started.");
        error.unsupportedBrowser = response.status === 409;
        throw error;
      }
      return await Promise.race([response.json(), deadline]);
    };
    try {
      // Bound both the wait for another tab and the fetch/body inside the lock.
      return await Promise.race([
        locks?.request
          ? locks.request("vedomost-session-bootstrap", { signal: controller.signal }, request)
          : request(),
        deadline,
      ]);
    } finally { clearTimeout(timer); }
  }

  // Share each in-flight session request; clear failures so a later app retry can try again.
  let sessionReady = null;
  function ensureSession() {
    if (!sessionReady) {
      let tracked;
      tracked = Promise.resolve()
        .then(startSession)
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
      /^\/(?:students(?:\/[^/]+(?:\/(?:payments|statement))?)?|payments(?:\/[0-9]+\/void)?|activity|debtors|exchange-rates)$/.test(url.pathname) &&
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
      if (error.unsupportedBrowser) {
        target.textContent = window.i18n?.language === "uz"
          ? "Demoni boshlash uchun brauzeringizni yangilang."
          : window.i18n?.language === "en"
            ? "Update your browser to start the demo."
            : "Обновите браузер, чтобы начать работу с демо.";
        return;
      }
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
