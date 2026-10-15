// Ustawienia (admin): the warehouse day cut-off, the dictionaries (carrier
// groups and types, ...) and the users.

const $ = (id) => document.getElementById(id);

// ordered: has a "Kolejność" (orderMin = lowest allowed); grouped: belongs to a
// carrier group; counted: has the "counted in reports" flag.
const DICTS = {
  "carrier-groups": {
    url: "/carrier-groups",
    title: "Grupy nośników",
    hint: "Grupa łączy typy nośników liczone razem (np. EUR). Grupę z typami można tylko dezaktywować.",
  },
  "carrier-types": {
    url: "/carrier-types",
    title: "Typy nośników",
    hint: "Każdy typ ma własny stan. Raporty liczą tylko typy „w raportach”, pozostałe pokazuje filtr.",
    ordered: true,
    orderMin: 0,
    grouped: true,
    counted: true,
    transplaner: true,
  },
};

// ---------- tabs ----------

function showTab(tab) {
  document.querySelectorAll("#tabs .chip").forEach((c) => c.classList.toggle("on", c.dataset.tab === tab));
  document.querySelectorAll("[data-panel]").forEach((p) => p.classList.add("hidden"));
  if (tab === "day") {
    document.querySelector('[data-panel="day"]').classList.remove("hidden");
    loadDay();
  } else if (tab === "users") {
    document.querySelector('[data-panel="users"]').classList.remove("hidden");
    loadUsers();
  } else if (tab === "reminders") {
    document.querySelector('[data-panel="reminders"]').classList.remove("hidden");
    loadReminders();
  } else if (tab === "holidays") {
    document.querySelector('[data-panel="holidays"]').classList.remove("hidden");
    openHolidays();
  } else {
    document.querySelector('[data-panel="dictionary"]').classList.remove("hidden");
    openDictionary(tab);
  }
}

// ---------- warehouse day ----------

async function loadDay() {
  const s = await api("/settings");
  $("cutoff").value = s.day_cutoff;
  $("day-info").textContent =
    `Bieżąca doba: ${fmtDate(s.current_day)}` +
    (s.last_closed_day ? ` · ostatnia zamknięta: ${fmtDate(s.last_closed_day)}` : "");
}

$("day-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/settings", { method: "PUT", body: { day_cutoff: $("cutoff").value } });
    setMsg($("day-msg"), "Zapisano", "success");
    await loadDay();
  } catch (err) {
    setMsg($("day-msg"), err.message);
  }
});

// ---------- reminders ----------

let reminders = [];
let editedReminder = null; // null = creating
let operationTypes = [];

async function loadReminders() {
  const [status, rows, types] = await Promise.all([
    api("/reminders/status"),
    api("/reminders"),
    operationTypes.length ? Promise.resolve(operationTypes) : api("/movements/types"),
  ]);
  operationTypes = types;
  reminders = rows;
  $("r-check").innerHTML = Object.entries(status.checks)
    .map(([code, label]) => `<option value="${code}">${esc(label)}</option>`)
    .join("");
  $("r-type").innerHTML = operationTypes
    .filter((t) => t.code !== "INVENTORY")
    .map((t) => `<option value="${t.code}">${esc(t.label)}</option>`)
    .join("");
  $("r-status").innerHTML =
    (status.smtp_configured
      ? `<span class="bg ok">Poczta: ${esc(status.sender)}</span>`
      : '<span class="bg wr">Poczta nie jest skonfigurowana (SMTP w .env) — e-maile nie wychodzą</span>') +
    (status.working_day_today
      ? '<span class="bg nu">Dziś dzień roboczy</span>'
      : '<span class="bg nu">Dziś dzień wolny — bez powiadomień</span>');

  $("r-table").innerHTML = rows.length
    ? `<thead><tr><th>Godzina</th><th>Nazwa</th><th>Co sprawdzamy</th><th>Odbiorcy</th>
        <th>Ostatnio wysłano</th><th>Status</th><th></th></tr></thead>
       <tbody>${rows
         .map(
           (r) => `<tr data-uuid="${r.uuid}">
             <td class="strong">${r.deadline}</td>
             <td>${esc(r.name)}</td>
             <td class="mut">${esc(r.description)}</td>
             <td>${r.recipients.length ? r.recipients.map(esc).join("<br>") : '<span class="bg wr">brak odbiorców</span>'}</td>
             <td class="mut">${r.last_sent_on ? fmtDate(r.last_sent_on) : "—"}</td>
             <td>${r.is_active ? '<span class="bg ok">Aktywne</span>' : '<span class="bg nu">Wyłączone</span>'}</td>
             <td class="row" style="justify-content:flex-end">
               <button class="sm r-edit">Zmień</button>
               <button class="sm r-test">Test</button>
               <button class="sm danger r-delete">Usuń</button>
             </td>
           </tr>`
         )
         .join("")}</tbody>`
    : `<tbody><tr><td class="empty">Brak powiadomień</td></tr></tbody>`;

  $("r-table").querySelectorAll("tbody tr[data-uuid]").forEach((tr) => {
    const row = rows.find((r) => r.uuid === tr.dataset.uuid);
    tr.querySelector(".r-edit").onclick = () => openReminder(row);
    tr.querySelector(".r-test").onclick = async () => {
      try {
        await api(`/reminders/${row.uuid}/test`, { method: "POST" });
        setMsg($("r-msg"), `Wysłano wiadomość testową: ${row.recipients.join(", ")}`, "success");
      } catch (err) {
        setMsg($("r-msg"), err.message);
      }
    };
    tr.querySelector(".r-delete").onclick = async () => {
      if (!confirm(`Usunąć powiadomienie „${row.name}”?`)) return;
      try {
        await api(`/reminders/${row.uuid}`, { method: "DELETE" });
        setMsg($("r-msg"), `Usunięto „${row.name}”`, "success");
        await loadReminders();
      } catch (err) {
        setMsg($("r-msg"), err.message);
      }
    };
  });
}

