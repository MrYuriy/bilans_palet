// Nowa operacja: area -> movement type -> lines. Saved movements never change;
// a mistake is fixed with a correction.

const TYPE_HINTS = {
  RECEIPT: "Ilość przyjętych palet.",
  LM_PURCHASE: "Dostawa od Leroy Merlin — liczona jak przyjęcie.",
  SHIPMENT: "Ilość wysłanych palet.",
  CORRECTION: "Ilość ze znakiem: dodatnia zwiększa, ujemna zmniejsza stan.",
  RECLASSIFICATION: "Palety przechodzą do gorszej jakości.",
};

const state = {
  type: "RECEIPT",
  palletTypes: [],
  qualities: [],
  stock: {}, // "area|type|quality" -> quantity
};

const $ = (id) => document.getElementById(id);

function areaUuid() {
  return $("area").value;
}

function available(typeUuid, qualityUuid) {
  return state.stock[`${areaUuid()}|${typeUuid}|${qualityUuid}`] || 0;
}

function options(rows, selected) {
  return rows
    .map((r) => `<option value="${r.uuid}" ${r.uuid === selected ? "selected" : ""}>${esc(r.name)}</option>`)
    .join("");
}

// ---------- lines ----------

function lineRow() {
  const reclass = state.type === "RECLASSIFICATION";
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><select class="l-type">${options(state.palletTypes)}</select></td>
    <td><select class="l-quality">${options(state.qualities)}</select></td>
    ${reclass ? '<td><select class="l-to"></select></td>' : ""}
    <td class="num"><input class="num-in l-qty" type="number" step="1"></td>
    <td class="mut l-avail"></td>
    <td><button type="button" class="sm danger l-remove" title="Usuń pozycję">Usuń</button></td>`;

  const refresh = () => {
    if (reclass) {
      // Only a worse quality (higher sort order) can be the target.
      const from = state.qualities.find((q) => q.uuid === tr.querySelector(".l-quality").value);
      const worse = state.qualities.filter((q) => from && q.sort_order > from.sort_order);
      const to = tr.querySelector(".l-to");
      to.innerHTML = worse.length ? options(worse) : '<option value="">brak gorszej jakości</option>';
    }
    const takesAway = ["SHIPMENT", "RECLASSIFICATION", "CORRECTION"].includes(state.type);
    tr.querySelector(".l-avail").textContent = takesAway
      ? `dostępne: ${fmt(available(tr.querySelector(".l-type").value, tr.querySelector(".l-quality").value))}`
      : "";
  };
  tr.querySelector(".l-type").onchange = refresh;
  tr.querySelector(".l-quality").onchange = refresh;
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
  const reclass = state.type === "RECLASSIFICATION";
  $("lines").innerHTML = `
    <thead><tr><th>Typ palety</th><th>${reclass ? "Z jakości" : "Jakość"}</th>
      ${reclass ? "<th>Do jakości</th>" : ""}
      <th class="num">${state.type === "CORRECTION" ? "Ilość (+/−)" : "Ilość"}</th><th></th><th></th></tr></thead>
    <tbody></tbody>`;
  addLine();
}

function refreshLines() {
  $("lines").querySelectorAll("tbody tr").forEach((tr) => tr.refresh());
}

// ---------- types ----------

function renderTypes(types) {
  const chips = types
    .filter((t) => t.code !== "INVENTORY")
    .map((t) => `<button type="button" class="chip" data-type="${t.code}">${esc(t.label)}</button>`);
  // A stock count has its own sheet.
  chips.push('<a class="chip" href="/app/inwentaryzacja">Inwentaryzacja</a>');
  $("types").innerHTML = chips.join("");
  $("types").querySelectorAll("button.chip").forEach((chip) => {
    chip.onclick = () => selectType(chip.dataset.type, chip.textContent);
  });
}

function selectType(code, label) {
  state.type = code;
  $("types").querySelectorAll("button.chip").forEach((c) => c.classList.toggle("on", c.dataset.type === code));
  $("lines-title").textContent = label || "Pozycje";
  $("lines-hint").textContent = TYPE_HINTS[code] || "";
  const correction = code === "CORRECTION";
  $("comment-label").textContent = correction ? "Komentarz (powód korekty — wymagany)" : "Komentarz";
  $("comment").placeholder = correction ? "np. uszkodzenie przy rozładunku" : "opcjonalnie";
  resetLines();
}

// ---------- saving ----------

function collectLines() {
  return [...$("lines").querySelectorAll("tbody tr")].map((tr) => {
    const line = {
      pallet_type_uuid: tr.querySelector(".l-type").value,
      quality_uuid: tr.querySelector(".l-quality").value,
      quantity: parseInt(tr.querySelector(".l-qty").value, 10),
    };
    const to = tr.querySelector(".l-to");
    if (to) line.to_quality_uuid = to.value || null;
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
        type: state.type,
        area_uuid: areaUuid() || null,
        document_number: $("document").value,
        comment: $("comment").value,
        lines,
      },
    });
    msg.className = "msg success";
    msg.innerHTML = `Zapisano: ${esc(movement.type_label)} · ${esc(movement.area.name)} ·
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
  for (const area of balance.areas) {
    for (const r of area.rows) {
      state.stock[`${area.area.uuid}|${r.pallet_type.uuid}|${r.quality.uuid}`] = r.quantity;
    }
  }
}

// ---------- start ----------

(async () => {
  await App.ready;
  if (!App.can("movements")) {
    document.querySelector(".wrap").innerHTML = '<div class="card"><div class="empty">Brak uprawnień do wprowadzania operacji</div></div>';
    return;
  }

  const [settings, types, palletTypes, qualities, allAreas] = await Promise.all([
    api("/settings"),
    api("/movements/types"),
    api("/pallet-types", { query: { active: true } }),
    api("/qualities", { query: { active: true } }),
    App.user.role === "admin" ? api("/areas", { query: { active: true } }) : Promise.resolve(null),
  ]);
  state.palletTypes = palletTypes;
  state.qualities = qualities;
  $("day").textContent = `Doba robocza: ${fmtDate(settings.current_day)}`;

  // The admin works in any area; everyone else in their assigned ones.
  const areas = allAreas || App.user.areas;
  $("area").innerHTML = options(areas);
  if (areas.length === 1) {
    $("area-field").classList.add("hidden");
    $("area-fixed").textContent = `Obszar: ${areas[0].name}`;
    $("area-fixed").classList.remove("hidden");
  } else if (!areas.length) {
    setMsg($("msg"), "Nie masz przypisanego obszaru — skontaktuj się z administratorem");
    $("save").disabled = true;
  }
  $("area").onchange = refreshLines;

  await loadStock();
  renderTypes(types);
  selectType("RECEIPT", types.find((t) => t.code === "RECEIPT").label);
  $("add-line").onclick = addLine;
  $("movement-form").addEventListener("submit", save);
})();
