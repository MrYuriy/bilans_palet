// Nowa operacja: operation -> lines (carrier type, quantity). Saved movements
// never change; a mistake is fixed with a correction. Which operations the user
// may enter, their sign and whether a note is required come from the API.

const state = {
  type: null, // the selected operation (from /movements/types)
  carrierTypes: [], // active carrier types, in list order
  stock: {}, // carrier type uuid -> quantity now
};

const $ = (id) => document.getElementById(id);

function hint(op) {
  if (op.code === "RECLASSIFICATION") return "Ilość przechodzi z jednego typu nośnika na inny.";
  if (op.code === "CORRECTION") return "Ilość ze znakiem: dodatnia zwiększa, ujemna zmniejsza stan.";
  const sign = op.sign > 0 ? "zwiększa stan" : "zmniejsza stan";
  return op.counted_types_only ? `Ilość ${sign}. Tylko typy liczone w raportach.` : `Ilość ${sign}.`;
}

// <option>s grouped by carrier group; ``except`` leaves one type out.
function typeOptions(types, except) {
  const groups = new Map();
  for (const t of types) {
    if (t.uuid === except) continue;
    if (!groups.has(t.group.uuid)) groups.set(t.group.uuid, { name: t.group.name, types: [] });
    groups.get(t.group.uuid).types.push(t);
  }
  return [...groups.values()]
    .map(
      (g) => `<optgroup label="${esc(g.name)}">${g.types
        .map((t) => `<option value="${t.uuid}">${esc(t.name)}</option>`)
        .join("")}</optgroup>`
    )
    .join("");
}

function allowedTypes() {
  return state.type.counted_types_only
    ? state.carrierTypes.filter((t) => t.count_in_reports)
    : state.carrierTypes;
}

// ---------- lines ----------

function lineRow() {
  const reclass = state.type.code === "RECLASSIFICATION";
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><select class="l-type">${typeOptions(allowedTypes())}</select></td>
    ${reclass ? '<td><select class="l-to"></select></td>' : ""}
    <td class="num"><input class="num-in l-qty" type="number" step="1"></td>
    <td class="mut l-stock"></td>
    <td><button type="button" class="sm danger l-remove" title="Usuń pozycję">Usuń</button></td>`;

  const refresh = () => {
    const from = tr.querySelector(".l-type").value;
    if (reclass) {
      const to = tr.querySelector(".l-to");
      const kept = to.value;
      to.innerHTML = typeOptions(state.carrierTypes, from);
      if (kept && kept !== from) to.value = kept;
    }
    tr.querySelector(".l-stock").textContent = `stan: ${fmt(state.stock[from] || 0)}`;
  };
  tr.querySelector(".l-type").onchange = refresh;
  tr.querySelector(".l-remove").onclick = () => {
    tr.remove();
    if (!$("lines").querySelector("tbody tr")) addLine();
  };
  tr.refresh = refresh;
  refresh();
  return tr;
}

function addLine() {
  $("lines").querySelector("tbody").appendChild(lineRow());
}

function resetLines() {
  const reclass = state.type.code === "RECLASSIFICATION";
  $("lines").innerHTML = `
    <thead><tr><th>${reclass ? "Z typu" : "Typ nośnika"}</th>
      ${reclass ? "<th>Na typ</th>" : ""}
      <th class="num">${state.type.code === "CORRECTION" ? "Ilość (+/−)" : "Ilość"}</th><th></th><th></th></tr></thead>
    <tbody></tbody>`;
  addLine();
}

function refreshLines() {
  $("lines").querySelectorAll("tbody tr").forEach((tr) => tr.refresh());
}

// ---------- operations ----------

function renderTypes(types) {
  const chips = types.map(
    (t) => `<button type="button" class="chip" data-type="${t.code}">${esc(t.label)}</button>`
  );
  // The file operations and a stock count have their own screens.
  if (App.can("operations")) {
    chips.push('<a class="chip" href="/app/import">Wysyłka / zwroty / Saldo Palet — importy</a>');
  }
  if (App.can("inventory")) chips.push('<a class="chip" href="/app/inwentaryzacja">Inwentaryzacja</a>');
  $("types").innerHTML = chips.join("");
  $("types").querySelectorAll("button.chip").forEach((chip) => {
    chip.onclick = () => selectType(types.find((t) => t.code === chip.dataset.type));
  });
}

function selectType(op) {
  state.type = op;
  $("types").querySelectorAll("button.chip").forEach((c) => c.classList.toggle("on", c.dataset.type === op.code));
  $("lines-title").textContent = op.label;
  $("lines-hint").textContent = hint(op);
  $("comment-label").textContent = op.note_required ? "Notatka (wymagana)" : "Notatka";
  $("comment").placeholder = op.note_required ? "np. powód, odbiorca, nr zlecenia" : "opcjonalnie";
  resetLines();
}

// ---------- saving ----------

function collectLines() {
  return [...$("lines").querySelectorAll("tbody tr")].map((tr) => {
    const line = {
      carrier_type_uuid: tr.querySelector(".l-type").value,
      quantity: parseInt(tr.querySelector(".l-qty").value, 10),
    };
    const to = tr.querySelector(".l-to");
    if (to) line.to_carrier_type_uuid = to.value || null;
    return line;
  });
}

async function save(e) {
  e.preventDefault();
  const msg = $("msg");
  const lines = collectLines();
  if (lines.some((l) => Number.isNaN(l.quantity))) {
    setMsg(msg, "Podaj ilość w każdej pozycji");
    return;
  }
  $("save").disabled = true;
  try {
    const movement = await api("/movements", {
      method: "POST",
      body: {
        type: state.type.code,
        document_number: $("document").value,
        comment: $("comment").value,
        lines,
      },
    });
    msg.className = "msg success";
    msg.innerHTML = `Zapisano: ${esc(movement.type_label)} ·
      <a href="/app/ruchy?ruch=${movement.uuid}">zobacz w rejestrze</a>`;
    $("document").value = "";
    $("comment").value = "";
    await loadStock();
    resetLines();
  } catch (err) {
    setMsg(msg, err.message);
  } finally {
    $("save").disabled = false;
  }
}

async function loadStock() {
  const balance = await api("/balances/current");
  state.stock = {};
  for (const group of balance.groups) {
    for (const r of group.rows) state.stock[r.carrier_type.uuid] = r.quantity;
  }
}

// ---------- start ----------

(async () => {
  await App.ready;
  const [settings, types, carrierTypes] = await Promise.all([
    api("/settings"),
    api("/movements/types"),
    api("/carrier-types", { query: { active: true } }),
  ]);
  const allowed = types.filter((t) => t.can_enter);
  if (!allowed.length) {
    document.querySelector(".wrap").innerHTML = '<div class="card"><div class="empty">Brak uprawnień do wprowadzania operacji</div></div>';
    return;
  }
  state.carrierTypes = carrierTypes;
  $("day").textContent = `Doba robocza: ${fmtDate(settings.current_day)}`;

  await loadStock();
  renderTypes(allowed);
  selectType(allowed[0]);
  $("add-line").onclick = addLine;
  $("movement-form").addEventListener("submit", save);
})();
