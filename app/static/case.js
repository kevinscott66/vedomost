"use strict";
(() => {
  const refresh = () => {
    document.title = window.i18n.t("casePageTitle");
    const formatter = new Intl.NumberFormat(window.i18n.locale);
    for (const element of document.querySelectorAll("[data-case-amount]")) {
      element.textContent = formatter.format(Number(element.dataset.caseAmount));
    }
    const video = document.getElementById("case-video");
    for (const track of video.textTracks) {
      track.mode = track.language === window.i18n.language ? "showing" : "disabled";
    }
  };
  window.addEventListener("languagechange", refresh);
  document.getElementById("case-video").addEventListener("loadedmetadata", refresh);
  refresh();
})();