function showTypeField() {
  $("r-type-field").classList.toggle("hidden", $("r-check").value !== "movement");
}

function openReminder(row) {
  editedReminder = row;
  $("r-title").textContent = row ? `Edycja: ${row.name}` : "Nowe powiadomienie";
  $("r-name").value = row ? row.name : "";
  $("r-deadline").value = row ? row.deadline : "12:00";
  $("r-check").value = row ? row.check : "transplaner";
  if (row && row.movement_type) $("r-type").value = row.movement_type;
  $("r-recipients").value = row ? row.recipients.join("\n") : "";
  $("r-active").checked = row ? row.is_active : true;
  showTypeField();
  setMsg($("r-form-msg"), "");
  $("r-dialog").showModal();
}

$("r-check").onchange = showTypeField;
$("r-new").onclick = () => openReminder(null);
$("r-cancel").onclick = () => $("r-dialog").close();
$("r-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    name: $("r-name").value,
    deadline: $("r-deadline").value,
    check: $("r-check").value,
    movement_type: $("r-check").value === "movement" ? $("r-type").value : null,
    recipients: $("r-recipients").value.split(/[\n,;]+/).map((a) => a.trim()).filter(Boolean),
    is_active: $("r-active").checked,
  };
  try {
    if (editedReminder) {
      await api(`/reminders/${editedReminder.uuid}`, { method: "PUT", body });
    } else {
      await api("/reminders", { method: "POST", body });
    }
    $("r-dialog").close();
    setMsg($("r-msg"), "Zapisano", "success");
    await loadReminders();
  } catch (err) {
    setMsg($("r-form-msg"), err.message);
  }
});

// ---------- days off ----------

const WEEKDAYS = ["niedziela", "poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota"];

function openHolidays() {
  const year = new Date().getFullYear();
  if (!$("h-year").options.length) {
    $("h-year").innerHTML = [year - 1, year, year + 1, year + 2]
      .map((y) => `<option value="${y}" ${y === year ? "selected" : ""}>${y}</option>`)
      .join("");
  }
  setMsg($("h-msg"), "");
  loadHolidays();
}

