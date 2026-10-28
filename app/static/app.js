"use strict";
const $ = (id) => document.getElementById(id);
const t = (key, values) => window.i18n.t(key, values);
const localDate = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const number = (value) =>
  new Intl.NumberFormat(window.i18n.locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(window.currency.convert(value)) +
  "\u00a0" +
  window.currency.unit;
let students = [],
  deleteId = null,
  generation = 0;
let paymentPending = false;
let studentPending = false;
let paymentAttempt = null;
let historyGeneration = 0;
let paymentContextMonth = null;
let lastReport = null,
  historyStudent = null;
$("month").value = localDate().slice(0, 7);
$("pay-date").value = localDate();
function node(tag, text, cls) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (cls) el.className = cls;
  return el;
}
function button(text, action, cls = "text-button") {
  const b = node("button", text, cls);
  b.type = "button";
  b.addEventListener("click", action);
  return b;
}
async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error(t("requestError"));
  }
  if (!response.ok) {
    let message = t("requestError");
    try {
      const data = await response.json();
      if (typeof data.detail === "string") {
        const known = {
          "Ученик не найден": "studentMissing",
          "Дата оплаты раньше начала обучения": "paymentBeforeStart",
          "Начало обучения позже существующих оплат": "startAfterPayments",
          "Нельзя удалить ученика с оплатами: история должна сохраниться":
            "historyProtected",
        };
        message = known[data.detail]
          ? t(known[data.detail])
          : response.status === 422
            ? t("invalidMonth")
            : t("requestError");
      } else if (Array.isArray(data.detail))
        message = t("checkFields", {
          fields: data.detail
            .map((e) =>
              t(
                {
                  student_id: "student",
                  monthly_fee: "monthlyFee",
                  start_month: "startMonth",
                }[e.loc.at(-1)] || e.loc.at(-1),
              ),
            )
            .join(", "),
        });
    } catch {}
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}
function message(id, text, error = false) {
  $(id).textContent = text;
  const key = window.i18n.keyFor(text);
  if (key) $(id).dataset.statusKey = key;
  else delete $(id).dataset.statusKey;
  $(id).classList.toggle("error", error);
}
function empty(title, text) {
  const e = node("div", undefined, "empty");
  e.append(node("strong", title), node("span", text));
  return e;
}
function person(s) {
  const e = node("div", undefined, "person");
  e.append(
    node("span", s.name, "person-name"),
    node("span", `${s.group} · ${s.phone}`, "person-detail"),
  );
  return e;
}
function renderStudents() {
  $("student-count").textContent = students.length;
  const selected = $("pay-student").value;
  $("pay-student").replaceChildren(
    new Option(t("chooseStudent"), ""),
    ...students.map((s) => new Option(`${s.name} — ${s.group}`, s.id)),
  );
  if (students.some((s) => String(s.id) === selected))
    $("pay-student").value = selected;
  $("save-payment").disabled = paymentPending || !students.length;
  paymentDateBounds();
  const list = $("students-list");
  list.replaceChildren();
  if (!students.length) {
    list.append(empty(t("startStudent"), t("startStudentText")));
    return;
  }
  for (const s of students) {
    const row = node("div", undefined, "student-row");
    const info = person(s);
    info.append(
      node(
        "span",
        t("perMonth", { amount: number(s.monthly_fee) }),
        "person-detail",
      ),
    );
    info.append(
      node(
        "span",
        t("enrolledFrom", { month: window.i18n.formatMonth(s.start_month) }),
        "person-detail",
      ),
    );
    const actions = node("div", undefined, "student-actions");
    actions.append(
      button(t("history"), () => history(s)),
      button(t("edit"), () => editStudent(s)),
      button(
        t("delete"),
        () => {
          deleteId = s.id;
          $("delete-description").textContent = s.name;
          message("delete-message", "");
          $("delete-dialog").showModal();
        },
        "text-button delete",
      ),
    );
    row.append(info, actions);
    list.append(row);
  }
}
function renderDebtors(report) {
  const parts = new Intl.NumberFormat(window.i18n.locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).formatToParts(window.currency.convert(report.total_debt));
  const whole = parts
    .filter((p) => p.type !== "decimal" && p.type !== "fraction")
    .map((p) => p.value)
    .join("");
  const minor = parts
    .filter((p) => p.type === "decimal" || p.type === "fraction")
    .map((p) => p.value)
    .join("");
  $("total").replaceChildren(
    document.createTextNode(
      (window.currency.code === "UZS" ? "" : "≈ ") + whole,
    ),
    node("span", minor, "minor-amount"),
    node("span", "\u00a0" + window.currency.unit, "currency-unit"),
  );
  $("debt-count").textContent = report.debtors.length;
  const count = report.debtors.length;
  const plural = new Intl.PluralRules(window.i18n.locale).select(count);
  $("debt-count-label").textContent = t(
    plural === "one"
      ? "studentOne"
      : plural === "few"
        ? "studentFew"
        : "studentMany",
  );
  const list = $("debt-list");
  list.replaceChildren();
  if (!students.length) {
    list.append(empty(t("emptyLedger"), t("emptyLedgerText")));
    return;
  }
  if (!report.debtors.length) {
    const active = students.some((s) => s.start_month <= report.month);
    list.append(
      empty(
        t(active ? "allPaid" : "noCharges"),
        t(active ? "allPaidText" : "noChargesText"),
      ),
    );
    return;
  }
  const head = node("div", undefined, "table-head");
  [t("studentGroup"), t("paid"), t("remaining"), ""].forEach((t) =>
    head.append(node("span", t)),
  );
  list.append(head);
  for (const s of report.debtors) {
    const row = node("div", undefined, "debtor-row");
    const paid = node("div", number(s.paid), "amount");
    paid.setAttribute("data-label", t("paid"));
    const debt = node("div", number(s.debt), "amount debt");
    debt.setAttribute("data-label", t("remaining"));
    const pay = button(
      t("pay"),
      () => {
        $("pay-student").value = s.id;
        $("pay-amount").value = s.debt;
        paymentContextMonth = report.month;
        if ($("pay-date").value.slice(0, 7) !== report.month)
          $("pay-date").value = "";
        paymentDateBounds();
        message(
          "payment-message",
          t("paymentPeriod", { month: window.i18n.formatMonth(report.month) }),
        );
        $("payment-form").scrollIntoView({ block: "center" });
        $("pay-amount").focus();
      },
      "pay-button",
    );
    pay.setAttribute("aria-label", t("payFor", { name: s.name }));
    const identity = node("div", undefined, "debtor-person");
    identity.append(
      node("div", s.name, "debtor-name"),
      node("div", s.group, "debtor-group"),
    );
    row.append(identity, paid, debt, pay);
    list.append(row);
  }
}
async function refresh() {
  monthLabel();
  if (paymentContextMonth && paymentContextMonth !== $("month").value) {
    paymentContextMonth = null;
    paymentDateBounds();
    message("payment-message", "");
  }
  const ticket = ++generation;
  const month = $("month").value;
  if (!month) return;
  $("global-error").hidden = true;
  try {
    const [all, report] = await Promise.all([
      request("/students"),
      request("/debtors?month=" + encodeURIComponent(month)),
    ]);
    if (ticket !== generation) return;
    students = all;
    renderStudents();
    lastReport = report;
    renderDebtors(report);
  } catch (e) {
    if (ticket !== generation) return;
    lastReport = null;
    $("global-error").replaceChildren(
      node("span", e.message + " "),
      button(t("retry"), refresh),
    );
    $("global-error").hidden = false;
    $("total").textContent = "—";
    $("debt-count").textContent = "—";
    $("debt-count-label").textContent = t("noData");
    $("debt-list").replaceChildren(empty(t("loadError"), t("loadErrorText")));
  }
}
function monthLabel() {
  const value = $("month").value;
  if (value) $("month-display").textContent = window.i18n.formatMonth(value);
}
$("month").addEventListener("change", refresh);
function moveMonth(offset) {
  const [year, month] = $("month").value.split("-").map(Number);
  const index = year * 12 + month - 1 + offset;
  const nextYear = Math.floor(index / 12),
    nextMonth = (index % 12) + 1;
  if (nextYear < 1 || nextYear > 9999) return;
  $("month").value =
    `${String(nextYear).padStart(4, "0")}-${String(nextMonth).padStart(2, "0")}`;
  refresh();
}
$("previous-month").onclick = () => moveMonth(-1);
$("next-month").onclick = () => moveMonth(1);
for (const [tab, other, view, otherView] of [
  ["debts-tab", "students-tab", "debts-view", "students-view"],
  ["students-tab", "debts-tab", "students-view", "debts-view"],
])
  $(tab).onclick = () => {
    $("page-title").textContent =
      tab === "debts-tab" ? t("apiPayments") : t("apiStudents");
    document
      .querySelector("main")
      .classList.toggle("students-mode", tab === "students-tab");
    $(tab).setAttribute("aria-pressed", "true");
    $(other).setAttribute("aria-pressed", "false");
    $(view).hidden = false;
    $(otherView).hidden = true;
  };
