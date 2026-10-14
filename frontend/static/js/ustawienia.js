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
  const { ordered, grouped, counted } = dict;
  $("dict-table").innerHTML = rows.length
    ? `<thead><tr>${grouped ? "<th>Grupa</th>" : ""}<th>Nazwa</th>${ordered ? '<th class="num">Kolejność</th>' : ""}<th>Opis</th>
        ${counted ? "<th>Raporty</th>" : ""}<th>Status</th><th></th></tr></thead>
       <tbody>${rows
         .map(
           (r) => `<tr data-uuid="${r.uuid}">
             ${grouped ? `<td>${esc(r.group.name)}</td>` : ""}
             <td class="strong">${esc(r.name)}</td>
             ${ordered ? `<td class="num">${r.sort_order}</td>` : ""}
             <td>${esc(r.description || "")}</td>
             ${counted ? `<td>${r.count_in_reports ? '<span class="bg ok">W raportach</span>' : '<span class="bg nu">Ukryty</span>'}</td>` : ""}
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
  const { ordered, grouped, counted } = dict;
  tr.innerHTML = `
    ${grouped ? `<td><select class="e-group">${groupOptions(row.group.uuid)}</select></td>` : ""}
    <td><input class="e-name" value="${esc(row.name)}"></td>
    ${ordered ? `<td class="num"><input class="num-in e-order" type="number" min="${dict.orderMin}" value="${row.sort_order}"></td>` : ""}
    <td><input class="e-description" value="${esc(row.description || "")}"></td>
    ${counted ? `<td><label class="row"><input type="checkbox" class="e-counted" ${row.count_in_reports ? "checked" : ""}> w raportach</label></td>` : ""}
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