async function loadHolidays() {
  const year = $("h-year").value;
  $("h-public").textContent = `Dodaj święta państwowe ${year}`;
  const days = await api(`/holidays/${year}`);
  $("h-table").innerHTML = days.length
    ? `<thead><tr><th>Dzień</th><th>Dzień tygodnia</th><th>Nazwa</th><th></th></tr></thead>
       <tbody>${days
         .map(
           (h) => `<tr data-uuid="${h.uuid}">
             <td class="strong">${fmtDate(h.day)}</td>
             <td class="mut">${WEEKDAYS[new Date(h.day + "T12:00:00").getDay()]}</td>
             <td>${esc(h.name)}</td>
             <td class="row" style="justify-content:flex-end"><button class="sm danger h-delete">Usuń</button></td>
           </tr>`
         )
         .join("")}</tbody>`
    : `<tbody><tr><td class="empty">Brak dni wolnych w ${year} roku</td></tr></tbody>`;
  $("h-table").querySelectorAll(".h-delete").forEach((button) => {
    const tr = button.closest("tr");
    const day = days.find((h) => h.uuid === tr.dataset.uuid);
    button.onclick = async () => {
      if (!confirm(`Usunąć ${fmtDate(day.day)} (${day.name}) z dni wolnych?`)) return;
      try {
        await api(`/holidays/${day.uuid}`, { method: "DELETE" });
        setMsg($("h-msg"), `Usunięto ${fmtDate(day.day)}`, "success");
        await loadHolidays();
      } catch (err) {
        setMsg($("h-msg"), err.message);
      }
    };
  });
}

$("h-year").onchange = loadHolidays;

$("h-public").onclick = async () => {
  try {
    const added = await api(`/holidays/public/${$("h-year").value}`, { method: "POST" });
    setMsg(
      $("h-msg"),
      added.length ? `Dodano ${added.length} ${plural(added.length, "dzień", "dni", "dni")}` : "Wszystkie święta państwowe są już na liście",
      "success"
    );
    await loadHolidays();
  } catch (err) {
    setMsg($("h-msg"), err.message);
  }
};

$("h-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const day = await api("/holidays", {
      method: "POST",
      body: { day: $("h-day").value, name: $("h-name").value },
    });
    $("h-form").reset();
    $("h-year").value = day.day.slice(0, 4);
    setMsg($("h-msg"), `Dodano ${fmtDate(day.day)}`, "success");
    await loadHolidays();
  } catch (err) {
    setMsg($("h-msg"), err.message);
  }
});

// ---------- dictionaries ----------

let dict = null; // current DICTS entry
let groups = []; // carrier groups, for the types' group select

function groupOptions(selected) {
  return groups
    .filter((g) => g.is_active || g.uuid === selected)
    .map((g) => `<option value="${g.uuid}" ${g.uuid === selected ? "selected" : ""}>${esc(g.name)}</option>`)
    .join("");
}

async function openDictionary(key) {
  dict = DICTS[key];
  $("dict-title").textContent = dict.title;
  $("dict-hint").textContent = dict.hint;
  $("dict-order-field").classList.toggle("hidden", !dict.ordered);
  $("dict-order").min = dict.orderMin ?? "";
  $("dict-group-field").classList.toggle("hidden", !dict.grouped);
  $("dict-group").required = !!dict.grouped;
  $("dict-counted-field").classList.toggle("hidden", !dict.counted);
  $("dict-form").reset();
  setMsg($("dict-msg"), "");
  if (dict.grouped) {
    groups = await api("/carrier-groups");
    $("dict-group").innerHTML = groupOptions(null);
  }
  await loadDictionary();
}

