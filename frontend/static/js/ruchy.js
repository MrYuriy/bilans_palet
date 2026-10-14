// Rejestr operacji: every movement, filtered and paged, with its details.

const PAGE_SIZE = 50;
const state = { offset: 0, total: 0 };

function filters() {
  return {
    date_from: document.getElementById("f-from").value,
    date_to: document.getElementById("f-to").value,
    type: document.getElementById("f-type").value,
    carrier_type_uuid: document.getElementById("f-carrier").value,
  };
}

async function fillFilters() {
  const [types, carriers] = await Promise.all([
    api("/movements/types"),
    api("/carrier-types"),
  ]);

  document.getElementById("f-type").innerHTML += types
    .map((t) => `<option value="${t.code}">${esc(t.label)}</option>`)
    .join("");
  document.getElementById("f-carrier").innerHTML += carriers
    .map((t) => `<option value="${t.uuid}">${esc(t.group.name)} · ${esc(t.name)}</option>`)
    .join("");
}

async function load() {
  const table = document.getElementById("movements");
  let page;
  try {
    page = await api("/movements", {
      query: { ...filters(), limit: PAGE_SIZE, offset: state.offset },
      withTotal: true,
    });
  } catch (err) {
    table.innerHTML = `<tbody><tr><td class="empty">${esc(err.message)}</td></tr></tbody>`;
    return;
  }
  state.total = page.total;

  table.innerHTML = page.data.length
    ? `<thead><tr><th>Data</th><th>Operacja</th><th>Pozycje</th>
         <th>Nr dokumentu</th><th>Użytkownik</th><th>Wprowadzono</th></tr></thead>
       <tbody>${page.data
         .map(
           (m) => `<tr class="click" data-uuid="${m.uuid}">
             <td class="mut">${fmtDate(m.operation_date)}</td>
             <td class="strong">${esc(m.type_label)}</td>
             <td>${linesSummary(m)}</td>
             <td>${esc(m.document_number || "")}</td>
             <td class="mut">${esc(m.user.username)}</td>
             <td class="mut">${fmtDateTime(m.created_at)}</td>
           </tr>`
         )
         .join("")}</tbody>`
    : `<tbody><tr><td class="empty">Brak operacji dla wybranych filtrów</td></tr></tbody>`;

  table.querySelectorAll("tr.click").forEach((tr) => {
    tr.onclick = () => openDetail(tr.dataset.uuid);
  });

  const from = page.total ? state.offset + 1 : 0;
  const to = Math.min(state.offset + PAGE_SIZE, page.total);
  document.getElementById("range").textContent = `${from}–${to} z ${fmt(page.total)}`;
  document.getElementById("prev").disabled = state.offset === 0;
  document.getElementById("next").disabled = to >= page.total;
}

function field(label, value) {
  return `<div class="field-view"><span class="k">${label}</span><span class="v">${value || "—"}</span></div>`;
}

async function openDetail(uuid) {
  let m;
  try {
    m = await api(`/movements/${uuid}`);
  } catch (err) {
    alert(err.message);
    return;
  }
  document.getElementById("d-title").textContent = m.type_label;
  document.getElementById("d-fields").innerHTML = [
    field("Data operacji", fmtDate(m.operation_date)),
    field("Użytkownik", esc(m.user.username)),
    field("Nr dokumentu", esc(m.document_number || "")),
    field("Wprowadzono", fmtDateTime(m.created_at)),
    field("Komentarz", esc(m.comment || "")),
  ].join("");

  document.getElementById("d-lines").innerHTML = m.lines.length
    ? `<thead><tr><th>Typ nośnika</th><th class="num">Zmiana stanu</th></tr></thead>
       <tbody>${m.lines
         .map(
           (l) => `<tr><td>${esc(l.carrier_type.name)}</td>
             <td class="num ${l.quantity < 0 ? "neg" : "pos"}">${l.quantity > 0 ? "+" : ""}${fmt(l.quantity)}</td></tr>`
         )
         .join("")}</tbody>`
    : `<tbody><tr><td class="empty">Spis zgodny ze stanem — bez zmian</td></tr></tbody>`;

  const sheetWrap = document.getElementById("d-sheet-wrap");
  sheetWrap.classList.toggle("hidden", !m.inventory_lines);
  if (m.inventory_lines) {
    document.getElementById("d-sheet").innerHTML = `
      <thead><tr><th>Typ nośnika</th><th class="num">Stan systemowy</th>
        <th class="num">Policzono</th><th class="num">Różnica</th></tr></thead>
      <tbody>${m.inventory_lines
        .map(
          (r) => `<tr><td>${esc(r.carrier_type.name)}</td>
            <td class="num">${fmt(r.system_quantity)}</td><td class="num">${fmt(r.counted_quantity)}</td>
            <td class="num ${r.difference < 0 ? "neg" : r.difference > 0 ? "pos" : "mut"}">${r.difference > 0 ? "+" : ""}${fmt(r.difference)}</td></tr>`
        )
        .join("")}</tbody>`;
  }
  document.getElementById("detail").showModal();
}

(async () => {
  await App.ready;
  await fillFilters();

  document.getElementById("filters").addEventListener("submit", (e) => {
    e.preventDefault();
    state.offset = 0;
    load();
  });
  document.getElementById("f-clear").onclick = () => {
    document.getElementById("filters").reset();
    state.offset = 0;
    load();
  };
  document.getElementById("prev").onclick = () => {
    state.offset = Math.max(0, state.offset - PAGE_SIZE);
    load();
  };
  document.getElementById("next").onclick = () => {
    state.offset += PAGE_SIZE;
    load();
  };
  document.getElementById("f-export").onclick = async () => {
    setMsg(document.getElementById("export-msg"), "");
    try {
      await download("/movements/export.xlsx", filters());
    } catch (err) {
      setMsg(document.getElementById("export-msg"), err.message);
    }
  };
  document.getElementById("d-close").onclick = () => document.getElementById("detail").close();

  await load();

  // /app/ruchy?ruch=<uuid> opens one movement (links from the dashboard).
  const wanted = new URLSearchParams(location.search).get("ruch");
  if (wanted) openDetail(wanted);
})();
