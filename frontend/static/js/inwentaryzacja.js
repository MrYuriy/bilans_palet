// Inwentaryzacja: count an area against the system stock and approve it in one
// step. Only the counted rows change; each becomes exactly what was counted.

const $ = (id) => document.getElementById(id);
let sheetRows = [];

function differenceCell(tr, row) {
  const raw = tr.querySelector(".c-count").value;
  const diffCell = tr.querySelector(".c-diff");
  const pctCell = tr.querySelector(".c-pct");
  if (raw === "") {
    diffCell.textContent = "";
    pctCell.textContent = "";
    diffCell.className = "num c-diff";
    return;
  }
  const diff = parseInt(raw, 10) - row.system_quantity;
  diffCell.textContent = (diff > 0 ? "+" : "") + fmt(diff);
  diffCell.className = "num c-diff " + (diff < 0 ? "neg" : diff > 0 ? "pos" : "mut");
  pctCell.textContent = row.system_quantity
    ? `${diff > 0 ? "+" : ""}${((diff / row.system_quantity) * 100).toFixed(1).replace(".", ",")}%`
    : "—";
}

async function loadSheet() {
  const area = $("area").value;
  if (!area) return;
  setMsg($("msg"), "");
  sheetRows = await api("/inventories/sheet", { query: { area_uuid: area } });
  $("sheet-sub").textContent = $("area").selectedOptions[0].text;

  $("sheet").innerHTML = `
    <thead><tr><th>Typ palety</th><th>Jakość</th><th class="num">Stan systemowy</th>
      <th class="num">Policzono</th><th class="num">Różnica</th><th class="num">%</th></tr></thead>
    <tbody>${sheetRows
      .map(
        (r, i) => `<tr data-i="${i}">
          <td class="strong">${esc(r.pallet_type.name)}</td>
          <td>${esc(r.quality.name)}</td>
          <td class="num">${fmt(r.system_quantity)}</td>
          <td class="num"><input class="num-in c-count" type="number" min="0" step="1"></td>
          <td class="num c-diff"></td>
          <td class="num c-pct mut"></td>
        </tr>`
      )
      .join("")}</tbody>`;

  $("sheet").querySelectorAll("tbody tr").forEach((tr) => {
    const row = sheetRows[tr.dataset.i];
    tr.querySelector(".c-count").oninput = () => differenceCell(tr, row);
  });
}

async function loadHistory() {
  const area = $("area").value;
  const counts = await api("/movements", {
    query: { type: "INVENTORY", area_uuid: area, limit: 10 },
  });
  $("history").innerHTML = counts.length
    ? `<thead><tr><th>Data</th><th>Obszar</th><th>Różnice</th><th>Nr dokumentu</th><th>Użytkownik</th></tr></thead>
       <tbody>${counts
         .map(
           (m) => `<tr class="click" data-uuid="${m.uuid}">
             <td class="mut">${fmtDate(m.operation_date)}</td>
             <td>${esc(m.area.name)}</td>
             <td>${linesSummary(m, false)}</td>
             <td>${esc(m.document_number || "")}</td>
             <td class="mut">${esc(m.user.username)}</td>
           </tr>`
         )
         .join("")}</tbody>`
    : `<tbody><tr><td class="empty">Brak spisów w tym obszarze</td></tr></tbody>`;
  $("history").querySelectorAll("tr.click").forEach((tr) => {
    tr.onclick = () => (location.href = `/app/ruchy?ruch=${tr.dataset.uuid}`);
  });
}

function countedLines() {
  return [...$("sheet").querySelectorAll("tbody tr")]
    .map((tr) => ({ tr, row: sheetRows[tr.dataset.i], raw: tr.querySelector(".c-count").value }))
    .filter((x) => x.raw !== "")
    .map((x) => ({ ...x, counted: parseInt(x.raw, 10) }));
}

async function approve(e) {
  e.preventDefault();
  const msg = $("msg");
  const counted = countedLines();
  if (!counted.length) {
    setMsg(msg, "Wpisz policzoną ilość przynajmniej w jednej pozycji");
    return;
  }
  if (counted.some((x) => Number.isNaN(x.counted) || x.counted < 0)) {
    setMsg(msg, "Policzona ilość musi być liczbą nieujemną");
    return;
  }
  const differences = counted.filter((x) => x.counted !== x.row.system_quantity).length;
  const question =
    `Zatwierdzić spis obszaru „${$("area").selectedOptions[0].text}”?\n` +
    `Policzone pozycje: ${counted.length}, z różnicą: ${differences}.\n` +
    "Stan tych pozycji zostanie ustawiony na policzoną ilość.";
  if (!confirm(question)) return;

  $("save").disabled = true;
  try {
    const movement = await api("/inventories", {
      method: "POST",
      body: {
        area_uuid: $("area").value,
        document_number: $("document").value,
        comment: $("comment").value,
        lines: counted.map((x) => ({
          pallet_type_uuid: x.row.pallet_type.uuid,
          quality_uuid: x.row.quality.uuid,
          counted_quantity: x.counted,
        })),
      },
    });
    $("document").value = "";
    $("comment").value = "";
    await loadSheet();
    await loadHistory();
    msg.className = "msg success";
    msg.innerHTML = `Spis zatwierdzony (${differences} ${plural(differences, "różnica", "różnice", "różnic")}) ·
      <a href="/app/ruchy?ruch=${movement.uuid}">zobacz w rejestrze</a>`;
  } catch (err) {
    setMsg(msg, err.message);
  } finally {
    $("save").disabled = false;
  }
}

(async () => {
  await App.ready;
  if (!App.can("movements")) {
    document.querySelector(".wrap").innerHTML =
      '<div class="card"><div class="empty">Brak uprawnień do inwentaryzacji</div></div>';
    return;
  }

  const [settings, allAreas] = await Promise.all([
    api("/settings"),
    App.user.role === "admin" ? api("/areas", { query: { active: true } }) : Promise.resolve(null),
  ]);
  $("day").textContent = `Spis na dobę: ${fmtDate(settings.current_day)}`;

  const areas = allAreas || App.user.areas;
  $("area").innerHTML = areas
    .map((a) => `<option value="${a.uuid}">${esc(a.name)}</option>`)
    .join("");
  if (areas.length === 1) {
    $("area-field").classList.add("hidden");
    $("area-fixed").textContent = `Obszar: ${areas[0].name}`;
    $("area-fixed").classList.remove("hidden");
  } else if (!areas.length) {
    setMsg($("msg"), "Nie masz przypisanego obszaru — skontaktuj się z administratorem");
    $("save").disabled = true;
    return;
  }

  $("area").onchange = async () => {
    await loadSheet();
    await loadHistory();
  };
  $("count-form").addEventListener("submit", approve);
  await loadSheet();
  await loadHistory();
})();
