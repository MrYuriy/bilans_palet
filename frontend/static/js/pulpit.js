// Pulpit: stock now (per carrier group and type), the warehouse day, recent movements.

function renderDay(settings) {
  document.getElementById("day-badge").textContent =
    `Doba robocza: ${fmtDate(settings.current_day)} · zamknięcie o ${settings.day_cutoff}`;
  const closed = document.getElementById("closed-badge");
  if (settings.last_closed_day) {
    closed.textContent = `Ostatnia zamknięta doba: ${fmtDate(settings.last_closed_day)}`;
    closed.classList.remove("hidden");
  }
}

function renderStock(balance) {
  document.getElementById("kpis").innerHTML = balance.groups
    .map(
      (g) => `
      <div class="kpi">
        <span class="lb">${esc(g.group.name)}</span>
        <span class="v">${fmt(g.total)}</span>
        <span class="d">${TypeFilter.isDefault() ? "szt. w raportach" : "szt. · wybrane typy"}</span>
      </div>`
    )
    .join("");

  const rows = balance.groups
    .map((g) => {
      const types = g.rows
        .map(
          (r) => `<tr>
            <td style="padding-left:24px">${esc(r.carrier_type.name)}
              ${r.carrier_type.count_in_reports ? "" : '<span class="bg nu">poza raportami</span>'}</td>
            <td class="num">${fmt(r.quantity)}</td>
          </tr>`
        )
        .join("");
      return `<tr><td colspan="2" class="strong" style="background:#fafbf9">${esc(g.group.name)}</td></tr>
        ${types}
        <tr class="sum"><td style="padding-left:24px">Razem</td><td class="num">${fmt(g.total)}</td></tr>`;
    })
    .join("");

  document.getElementById("stock-table").innerHTML = balance.groups.length
    ? `<thead><tr><th>Grupa / typ nośnika</th><th class="num">Stan</th></tr></thead><tbody>${rows}</tbody>`
    : `<tbody><tr><td class="empty">Nie wybrano typów nośników</td></tr></tbody>`;
}

let historyDays = 30;
let historyPoints = [];

async function loadHistory() {
  const data = await api("/balances/history", {
    query: { days: historyDays, type: TypeFilter.query() },
  });
  historyPoints = data.days;
  columnChart(document.getElementById("history-chart"), historyPoints, "szt.");
  chartTable(document.getElementById("history-table"), historyPoints, "szt.");
}

// The table and the chart follow the same type filter.
async function loadStock() {
  const [balance] = await Promise.all([
    api("/balances/current", { query: { type: TypeFilter.query() } }),
    loadHistory(),
  ]);
  renderStock(balance);
}

document.querySelectorAll("#period .chip").forEach((chip) => {
  chip.onclick = () => {
    historyDays = parseInt(chip.dataset.days, 10);
    document.querySelectorAll("#period .chip").forEach((c) => c.classList.toggle("on", c === chip));
    loadHistory();
  };
});

let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (historyPoints.length) columnChart(document.getElementById("history-chart"), historyPoints, "szt.");
  }, 150);
});

function renderRecent(movements) {
  document.getElementById("recent-table").innerHTML = movements.length
    ? `<thead><tr><th>Data</th><th>Operacja</th><th>Pozycje</th><th>Użytkownik</th></tr></thead>
       <tbody>${movements
         .map(
           (m) => `<tr class="click" data-uuid="${m.uuid}">
             <td class="mut">${fmtDate(m.operation_date)}</td>
             <td class="strong">${esc(m.type_label)}</td>
             <td>${linesSummary(m)}</td>
             <td class="mut">${esc(m.user.username)}</td>
           </tr>`
         )
         .join("")}</tbody>`
    : `<tbody><tr><td class="empty">Brak operacji</td></tr></tbody>`;

  document.querySelectorAll("#recent-table tr.click").forEach((tr) => {
    tr.onclick = () => (location.href = `/app/ruchy?ruch=${tr.dataset.uuid}`);
  });
}

(async () => {
  await App.ready;
  const [settings, recent] = await Promise.all([
    api("/settings"),
    api("/movements", { query: { limit: 8 } }),
    TypeFilter.init(document.getElementById("type-filter"), loadStock),
  ]);
  renderDay(settings);
  renderRecent(recent);
  await loadStock();
})();
