"use strict";
(() => {
  // Dated reference snapshot; display only, never a payment/exchange quote.
  const rates = Object.freeze({ UZS: 1, RUB: 148.04, USD: 11918.98 });
  let selected = "UZS";
  try {
    const saved = localStorage.getItem("vedomost-currency");
    if (Object.hasOwn(rates, saved)) selected = saved;
  } catch {}
  const picker = document.getElementById("currency");
  function update() {
    if (picker) picker.value = selected;
    const note = document.getElementById("currency-note");
    if (note)
      note.textContent = window.i18n.t("currencyNote", {
        rate:
          selected === "UZS"
            ? ""
            : `1 ${selected} = ${new Intl.NumberFormat(window.i18n.locale, { maximumFractionDigits: 2 }).format(rates[selected])} UZS · 28.10.2026`,
      });
  }
  window.currency = {
    convert(value) {
      return Number(value) / rates[selected];
    },
    get unit() {
      return selected === "UZS"
        ? window.i18n.t("currencyUnit")
        : selected === "RUB"
          ? "₽"
          : "$";
    },
    get code() {
      return selected;
    },
    set(value) {
      if (!Object.hasOwn(rates, value)) return;
      selected = value;
      try {
        localStorage.setItem("vedomost-currency", value);
      } catch {}
      update();
      window.dispatchEvent(new Event("currencychange"));
    },
  };
  picker?.addEventListener("change", (e) =>
    window.currency.set(e.target.value),
  );
  window.addEventListener("languagechange", update);
  update();
})();
