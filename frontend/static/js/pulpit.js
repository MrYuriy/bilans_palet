// Pulpit: stock now (per quality and per area), the warehouse day, recent movements.

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
  const manyTypes = new Set(balance.total.map((r) => r.pallet_type.uuid)).size > 1;
  const areaCount = balance.areas.length;

  document.getElementById("kpis").innerHTML = balance.total
    .map(
      (r) => `
      <div class="kpi">
        <span class="lb">${esc(pairLabel(r, manyTypes))}</span>
        <span class="v">${fmt(r.quantity)}</span>
        <span class="d">szt. łącznie${areaCount > 1 ? ` · ${areaCount} ${plural(areaCount, "obszar", "obszary", "obszarów")}` : ""}</span>
      </div>`
    )
    .join("");

  const pairs = balance.total.map((r) => `${r.pallet_type.uuid}|${r.quality.uuid}`);
  const head = balance.total.map((r) => `<th class="num">${esc(pairLabel(r, manyTypes))}</th>`).join("");
  const body = balance.areas
    .map((a) => {
      const byPair = Object.fromEntries(
        a.rows.map((r) => [`${r.pallet_type.uuid}|${r.quality.uuid}`, r.quantity])
      );
      const cells = pairs.map((p) => `<td class="num">${fmt(byPair[p] || 0)}</td>`).join("");
      return `<tr><td class="strong">${esc(a.area.name)}</td>${cells}</tr>`;
    })
    .join("");
  const total = balance.total.map((r) => `<td class="num">${fmt(r.quantity)}</td>`).join("");

  document.getElementById("areas-table").innerHTML = areaCount
    ? `<thead><tr><th>Obszar</th>${head}</tr></thead>
       <tbody>${body}</tbody>
       ${areaCount > 1 ? `<tfoot><tr class="sum"><td>Razem</td>${total}</tr></tfoot>` : ""}`
    : `<tbody><tr><td class="empty">Brak obszarów</td></tr></tbody>`;

  return manyTypes;
}

function renderRecent(movements, manyTypes) {
  document.getElementById("recent-table").innerHTML = movements.length
    ? `<thead><tr><th>Data</th><th>Operacja</th><th>Obszar</th><th>Pozycje</th><th>Użytkownik</th></tr></thead>
       <tbody>${movements
         .map(
           (m) => `<tr class="click" data-uuid="${m.uuid}">
             <td class="mut">${fmtDate(m.operation_date)}</td>
             <td class="strong">${esc(m.type_label)}</td>
             <td>${esc(m.area.name)}</td>
             <td>${linesSummary(m, manyTypes)}</td>
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
  const [settings, balance, recent] = await Promise.all([
    api("/settings"),
    api("/balances/current"),
    api("/movements", { query: { limit: 8 } }),
  ]);
  renderDay(settings);
  const manyTypes = renderStock(balance);
  renderRecent(recent, manyTypes);
})();
