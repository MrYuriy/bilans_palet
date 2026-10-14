// Inwentaryzacja: count the stock against the system and approve it in one step.
// Only the counted rows change; each becomes exactly what was counted. The first
// count enters the starting stock.

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
  setMsg($("msg"), "");
  sheetRows = await api("/inventories/sheet");

  let group = null;
  $("sheet").innerHTML = `
    <thead><tr><th>Typ nośnika</th><th class="num">Stan systemowy</th>
      <th class="num">Policzono</th><th class="num">Różnica</th><th class="num">%</th></tr></thead>
    <tbody>${sheetRows
      .map((r, i) => {
        const header =
          r.group.uuid === group
            ? ""
            : `<tr><td colspan="5" class="strong" style="background:#fafbf9">${esc(r.group.name)}</td></tr>`;
        group = r.group.uuid;
        return `${header}<tr data-i="${i}">
          <td class="strong" style="padding-left:24px">${esc(r.carrier_type.name)}</td>
          <td class="num">${fmt(r.system_quantity)}</td>
          <td class="num"><input class="num-in c-count" type="number" min="0" step="1"></td>
          <td class="num c-diff"></td>
          <td class="num c-pct mut"></td>
        </tr>`;
      })
      .join("")}</tbody>`;

  $("sheet").querySelectorAll("tbody tr[data-i]").forEach((tr) => {
    const row = sheetRows[tr.dataset.i];
    tr.querySelector(".c-count").oninput = () => differenceCell(tr, row);
  });
}

async function loadHistory() {
  const counts = await api("/movements", { query: { type: "INVENTORY", limit: 10 } });
  $("history").innerHTML = counts.length
    ? `<thead><tr><th>Data</th><th>Różnice</th><th>Nr dokumentu</th><th>Użytkownik</th></tr></thead>
       <tbody>${counts
         .map(
           (m) => `<tr class="click" data-uuid="${m.uuid}">
             <td class="mut">${fmtDate(m.operation_date)}</td>
             <td>${linesSummary(m)}</td>
             <td>${esc(m.document_number || "")}</td>
             <td class="mut">${esc(m.user.username)}</td>
           </tr>`
         )
         .join("")}</tbody>`
    : `<tbody><tr><td class="empty">Brak spisów</td></tr></tbody>`;
  $("history").querySelectorAll("tr.click").forEach((tr) => {
    tr.onclick = () => (location.href = `/app/ruchy?ruch=${tr.dataset.uuid}`);
  });
}

function countedLines() {
  return [...$("sheet").querySelectorAll("tbody tr[data-i]")]
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
    "Zatwierdzić spis?\n" +
    `Policzone pozycje: ${counted.length}, z różnicą: ${differences}.\n` +
    "Stan tych pozycji zostanie ustawiony na policzoną ilość.";
  if (!confirm(question)) return;

  $("save").disabled = true;
  try {
    const movement = await api("/inventories", {
      method: "POST",
      body: {
        document_number: $("document").value,
        comment: $("comment").value,
        lines: counted.map((x) => ({
          carrier_type_uuid: x.row.carrier_type.uuid,
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
  if (!App.can("inventory")) {
    document.querySelector(".wrap").innerHTML =
      '<div class="card"><div class="empty">Brak uprawnień do inwentaryzacji</div></div>';
    return;
  }

  const settings = await api("/settings");
  $("day").textContent = `Spis na dobę: ${fmtDate(settings.current_day)}`;

  $("count-form").addEventListener("submit", approve);
  await loadSheet();
  await loadHistory();
})();
