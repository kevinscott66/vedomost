// Apply the saved preference before the first paint; storage may be disabled.
try {
  const savedTheme = localStorage.getItem("vedomost-theme");
  if (savedTheme === "light" || savedTheme === "dark") {
    document.documentElement.dataset.theme = savedTheme;
  }
} catch {}
