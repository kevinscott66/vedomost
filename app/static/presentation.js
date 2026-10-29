"use strict";
(() => {
  // Decorative motion is deliberately independent of forms, money and storage.
  const elements = [...document.querySelectorAll("[data-parallax]")];
  if (!elements.length) return;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const fine = window.matchMedia("(hover: hover) and (pointer: fine)");
  const reset = () => elements.forEach(el => {
    el.style.removeProperty("--tilt-x");
    el.style.removeProperty("--tilt-y");
  });
  document.addEventListener("pointermove", event => {
    if (reduced.matches || !fine.matches || document.hidden) return;
    const x = Math.max(-1, Math.min(1, event.clientX / window.innerWidth * 2 - 1));
    const y = Math.max(-1, Math.min(1, event.clientY / window.innerHeight * 2 - 1));
    for (const el of elements) {
      el.style.setProperty("--tilt-x", `${-y * 2}deg`);
      el.style.setProperty("--tilt-y", `${x * 3}deg`);
    }
  }, { passive: true });
  document.documentElement.addEventListener("pointerleave", reset);
  document.addEventListener("visibilitychange", reset);
  reduced.addEventListener("change", reset);
  fine.addEventListener("change", reset);
})();
