"use strict";
(() => {
  let target = null, correcting = false, pending = false;
  function show(payment, student, correct) {
    if (paymentPending || pending) return;
    target = { payment, student };
    correcting = correct;
    $("void-form").reset();
    $("void-reason").setCustomValidity("");
    message("void-message", "");
    $("void-title").textContent = t(correct ? "correctPayment" : "voidPayment");
    $("void-note").textContent = t(correct ? "correctionNote" : "voidNote");
    $("confirm-void").textContent = t(correct ? "voidAndPrepare" : "confirmVoid");
    $("void-description").textContent = `${student.name} · ${paymentNumber(payment.amount, payment.currency)} · ${new Intl.DateTimeFormat(window.i18n.locale).format(new Date(payment.date + "T12:00:00"))}`;
    $("void-dialog").showModal();
  }
  $("close-void").onclick = () => { if (!pending) $("void-dialog").close(); };
  $("void-dialog").addEventListener("cancel", event => { if (pending) event.preventDefault(); });
  $("void-reason").addEventListener("input", () => $("void-reason").setCustomValidity(""));
  $("void-form").onsubmit = async event => {
    event.preventDefault();
    if (pending || !target) return;
    const reason = $("void-reason").value.trim();
    if (!reason) {
      $("void-reason").setCustomValidity(t("reasonRequired"));
      $("void-reason").reportValidity();
      return;
    }
    pending = true;
    const { payment, student } = target;
    const prepare = correcting;
    ["close-void", "confirm-void", "void-reason"].forEach(id => $(id).disabled = true);
    message("void-message", t("saving"));
    try {
      await request(`/payments/${payment.id}/void`, { method: "POST", body: JSON.stringify({ reason }) });
      // This is a separate payment draft. Nothing is silently posted at a new FX rate.
      // Keep the modal blocking the payment form until its draft is ready.
      await refresh();
      $("void-dialog").close();
      $("history-dialog").close();
      if (prepare) {
        activateView("debts-tab");
        clearValidation($("payment-form"));
        paymentAttempt = null;
        paymentContextMonth = null;
        $("pay-student").value = student.id;
        $("pay-amount").value = payment.amount;
        $("pay-currency").value = payment.currency;
        $("pay-date").value = payment.date;
        paymentDateBounds();
        message("payment-message", t("correctionDraft"));
        $("payment-form").scrollIntoView({ block: "center" });
        $("pay-amount").focus();
      } else {
        await history(student);
      }
    } catch (error) {
      message("void-message", error.message, true);
    } finally {
      pending = false;
      syncPaymentActions();
      ["close-void", "confirm-void", "void-reason"].forEach(id => $(id).disabled = false);
    }
  };
  window.paymentActions = Object.freeze({ append(row, payment, student) {
    const actions = node("div", undefined, "payment-actions");
    const edit = button(t("correctPayment"), () => show(payment, student, true));
    const cancel = button(t("voidPayment"), () => show(payment, student, false), "text-button delete");
    edit.disabled = cancel.disabled = paymentPending || pending;
    actions.append(edit, cancel);
    row.append(actions);
  } });
})();
