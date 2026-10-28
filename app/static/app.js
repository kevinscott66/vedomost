"use strict";
const $ = (id) => document.getElementById(id);
const localDate = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const number = (value) =>
  new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
let students = [],
  deleteId = null,
  generation = 0;
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
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    let message = "Не удалось выполнить запрос. Попробуйте ещё раз.";
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail))
        message =
          "Проверьте поля: " + data.detail.map((e) => e.loc.at(-1)).join(", ");
    } catch {}
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}
function message(id, text, error = false) {
  $(id).textContent = text;
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
    new Option("Выберите ученика", ""),
    ...students.map((s) => new Option(`${s.name} — ${s.group}`, s.id)),
  );
  if (students.some((s) => String(s.id) === selected))
    $("pay-student").value = selected;
  $("save-payment").disabled = !students.length;
  const list = $("students-list");
  list.replaceChildren();
  if (!students.length) {
    list.append(
      empty(
        "Начните с ученика",
        "Добавьте имя, группу и месячную сумму оплаты.",
      ),
    );
    return;
  }
  for (const s of students) {
    const row = node("div", undefined, "student-row");
    const info = person(s);
    info.append(
      node("span", `${number(s.monthly_fee)} за месяц`, "person-detail"),
    );
    const actions = node("div", undefined, "student-actions");
    actions.append(
      button("История оплат", () => history(s)),
      button("Изменить", () => editStudent(s)),
      button(
        "Удалить",
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
  const [whole, fraction] = number(report.total_debt).split(",");
  $("total").replaceChildren(
    document.createTextNode(whole),
    node("span", "," + fraction, "minor-amount"),
  );
  $("debt-count").textContent = report.debtors.length;
  const count = report.debtors.length;
  $("debt-count-label").textContent =
    count % 10 === 1 && count % 100 !== 11
      ? "ученик"
      : count % 10 >= 2 &&
          count % 10 <= 4 &&
          !(count % 100 >= 12 && count % 100 <= 14)
        ? "ученика"
        : "учеников";
  const list = $("debt-list");
  list.replaceChildren();
  if (!students.length) {
    list.append(
      empty(
        "Ведомость пока пуста",
        "Добавьте первого ученика, чтобы начать учёт.",
      ),
    );
    return;
  }
  if (!report.debtors.length) {
    list.append(empty("Всё оплачено", "За выбранный месяц задолженности нет."));
    return;
  }
  const head = node("div", undefined, "table-head");
  ["Ученик / Группа", "Оплачено", "Осталось", ""].forEach((t) =>
    head.append(node("span", t)),
  );
  list.append(head);
  for (const s of report.debtors) {
    const row = node("div", undefined, "debtor-row");
    const paid = node("div", number(s.paid), "amount");
    paid.setAttribute("data-label", "Внесено");
    const debt = node("div", number(s.debt), "amount debt");
    debt.setAttribute("data-label", "Осталось");
    const pay = button(
      "Внести",
      () => {
        $("pay-student").value = s.id;
        $("pay-amount").value = s.debt;
        $("payment-form").scrollIntoView({ block: "center" });
        $("pay-amount").focus();
      },
      "pay-button",
    );
    pay.setAttribute("aria-label", `Внести оплату: ${s.name}`);
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
    renderDebtors(report);
  } catch (e) {
    if (ticket !== generation) return;
    $("global-error").replaceChildren(
      node("span", e.message + " "),
      button("Повторить", refresh),
    );
    $("global-error").hidden = false;
    $("total").textContent = "—";
    $("debt-count").textContent = "—";
    $("debt-count-label").textContent = "Нет данных";
    $("debt-list").replaceChildren(
      empty(
        "Не удалось загрузить ведомость",
        "Проверьте соединение с сервером и повторите запрос.",
      ),
    );
  }
}
$("month").addEventListener("change", refresh);
function moveMonth(offset) {
  const [year, month] = $("month").value.split("-").map(Number);
  const index = year * 12 + month - 1 + offset;
  const nextYear = Math.floor(index / 12),
    nextMonth = (index % 12) + 1;
  if (
    nextYear < 1 ||
    nextYear > 9999 ||
    (nextYear === 9999 && nextMonth === 12)
  )
    return;
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
    $("page-title").textContent = tab === "debts-tab" ? "Оплаты" : "Ученики";
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
  $("student-title").textContent = s ? "Изменить ученика" : "Новый ученик";
  for (const [field, key] of [
    ["name", "name"],
    ["phone", "phone"],
    ["group", "group"],
    ["fee", "monthly_fee"],
  ])
    $("student-" + field).value = s?.[key] ?? "";
  message("student-message", "");
  $("student-dialog").showModal();
}
$("new-student").onclick = () => editStudent();
$("close-student").onclick = () => $("student-dialog").close();
$("close-history").onclick = () => $("history-dialog").close();
$("cancel-delete").onclick = () => $("delete-dialog").close();
$("student-form").onsubmit = async (event) => {
  event.preventDefault();
  const id = $("student-id").value;
  const payload = {
    name: $("student-name").value,
    phone: $("student-phone").value,
    group: $("student-group").value,
    monthly_fee: $("student-fee").value,
  };
  $("save-student").disabled = true;
  message("student-message", "Сохраняем…");
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
    $("save-student").disabled = false;
  }
};
$("payment-form").onsubmit = async (event) => {
  event.preventDefault();
  $("save-payment").disabled = true;
  message("payment-message", "Сохраняем…");
  try {
    const payload = {
      student_id: Number($("pay-student").value),
      amount: $("pay-amount").value,
      date: $("pay-date").value,
    };
    await request("/payments", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    $("pay-amount").value = "";
    message("payment-message", "Оплата сохранена.");
    await refresh();
  } catch (e) {
    message("payment-message", e.message, true);
  } finally {
    $("save-payment").disabled = !students.length;
  }
};
async function history(s) {
  $("history-title").textContent = "Оплаты: " + s.name;
  $("history-list").textContent = "Загружаем…";
  $("history-dialog").showModal();
  try {
    const rows = await request(`/students/${s.id}/payments`);
    $("history-list").replaceChildren();
    if (!rows.length)
      $("history-list").append(
        empty("Пока без оплат", "Новые записи появятся здесь."),
      );
    for (const p of rows) {
      const row = node("div", undefined, "history-row");
      row.append(
        node("span", p.date.split("-").reverse().join(".")),
        node("strong", number(p.amount)),
      );
      $("history-list").append(row);
    }
  } catch (e) {
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

function syncThemeButton() {
  const light = document.documentElement.dataset.theme === "light";
  $("theme-toggle").setAttribute(
    "aria-label",
    light ? "Включить тёмную тему" : "Включить светлую тему",
  );
  $("theme-label").textContent = light ? "Тёмная тема" : "Светлая тема";
  $("theme-icon").src = light
    ? "/static/icons/moon.svg"
    : "/static/icons/sun.svg";
}
$("theme-toggle").onclick = () => {
  const theme =
    document.documentElement.dataset.theme === "light" ? "dark" : "light";
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem("vedomost-theme", theme);
  } catch {}
  syncThemeButton();
};
syncThemeButton();
