"use strict";
(() => {
  const rates = { UZS: 1, RUB: 148.04, USD: 11918.98 };
  let exactRates = { UZS: "1", RUB: "148.04", USD: "11918.98" };
  let selected = "UZS";
  let rateDate = "2026-10-28";
  let fetchedAt = null;
  let status = "fallback";
  let source = "reference";
  let loading = true;
  let lastStarted = 0;
  let inFlight = null;
  function decimalParts(value) {
    const match = String(value).trim().match(/^([+-]?)(\d+)(?:\.(\d*))?(?:e([+-]?\d+))?$/i);
    if (!match) throw new TypeError("Invalid decimal amount");
    const fraction = match[3] || "";
    const exponent = Number(match[4] || 0);
    let coefficient = BigInt((match[1] === "-" ? "-" : "") + match[2] + fraction);
    let scale = fraction.length - exponent;
    if (scale < 0) {
      coefficient *= 10n ** BigInt(-scale);
      scale = 0;
    }
    return { coefficient, scale };
  }
  function convertExact(value, rate) {
    const amount = decimalParts(value);
    const exchange = decimalParts(rate);
    let numerator = amount.coefficient * 10n ** BigInt(exchange.scale) * 100n;
    const denominator = exchange.coefficient * 10n ** BigInt(amount.scale);
    if (denominator <= 0n) throw new TypeError("Invalid exchange rate");
    const negative = numerator < 0n;
    if (negative) numerator = -numerator;
    const cents = (numerator + denominator / 2n) / denominator;
    const whole = cents / 100n;
    const minor = String(cents % 100n).padStart(2, "0");
    return `${negative && cents ? "-" : ""}${whole}.${minor}`;
  }
  function bookingRates(data) {
    if (data.booking_rates === undefined) return null;
    const values = data.booking_rates;
    if (
      !values ||
      Object.keys(values).sort().join(",") !== "RUB,USD,UZS" ||
      values.UZS !== "1"
    )
      return false;
    for (const code of ["RUB", "USD"]) {
      const value = values[code];
      if (
        typeof value !== "string" ||
        value.length > 128 ||
        !/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value) ||
        !Number.isFinite(Number(value)) ||
        Number(value) <= 0 ||
        Number(value) !== data.rates[code]
      )
        return false;
    }
    return { UZS: "1", RUB: values.RUB, USD: values.USD };
  }
  try {
    const saved = localStorage.getItem("vedomost-currency");
    if (Object.hasOwn(rates, saved)) selected = saved;
  } catch {}
  const picker = document.getElementById("currency");
  const fmtDate = (value) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return "";
    const [year, month, day] = value.split("-").map(Number);
    return new Intl.DateTimeFormat(window.i18n.locale, {
      dateStyle: "medium",
      timeZone: "UTC",
    }).format(new Date(Date.UTC(year, month - 1, day, 12)));
  };
  const fmtTime = (value) => {
    if (!value) return window.i18n.t("currencyNeverFetched");
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? ""
      : new Intl.DateTimeFormat(window.i18n.locale, {
          dateStyle: "short",
          timeStyle: "short",
        }).format(date);
  };
  function update() {
    if (picker) picker.value = selected;
    const note = document.getElementById("currency-note");
    if (!note) return;
    const names = {
      CBU: window.i18n.t("currencySourceCBU"),
      CBR: window.i18n.t("currencySourceCBR"),
      reference: window.i18n.t("currencySourceReference"),
    };
    const labels = {
      fresh: window.i18n.t("currencyFresh"),
      stale: window.i18n.t("currencyStale"),
      fallback: window.i18n.t("currencyFallback"),
      loading: window.i18n.t("currencyLoading"),
    };
    const rate =
      selected === "UZS"
        ? ""
        : `1 ${selected} = ${new Intl.NumberFormat(window.i18n.locale, { maximumFractionDigits: 2 }).format(rates[selected])} UZS.`;
    note.textContent = window.i18n.t("currencyNote", {
      rate,
      source: names[source],
      rateDate: fmtDate(rateDate),
      fetchedAt: fmtTime(fetchedAt),
      freshness: labels[loading ? "loading" : status],
    });
  }
  function validPayload(data) {
    if (
      !data ||
      data.base !== "UZS" ||
      !data.rates ||
      data.rates.UZS !== 1 ||
      !/^\d{4}-\d{2}-\d{2}$/.test(data.rate_date || "")
    )
      return false;
    const d = new Date(`${data.rate_date}T00:00:00Z`);
    if (
      Number.isNaN(d.getTime()) ||
      d.toISOString().slice(0, 10) !== data.rate_date
    )
      return false;
    if (
      !["fresh", "stale", "fallback"].includes(data.status) ||
      !["CBU", "CBR", "reference"].includes(data.source)
    )
      return false;
    if (
      data.status !== "fallback" &&
      (typeof data.fetched_at !== "string" ||
        Number.isNaN(Date.parse(data.fetched_at)))
    )
      return false;
    if ((data.status === "fallback") !== (data.source === "reference"))
      return false;
    if (!["RUB", "USD"].every(
      (c) =>
        typeof data.rates[c] === "number" &&
        Number.isFinite(data.rates[c]) &&
        data.rates[c] > 0 &&
        data.rates[c] <= 1e9,
    ))
      return false;
    return bookingRates(data) !== false;
  }
  function refresh(force = false) {
    const now = Date.now();
    if (inFlight) return inFlight;
    if (!force && now - lastStarted < 60000) return Promise.resolve(false);
    lastStarted = now;
    if (typeof fetch !== "function") {
      loading = false;
      update();
      return Promise.resolve(false);
    }
    loading = true;
    update();
    let timer;
    const controller =
      typeof AbortController === "function" ? new AbortController() : null;
    if (controller) timer = setTimeout(() => controller.abort(), 10000);
    inFlight = fetch("/exchange-rates", { signal: controller?.signal })
      .then((res) => {
        if (!res.ok) throw new Error("rates unavailable");
        return res.json();
      })
      .then((data) => {
        if (!validPayload(data)) throw new Error("invalid rates");
        rates.RUB = data.rates.RUB;
        rates.USD = data.rates.USD;
        exactRates =
          bookingRates(data) || {
            UZS: "1",
            RUB: String(data.rates.RUB),
            USD: String(data.rates.USD),
          };
        rateDate = data.rate_date;
        fetchedAt = data.fetched_at;
        status = data.status;
        source = data.source;
        loading = false;
        update();
        window.dispatchEvent(new Event("currencychange"));
        return true;
      })
      .catch(() => {
        loading = false;
        if (status === "fresh") status = "stale";
        update();
        return false;
      })
      .finally(() => {
        if (timer !== undefined) clearTimeout(timer);
        inFlight = null;
      });
    return inFlight;
  }
  window.currency = {
    convert(value) {
      return Number(value) / rates[selected];
    },
    convertExact(value) {
      return convertExact(value, exactRates[selected]);
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
    refresh() {
      return refresh(true);
    },
  };
  picker?.addEventListener("change", (e) =>
    window.currency.set(e.target.value),
  );
  window.addEventListener("languagechange", update);
  window.addEventListener("online", () => refresh());
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") refresh();
  });
  setInterval(() => {
    if (document.visibilityState === "visible") refresh();
  }, 900000);
  update();
  refresh();
})();