async function loadDictionary() {
  const rows = await api(dict.url);
  const { ordered, grouped, counted, transplaner } = dict;
  $("dict-table").innerHTML = rows.length
    ? `<thead><tr>${grouped ? "<th>Grupa</th>" : ""}<th>Nazwa</th>${ordered ? '<th class="num">Kolejność</th>' : ""}<th>Opis</th>
        ${counted ? "<th>Raporty</th>" : ""}${transplaner ? "<th>Nazwa w Transplanerze</th><th>Jednostka w Saldzie Palet</th>" : ""}<th>Status</th><th></th></tr></thead>
       <tbody>${rows
         .map(
           (r) => `<tr data-uuid="${r.uuid}">
             ${grouped ? `<td>${esc(r.group.name)}</td>` : ""}
             <td class="strong">${esc(r.name)}</td>
             ${ordered ? `<td class="num">${r.sort_order}</td>` : ""}
             <td>${esc(r.description || "")}</td>
             ${counted ? `<td>${r.count_in_reports ? '<span class="bg ok">W raportach</span>' : '<span class="bg nu">Ukryty</span>'}</td>` : ""}
             ${transplaner ? `<td class="mut">${esc(r.transplaner_name || "—")}</td><td class="mut">${esc(r.saldo_palet_unit || "—")}</td>` : ""}
             <td>${r.is_active ? '<span class="bg ok">Aktywny</span>' : '<span class="bg nu">Nieaktywny</span>'}</td>
             <td class="row" style="justify-content:flex-end">
               <button class="sm d-edit">Zmień</button>
               <button class="sm d-toggle">${r.is_active ? "Dezaktywuj" : "Aktywuj"}</button>
               <button class="sm danger d-delete">Usuń</button>
             </td>
           </tr>`
         )
         .join("")}</tbody>`
    : `<tbody><tr><td class="empty">Brak pozycji</td></tr></tbody>`;

  $("dict-table").querySelectorAll("tbody tr[data-uuid]").forEach((tr) => {
    const row = rows.find((r) => r.uuid === tr.dataset.uuid);
    tr.querySelector(".d-edit").onclick = () => editDictionaryRow(tr, row);
    tr.querySelector(".d-toggle").onclick = () => saveDictionaryRow(row, { is_active: !row.is_active });
    tr.querySelector(".d-delete").onclick = async () => {
      if (!confirm(`Usunąć „${row.name}”?`)) return;
      try {
        await api(`${dict.url}/${row.uuid}`, { method: "DELETE" });
        setMsg($("dict-msg"), `Usunięto „${row.name}”`, "success");
        await loadDictionary();
      } catch (err) {
        setMsg($("dict-msg"), err.message);
      }
    };
  });
}

function editDictionaryRow(tr, row) {
  const { ordered, grouped, counted, transplaner } = dict;
  tr.innerHTML = `
    ${grouped ? `<td><select class="e-group">${groupOptions(row.group.uuid)}</select></td>` : ""}
    <td><input class="e-name" value="${esc(row.name)}"></td>
    ${ordered ? `<td class="num"><input class="num-in e-order" type="number" min="${dict.orderMin}" value="${row.sort_order}"></td>` : ""}
    <td><input class="e-description" value="${esc(row.description || "")}"></td>
    ${counted ? `<td><label class="row"><input type="checkbox" class="e-counted" ${row.count_in_reports ? "checked" : ""}> w raportach</label></td>` : ""}
    ${transplaner ? `<td><input class="e-transplaner" value="${esc(row.transplaner_name || "")}" placeholder="np. PAL EUR/ EPAL"></td>
      <td><input class="e-saldo" value="${esc(row.saldo_palet_unit || "")}" placeholder="np. EUR"></td>` : ""}
    <td></td>
    <td class="row" style="justify-content:flex-end">
      <button class="sm pri e-save">Zapisz</button><button class="sm e-cancel">Anuluj</button>
    </td>`;
  tr.querySelector(".e-cancel").onclick = loadDictionary;
  tr.querySelector(".e-save").onclick = () => {
    const changes = {
      name: tr.querySelector(".e-name").value,
      description: tr.querySelector(".e-description").value || null,
    };
    if (ordered) changes.sort_order = parseInt(tr.querySelector(".e-order").value, 10);
    if (grouped) changes.group_uuid = tr.querySelector(".e-group").value;
    if (counted) changes.count_in_reports = tr.querySelector(".e-counted").checked;
    if (transplaner) {
      changes.transplaner_name = tr.querySelector(".e-transplaner").value;
      changes.saldo_palet_unit = tr.querySelector(".e-saldo").value;
    }
    saveDictionaryRow(row, changes);
  };
}

async function saveDictionaryRow(row, changes) {
  try {
    await api(`${dict.url}/${row.uuid}`, { method: "PUT", body: changes });
    setMsg($("dict-msg"), "Zapisano", "success");
    await loadDictionary();
  } catch (err) {
    setMsg($("dict-msg"), err.message);
  }
}

$("dict-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = { name: $("dict-name").value, description: $("dict-description").value || null };
  if (dict.ordered && $("dict-order").value !== "") body.sort_order = parseInt($("dict-order").value, 10);
  if (dict.grouped) body.group_uuid = $("dict-group").value;
  if (dict.counted) body.count_in_reports = $("dict-counted").checked;
  try {
    const row = await api(dict.url, { method: "POST", body });
    $("dict-form").reset();
    if (dict.grouped) $("dict-group").value = body.group_uuid;
    setMsg($("dict-msg"), `Dodano „${row.name}”`, "success");
    await loadDictionary();
  } catch (err) {
    setMsg($("dict-msg"), err.message);
  }
});