function editStudent(s = null) {
  $("student-form").reset();
  $("student-id").value = s?.id ?? "";
  $("student-title").textContent = s ? t("editStudent") : t("newStudent");
  for (const [field, key] of [
    ["name", "name"],
    ["phone", "phone"],
    ["group", "group"],
    ["fee", "monthly_fee"],
  ])
    $("student-" + field).value = s?.[key] ?? "";
  $("student-start").value = s?.start_month ?? localDate().slice(0, 7);
  message("student-message", "");
  $("student-dialog").showModal();
}
$("new-student").onclick = () => editStudent();
$("close-student").onclick = () => $("student-dialog").close();
$("close-history").onclick = () => $("history-dialog").close();
$("cancel-delete").onclick = () => $("delete-dialog").close();
$("student-form").onsubmit = async (event) => {
  event.preventDefault();
  if (studentPending) return;
  studentPending = true;
  const id = $("student-id").value;
  const payload = {
    name: $("student-name").value,
    phone: $("student-phone").value,
    group: $("student-group").value,
    monthly_fee: $("student-fee").value,
    start_month: $("student-start").value,
  };
  $("save-student").disabled = true;
  message("student-message", t("saving"));
  try {
    await request("/students" + (id ? "/" + id : ""), {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    $("student-dialog").close();
    await refresh();
  } catch (e) {
    message("student-message", e.message, true);
  } finally {
    studentPending = false;
    $("save-student").disabled = false;
  }
};
function paymentDateBounds() {
  const student = students.find((s) => String(s.id) === $("pay-student").value);
  const date = $("pay-date");
  date.min = student ? student.start_month + "-01" : "0001-01-01";
  date.max = "9999-12-31";
  if (paymentContextMonth) {
    const bounds = window.ledgerCalendar.bounds(paymentContextMonth);
    date.min = bounds.min;
    date.max = bounds.max;
  }
}
$("pay-student").addEventListener("change", () => {
  paymentContextMonth = null;
  paymentDateBounds();
  message("payment-message", "");
});
$("payment-form").onsubmit = async (event) => {
  event.preventDefault();
  if (paymentPending) return;
  if (
    paymentContextMonth &&
    $("pay-date").value.slice(0, 7) !== paymentContextMonth
  ) {
    message(
      "payment-message",
      t("paymentPeriod", {
        month: window.i18n.formatMonth(paymentContextMonth),
      }),
      true,
    );
    return;
  }
  paymentPending = true;
  const controls = [...event.currentTarget.querySelectorAll("input, select")];
  controls.forEach((control) => (control.disabled = true));
  $("save-payment").disabled = true;
  message("payment-message", t("saving"));
  try {
    const payload = {
      student_id: Number($("pay-student").value),
      amount: $("pay-amount").value,
      date: $("pay-date").value,
    };
    const body = JSON.stringify(payload);
    if (!paymentAttempt || paymentAttempt.body !== body)
      paymentAttempt = { body, key: crypto.randomUUID() };
    await request("/payments", {
      method: "POST",
      headers: { "Idempotency-Key": paymentAttempt.key },
      body,
    });
    paymentAttempt = null;
    $("pay-amount").value = "";
    message("payment-message", t("paymentSaved"));
    await refresh();
  } catch (e) {
    message("payment-message", e.message, true);
  } finally {
    paymentPending = false;
    controls.forEach((control) => (control.disabled = false));
    $("save-payment").disabled = !students.length;
  }
};
async function history(s) {
  const ticket = ++historyGeneration;
  historyStudent = s;
  $("history-title").textContent = t("historyFor", { name: s.name });
  $("history-list").textContent = t("loading");
  $("history-dialog").showModal();
  try {
    const rows = await request(`/students/${s.id}/payments`);
    if (ticket !== historyGeneration || !$("history-dialog").open) return;
    $("history-list").replaceChildren();
    if (!rows.length)
      $("history-list").append(empty(t("noPayments"), t("noPaymentsText")));
    for (const p of rows) {
      const row = node("div", undefined, "history-row");
      row.append(
        node(
          "span",
          new Intl.DateTimeFormat(window.i18n.locale).format(
            new Date(p.date + "T12:00:00"),
          ),
        ),
        node("strong", number(p.amount)),
      );
      $("history-list").append(row);
    }
  } catch (e) {
    if (ticket !== historyGeneration || !$("history-dialog").open) return;
    $("history-list").textContent = e.message;
  }
}
$("confirm-delete").onclick = async () => {
  $("confirm-delete").disabled = true;
  try {
    await request("/students/" + deleteId, { method: "DELETE" });
    $("delete-dialog").close();
    await refresh();
  } catch (e) {
    message("delete-message", e.message, true);
  } finally {
    $("confirm-delete").disabled = false;
  }
};
refresh();

function refreshDisplay() {
  renderStudents();
  if (lastReport) renderDebtors(lastReport);
  monthLabel();
  $("page-title").textContent = t(
    $("students-view").hidden ? "payments" : "students",
  );
  $("student-title").textContent = t(
    $("student-id").value ? "editStudent" : "newStudent",
  );
  if ($("history-dialog").open && historyStudent) history(historyStudent);
}
window.addEventListener("languagechange", refreshDisplay);
window.addEventListener("currencychange", refreshDisplay);
