function accountsPage() {
  return {
    selected: [],
    modal: null,
    toggle(id, e) {
      if (e.target.checked) {
        if (!this.selected.includes(id)) this.selected.push(id);
      } else {
        this.selected = this.selected.filter((x) => x !== id);
      }
    },
    toggleAll(e) {
      const boxes = Array.from(document.querySelectorAll(".row-check"));
      const ids = boxes.map((el) => parseInt(el.value, 10));
      this.selected = e.target.checked ? ids : [];
      boxes.forEach((el) => (el.checked = e.target.checked));
    },
    openModal(name) {
      this.modal = name;
    },
    closeModal() {
      this.modal = null;
    },
    submitForm(formId) {
      const form = document.getElementById(formId);
      if (!form) return;
      form.querySelectorAll('input[name="account_ids"]').forEach((el) => el.remove());
      this.selected.forEach((id) => {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = "account_ids";
        input.value = id;
        form.appendChild(input);
      });
      form.submit();
    },
  };
}

function toggleAllGroupAccounts(checked) {
  document.querySelectorAll(".group-account-check").forEach((el) => (el.checked = checked));
  updateGroupSelectedCount();
}

function updateGroupSelectedCount() {
  const el = document.getElementById("groupSelectedCount");
  if (!el) return;
  el.textContent = document.querySelectorAll(".group-account-check:checked").length;
}

document.addEventListener("DOMContentLoaded", updateGroupSelectedCount);

function toggleAllWarmupAccounts(checked) {
  document.querySelectorAll(".warmup-account-check:not(:disabled)").forEach((el) => (el.checked = checked));
  updateWarmupSelectedCount();
}

function updateWarmupSelectedCount() {
  const el = document.getElementById("warmupSelectedCount");
  if (!el) return;
  el.textContent = document.querySelectorAll(".warmup-account-check:checked").length;
}

document.addEventListener("DOMContentLoaded", updateWarmupSelectedCount);
