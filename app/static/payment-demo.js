"use strict";
// Frontend placeholders only: no provider SDK, network request, credential fields or ledger writes.
(() => {
  const dialog = document.getElementById("gateway-dialog");
  const title = document.getElementById("gateway-dialog-title");
  const description = document.getElementById("gateway-description");
  const status = document.getElementById("gateway-status");
  const methods = Object.freeze({
    RUB: "gatewayRub",
    USD: "gatewayUsd",
    UZS: "gatewayUzs",
  });
  let selected = "UZS";
  let tested = false;
  function render() {
    title.textContent = window.i18n.t("gatewayTitle", { code: selected });
    description.textContent = window.i18n.t(methods[selected]);
    status.textContent = tested ? window.i18n.t("gatewayResult") : "";
  }
  document.querySelectorAll("[data-gateway]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!Object.hasOwn(methods, button.dataset.gateway)) return;
      selected = button.dataset.gateway;
      tested = false;
      render();
      dialog.showModal();
    });
  });
  document
    .getElementById("close-gateway")
    .addEventListener("click", () => dialog.close());
  document.getElementById("gateway-test").addEventListener("click", () => {
    tested = true;
    render();
  });
  window.addEventListener("languagechange", render);
})();