// ---------- users ----------

let roles = [];
let lookups = null; // Promise of the roles, reloaded each time the tab opens
let editedUser = null; // null = creating a new user

async function loadUsers() {
  lookups = api("/roles");
  const [users] = await Promise.all([api("/users"), lookups]);
  roles = await lookups;
  $("users-table").innerHTML = `
    <thead><tr><th>Login</th><th>Rola</th><th>Status</th><th></th></tr></thead>
    <tbody>${users
      .map(
        (u) => `<tr data-uuid="${u.uuid}">
          <td class="strong">${esc(u.username)}</td>
          <td>${esc(ROLE_LABELS[u.role] || u.role)}</td>
          <td class="row">
            ${u.is_active ? '<span class="bg ok">Aktywny</span>' : '<span class="bg nu">Nieaktywny</span>'}
            ${u.must_change_password ? '<span class="bg wr">Zmiana hasła</span>' : ""}
          </td>
          <td class="row" style="justify-content:flex-end">
            <button class="sm u-edit">Edytuj</button>
            <button class="sm danger u-delete">Usuń</button>
          </td>
        </tr>`
      )
      .join("")}</tbody>`;

  $("users-table").querySelectorAll("tbody tr").forEach((tr) => {
    const user = users.find((u) => u.uuid === tr.dataset.uuid);
    tr.querySelector(".u-edit").onclick = () => openUser(user);
    tr.querySelector(".u-delete").onclick = async () => {
      if (!confirm(`Usunąć użytkownika „${user.username}”?`)) return;
      try {
        await api(`/users/${user.uuid}`, { method: "DELETE" });
        setMsg($("users-msg"), `Usunięto „${user.username}”`, "success");
        await loadUsers();
      } catch (err) {
        setMsg($("users-msg"), err.message);
      }
    };
  });
}

async function openUser(user) {
  // The roles may still be loading when the button is clicked.
  roles = await lookups;
  editedUser = user;
  const creating = !user;
  $("user-title").textContent = creating ? "Nowy użytkownik" : `Edycja: ${user.username}`;
  $("u-name").value = creating ? "" : user.username;
  $("u-role").innerHTML = roles
    .map((r) => `<option value="${r.name}">${esc(ROLE_LABELS[r.name] || r.name)}</option>`)
    .join("");
  $("u-role").value = creating ? "operator" : user.role;
  $("u-password").value = "";
  $("u-password").required = creating;
  $("u-password-label").textContent = creating ? "Hasło" : "Nowe hasło (puste = bez zmian)";
  // An admin-set password should be replaced by the user.
  $("u-must").checked = creating ? true : user.must_change_password;
  $("u-active").checked = creating ? true : user.is_active;
  $("u-active").closest("label").classList.toggle("hidden", creating);

  setMsg($("user-msg"), "");
  $("user-dialog").showModal();
}

$("user-new").onclick = () => openUser(null);
$("user-cancel").onclick = () => $("user-dialog").close();

$("user-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    username: $("u-name").value,
    role: $("u-role").value,
    must_change_password: $("u-must").checked,
  };
  if ($("u-password").value) body.password = $("u-password").value;
  try {
    if (editedUser) {
      body.is_active = $("u-active").checked;
      await api(`/users/${editedUser.uuid}`, { method: "PUT", body });
    } else {
      await api("/users", { method: "POST", body });
    }
    $("user-dialog").close();
    setMsg($("users-msg"), "Zapisano", "success");
    await loadUsers();
  } catch (err) {
    setMsg($("user-msg"), err.message);
  }
});

// ---------- start ----------

(async () => {
  await App.ready;
  const tabs = [...document.querySelectorAll("#tabs .chip")].filter(
    (c) => !c.classList.contains("hidden")
  );
  if (!tabs.length) {
    document.querySelector(".wrap").innerHTML =
      '<div class="card"><div class="empty">Brak uprawnień do ustawień</div></div>';
    return;
  }
  tabs.forEach((c) => (c.onclick = () => showTab(c.dataset.tab)));
  showTab(tabs[0].dataset.tab);
})();
