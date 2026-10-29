"use strict";
(() => {
  let entries = [], cursor = null, revision = 0, pending = false, failed = false;
  const actionKeys = {
    "student.add": "eventStudentAdd", "student.update": "eventStudentUpdate",
    "student.delete": "eventStudentDelete", "payment.add": "eventPaymentAdd", "payment.void": "eventPaymentVoid",
  };
  function render() {
    const list = $("activity-list");
    list.replaceChildren();
    for (const entry of entries) {
      const item = node("article", undefined, "activity-entry");
      const head = node("div", undefined, "activity-head");
      head.append(node("strong", t(actionKeys[entry.action] || "activityTitle")),
        node("time", new Intl.DateTimeFormat(window.i18n.locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(entry.created_at))));
      item.append(head, node("p", entry.student_name, "activity-person"));
      const payment = entry.detail.payment;
      if (payment) {
        item.append(node("p", `#${payment.id} · ${paymentNumber(payment.amount, payment.currency)} · ${payment.date}`, "activity-detail"));
        if (payment.currency !== "UZS") item.append(node("p", t("baseEquivalent", { amount: paymentNumber(payment.base_amount, "UZS") }), "activity-detail"));
        if (payment.void_reason) item.append(node("p", payment.void_reason, "void-reason"));
      } else {
        const before = entry.detail.before, after = entry.detail.after;
        for (const [key, label] of [["name", "name"], ["phone", "phone"], ["group", "group"], ["monthly_fee", "monthlyFee"], ["start_month", "startMonth"]]) {
          if (before && after && before[key] === after[key]) continue;
          const format = value => key === "monthly_fee" ? paymentNumber(value, "UZS") : key === "start_month" ? window.i18n.formatMonth(value) : value;
          const text = before && after ? `${format(before[key])} → ${format(after[key])}` : format((after || before)[key]);
          item.append(node("p", `${t(label)}: ${text}`, "activity-detail"));
        }
      }
      list.append(item);
    }
    if (pending) list.append(node("p", t("loading"), "muted"));
    else if (failed) list.append(node("p", t("loadError"), "error"), button(t("retry"), () => load(false)));
    else if (!entries.length) list.append(empty(t("activityEmpty"), ""));
    $("activity-more").hidden = !cursor;
    $("activity-more").disabled = pending;
    $("activity-refresh").disabled = pending;
  }
  async function load(more = false) {
    const ticket = ++revision;
    const before = more ? cursor : null;
    if (!more) { entries = []; cursor = null; }
    pending = true; failed = false; render();
    try {
      const data = await request("/activity" + (before ? `?before=${before}` : ""));
      if (ticket !== revision) return;
      entries = more ? [...entries, ...data.items] : data.items;
      cursor = data.next_before;
    } catch { if (ticket === revision) failed = true; }
    finally { if (ticket === revision) { pending = false; render(); } }
  }
  $("activity-refresh").onclick = () => load();
  $("activity-more").onclick = () => load(true);
  window.addEventListener("languagechange", render);
  window.activityJournal = Object.freeze({ load });
})();
