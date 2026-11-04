const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function focusables(root) {
  return Array.from(root.querySelectorAll(FOCUSABLE)).filter((el) => el.getClientRects().length > 0);
}

function accountsPage() {
  return {
    selected: [],
    modal: null,
    menu: null,
    menuUp: false,
    menuTrigger: null,
    lastFocus: null,
    inerted: [],

    init() {
      this.$watch("selected", (v) => document.body.classList.toggle("has-selection", v.length > 0));
      this.$watch("modal", (v) => document.body.classList.toggle("has-modal", !!v));
    },
    rowIds() {
      return Array.from(document.querySelectorAll(".row-check")).map((el) => parseInt(el.value, 10));
    },
    isSelected(id) {
      return this.selected.includes(id);
    },
    allSelected() {
      const ids = this.rowIds();
      return ids.length > 0 && ids.every((id) => this.selected.includes(id));
    },
    toggle(id, e) {
      if (e.target.checked) {
        if (!this.selected.includes(id)) this.selected.push(id);
      } else {
        this.selected = this.selected.filter((x) => x !== id);
      }
    },
    toggleAll(e) {
      this.selected = e.target.checked ? this.rowIds() : [];
    },
    clearSelection() {
      this.selected = [];
    },

    recipients() {
      return this.selected
        .map((id) => {
          const row = document.querySelector(`tr[data-account-id="${id}"]`);
          if (!row) return null;
          const av = row.querySelector(".avatar");
          return { id, name: row.dataset.name, avatar: av ? av.outerHTML : "" };
        })
        .filter(Boolean);
    },
    recipientFirst() {
      const r = this.recipients();
      return r.length ? r[0].name : "";
    },
    recipientRest() {
      const n = this.selected.length;
      return n > 1 ? ` 외 ${n - 1}개 계정` : "";
    },

    dialog() {
      return this.modal ? document.querySelector(`[data-modal="${this.modal}"] .modal`) : null;
    },
    setInert(keep) {
      this.inerted.forEach((el) => (el.inert = false));
      this.inerted = [];
      for (let el = keep; el && el.parentElement && el !== document.body; el = el.parentElement) {
        for (const sib of el.parentElement.children) {
          if (sib === el || sib.inert || sib.tagName === "SCRIPT" || sib.tagName === "TEMPLATE") continue;
          sib.inert = true;
          this.inerted.push(sib);
        }
      }
    },
    openModal(name) {
      this.menu = null;
      this.lastFocus = document.activeElement;
      this.modal = name;
      this.$nextTick(() => {
        this.setInert(document.querySelector(`[data-modal="${name}"]`));
        requestAnimationFrame(() => {
          const dlg = this.dialog();
          if (!dlg) return;
          const touch = window.matchMedia("(pointer: coarse)").matches;
          const target = touch ? dlg : dlg.querySelector("input[type=text], textarea") || dlg.querySelector("input[type=file]") || dlg;
          target.focus({ preventScroll: true });
        });
      });
    },
    closeModal() {
      this.setInert(null);
      this.modal = null;
      if (this.lastFocus && document.contains(this.lastFocus)) this.lastFocus.focus({ preventScroll: true });
      this.lastFocus = null;
    },
    trapTab(e) {
      const dlg = this.dialog();
      if (!dlg) return;
      const items = focusables(dlg);
      if (!items.length) {
        e.preventDefault();
        dlg.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      const outside = !dlg.contains(active) || active === dlg;
      if (e.shiftKey && (active === first || outside)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (active === last || outside)) {
        e.preventDefault();
        first.focus();
      }
    },

    viewportBounds() {
      let top = 0;
      let bottom = window.innerHeight;
      for (const sel of [".mtop", ".tabbar", ".bulkbar"]) {
        const el = document.querySelector(sel);
        if (!el) continue;
        const r = el.getBoundingClientRect();
        if (!r.height) continue;
        if (sel === ".mtop") top = Math.max(top, r.bottom);
        else if (r.top < bottom && r.bottom > 0) bottom = Math.min(bottom, r.top);
      }
      return { top, bottom };
    },
    openMenu(id, trigger, focusWhich) {
      this.menuTrigger = trigger;
      this.menuUp = false;
      this.menu = id;
      this.$nextTick(() => {
        const menu = document.getElementById(`menu-${id}`);
        if (!menu) return;
        const t = trigger.getBoundingClientRect();
        const { top, bottom } = this.viewportBounds();
        const below = bottom - t.bottom;
        const above = t.top - top;
        this.menuUp = below < menu.offsetHeight + 12 && above > below;
        if (focusWhich) this.focusMenuItem(menu, focusWhich);
      });
    },
    toggleMenu(id, e) {
      if (this.menu === id) {
        this.menu = null;
        return;
      }
      this.openMenu(id, e.currentTarget, e.detail === 0 ? "first" : null);
    },
    openMenuFromKey(id, e, which) {
      if (this.menu === id) this.focusMenuItem(document.getElementById(`menu-${id}`), which);
      else this.openMenu(id, e.currentTarget, which);
    },
    focusMenuItem(menu, which) {
      const items = Array.from(menu.querySelectorAll('[role="menuitem"]'));
      const target = which === "last" ? items[items.length - 1] : items[0];
      if (target) target.focus();
    },
    menuKey(e) {
      const items = Array.from(e.currentTarget.querySelectorAll('[role="menuitem"]'));
      const i = items.indexOf(document.activeElement);
      const moves = {
        ArrowDown: items[(i + 1) % items.length],
        ArrowUp: items[(i - 1 + items.length) % items.length],
        Home: items[0],
        End: items[items.length - 1],
      };
      const next = moves[e.key];
      if (next) {
        e.preventDefault();
        next.focus();
      }
    },
    onMenuBlur(id, e) {
      if (this.menu === id && e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) this.menu = null;
    },
    onEscape() {
      if (this.menu !== null) {
        const trigger = this.menuTrigger;
        const wrap = trigger && trigger.closest(".row-actions");
        const inside = wrap && wrap.contains(document.activeElement);
        this.menu = null;
        if (inside) trigger.focus();
      } else if (this.modal) {
        this.closeModal();
      }
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

function fileDrop() {
  return {
    names: [],
    over: false,
    preview: "",
    pick(e) {
      const files = Array.from(e.target.files || []);
      this.names = files.map((f) => f.name);
      if (this.preview) URL.revokeObjectURL(this.preview);
      this.preview = files[0] && files[0].type.startsWith("image/") ? URL.createObjectURL(files[0]) : "";
      this.over = false;
    },
  };
}

function colorPicker(initial) {
  return {
    color: initial,
    label: "",
    is(c) {
      return (this.color || "").toLowerCase() === c.toLowerCase();
    },
  };
}

function openDialog(name) {
  window.dispatchEvent(new CustomEvent("open-modal", { detail: name }));
}

const TEXT_INPUTS = new Set(["text", "search", "email", "number", "tel", "url", "password", "date", "datetime-local", "month", "time", "week"]);

function isTyping(el) {
  if (!el) return false;
  if (el.isContentEditable || el.tagName === "TEXTAREA" || el.tagName === "SELECT") return true;
  return el.tagName === "INPUT" && TEXT_INPUTS.has((el.type || "text").toLowerCase());
}

function normalizePhoneQuery(value) {
  const raw = value.trim();
  if (!/^[\d\s+\-().]+$/.test(raw)) return value;
  let digits = raw.replace(/\D/g, "");
  if (digits.length >= 3 && raw.startsWith("0") && !raw.startsWith("00")) digits = "82" + digits.slice(1);
  return digits || value;
}

document.addEventListener("submit", (e) => {
  const input = e.target.querySelector && e.target.querySelector("[data-search]");
  if (input) input.value = normalizePhoneQuery(input.value);
});

document.addEventListener("keydown", (e) => {
  if (e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey && !isTyping(e.target)) {
    const search = document.querySelector("[data-search]");
    if (search && !document.body.classList.contains("has-modal")) {
      e.preventDefault();
      search.focus();
      search.select();
    }
  } else if (e.key === "Escape" && e.target && e.target.matches && e.target.matches("[data-search]")) {
    e.target.blur();
  }
});

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
