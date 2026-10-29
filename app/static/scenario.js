"use strict";
(() => {
  const data = window.VEDOMOST_SCENARIO;
  const $ = (id) => document.getElementById(id);
  const t = (key, values) => window.i18n.t(key, values);
  let step = 0;
  const numeric = (value, decimals = 0) => new Intl.NumberFormat(window.i18n.locale, {
    minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  }).format(value);
  const uzs = (value) => numeric(value) + "\u00a0" + t("currencyUnit");
  function render(announce = false) {
    document.title = t("tourPageTitle");
    const state = data[step === 0 ? "initial" : step === 1 ? "booked" : "changed"];
    $("tour-title").textContent = t("tourTitle" + step);
    $("tour-description").textContent = t("tourText" + step);
    $("tour-rate").textContent = t("tourRate" + step, {rate: numeric(step === 2 ? data.rates.changed : data.rates.booked)});
    $("tour-charge").textContent = uzs(state.charge);
    $("tour-paid").textContent = uzs(state.paid);
    $("tour-debt").textContent = uzs(state.debt);
    $("tour-next").textContent = t("tourNext" + (step === 0 ? 0 : 1));
    $("tour-next").hidden = step === 2;
    $("tour-next").disabled = step === 2;
    $("tour-open").hidden = step !== 2;
    $("tour-payment").hidden = step === 0;
    $("tour-reference").hidden = step !== 2;
    $("tour-original").textContent = numeric(data.payment.amount) + " $";
    $("tour-equivalent").textContent = uzs(data.payment.base_amount);
    $("tour-booked-rate").textContent = t("tourBookedRate", {rate: numeric(data.payment.exchange_rate)});
    $("tour-old-display").textContent = "≈ " + numeric(data.display.booked_usd, 2) + " $";
    $("tour-new-display").textContent = "≈ " + numeric(data.display.changed_usd, 2) + " $";
    for (let i = 0; i < 3; i++) $("tour-step-" + i).setAttribute("aria-current", i === step ? "step" : "false");
    if (announce || $("tour-status").textContent) {
      $("tour-status").textContent = t("tourStatus", {step: step + 1, title: t("tourTitle" + step).replace(/\n/g, " ")});
    }
    if (announce) $("tour-title").focus();
  }
  $("tour-next").addEventListener("click", () => { if (step < 2) { step++; render(true); } });
  $("tour-reset").addEventListener("click", () => { step = 0; render(true); });
  window.addEventListener("languagechange", () => render());
  render();
})();
