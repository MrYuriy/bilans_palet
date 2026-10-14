// Audyt (admin): who changed what in users, dictionaries and settings.

const PAGE_SIZE = 50;
const state = { offset: 0 };
const $ = (id) => document.getElementById(id);

// Field names stored in the log, as the admin reads them.
const FIELD_LABELS = {
  name: "Nazwa",
  description: "Opis",
  is_active: "Status",
  sort_order: "Kolejność",
  username: "Login",
  role: "Rola",
  must_change_password: "Wymagana zmiana hasła",
  group: "Grupa",
  count_in_reports: "Liczony w raportach",
  areas: "Obszary", // older entries
  password_changed: "Hasło",
  day_cutoff: "Godzina zamknięcia doby",
};

function value(field, v) {
  if (v === null || v === undefined) return "—";
  if (field === "is_active") return v ? "aktywny" : "nieaktywny";
  if (field === "password_changed") return v ? "zmienione" : "—";
  if (field === "role") return ROLE_LABELS[v] || v;
  if (typeof v === "boolean") return v ? "tak" : "nie";
  if (Array.isArray(v)) return v.length ? v.join(", ") : "brak";
  return String(v);
}

function changes(entry) {
  const oldData = entry.old_data || {};
  const newData = entry.new_data || {};
  const fields = [...new Set([...Object.keys(oldData), ...Object.keys(newData)])];
  return fields
    .map((f) => {
      const label = FIELD_LABELS[f] || f;
      if (entry.action === "create") return `${label}: ${esc(value(f, newData[f]))}`;
      if (entry.action === "delete") return `${label}: ${esc(value(f, oldData[f]))}`;
      if (f === "password_changed") return `${label}: zmienione`;
      return `${label}: ${esc(value(f, oldData[f]))} → <span class="strong">${esc(value(f, newData[f]))}</span>`;
    })
    .join("<br>");
}

const ACTION_CLASS = { create: "ok", update: "nu", delete: "er" };

async function load() {
  const table = $("log");
  let page;
  try {
    page = await api("/audit", {
      query: {
        entity: $("f-entity").value,
        user_uuid: $("f-user").value,
        date_from: $("f-from").value,
        date_to: $("f-to").value,
        limit: PAGE_SIZE,
        offset: state.offset,
      },
      withTotal: true,
    });
  } catch (err) {
    table.innerHTML = `<tbody><tr><td class="empty">${esc(err.message)}</td></tr></tbody>`;
    return;
  }

  table.innerHTML = page.data.length
    ? `<thead><tr><th>Czas</th><th>Autor</th><th>Działanie</th><th>Obiekt</th><th>Nazwa</th><th>Zmiany</th></tr></thead>
       <tbody>${page.data
         .map(
           (e) => `<tr>
             <td class="mut" style="white-space:nowrap">${fmtDateTime(e.created_at)}</td>
             <td>${esc(e.username)}${e.user_uuid ? "" : ' <span class="mut">(usunięty)</span>'}</td>
             <td><span class="bg ${ACTION_CLASS[e.action] || "nu"}">${esc(e.action_label)}</span></td>
             <td>${esc(e.entity_label)}</td>
             <td class="strong">${esc(e.entity_name)}</td>
             <td>${changes(e)}</td>
           </tr>`
         )
         .join("")}</tbody>`
    : `<tbody><tr><td class="empty">Brak wpisów dla wybranych filtrów</td></tr></tbody>`;

  const from = page.total ? state.offset + 1 : 0;
  const to = Math.min(state.offset + PAGE_SIZE, page.total);
  $("range").textContent = `${from}–${to} z ${fmt(page.total)}`;
  $("prev").disabled = state.offset === 0;
  $("next").disabled = to >= page.total;
}

(async () => {
  await App.ready;
  if (!App.can("audit")) {
    document.querySelector(".wrap").innerHTML =
      '<div class="card"><div class="empty">Brak uprawnień do audytu</div></div>';
    return;
  }

  const users = await api("/users");
  $("f-user").innerHTML += users
    .map((u) => `<option value="${u.uuid}">${esc(u.username)}</option>`)
    .join("");

  $("filters").addEventListener("submit", (e) => {
    e.preventDefault();
    state.offset = 0;
    load();
  });
  $("f-clear").onclick = () => {
    $("filters").reset();
    state.offset = 0;
    load();
  };
  $("prev").onclick = () => {
    state.offset = Math.max(0, state.offset - PAGE_SIZE);
    load();
  };
  $("next").onclick = () => {
    state.offset += PAGE_SIZE;
    load();
  };
  await load();
})();
