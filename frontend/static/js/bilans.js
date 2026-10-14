// Bilans dzienny: the balance of one warehouse day per carrier group and type.
// A closed day shows its stored balance (the D-1 report); the open day is a preview.

const $ = (id) => document.getElementById(id);
let currentDay = null; // the open warehouse day: no later day exists yet

function shiftDay(iso, days) {
  const d = new Date(iso + "T12:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function signed(n) {
  if (!n) return '<span class="mut">0</span>';
  return `<span class="${n < 0 ? "neg" : "pos"}">${n > 0 ? "+" : ""}${fmt(n)}</span>`;
}

function rowCells(r) {
  return `
    <td class="num">${fmt(r.opening)}</td>
    <td class="num">${r.receipts ? fmt(r.receipts) : '<span class="mut">0</span>'}</td>
    <td class="num">${r.shipments ? fmt(r.shipments) : '<span class="mut">0</span>'}</td>
    <td class="num">${signed(r.corrections)}</td>
    <td class="num">${signed(r.reclassifications)}</td>
    <td class="num strong">${fmt(r.closing)}</td>`;
}

function render(data) {
  const status = $("status");
  if (data.closed) {
    status.className = "bg ok";
    status.textContent = `Doba zamknięta · ${fmtDateTime(data.closed_at)}`;
  } else {
    status.className = "bg wr";
    status.textContent = "Podgląd — doba otwarta";
  }

  const head = `<thead><tr><th>Grupa / typ nośnika</th><th class="num">Stan otwarcia</th>
    <th class="num">Przyjęcia</th><th class="num">Wydania</th><th class="num">Korekty</th>
    <th class="num">Przeksięgowania</th><th class="num">Stan zamknięcia</th></tr></thead>`;

  const groups = data.groups
    .map((g) => {
      const rows = g.rows
        .map(
          (r) => `<tr><td style="padding-left:24px">${esc(r.carrier_type.name)}
            ${r.carrier_type.count_in_reports ? "" : '<span class="bg nu">poza raportami</span>'}</td>${rowCells(r)}</tr>`
        )
        .join("");
      return `<tr><td colspan="7" class="strong" style="background:#fafbf9">${esc(g.group.name)}</td></tr>
        ${rows}
        <tr class="sum"><td style="padding-left:24px">Razem w raportach</td>${rowCells(g.total)}</tr>`;
    })
    .join("");

  $("balance").innerHTML = data.groups.length
    ? `${head}<tbody>${groups}</tbody>`
    : '<tbody><tr><td class="empty">Brak typów nośników</td></tr></tbody>';

  $("prev-day").disabled = false;
  $("next-day").disabled = data.day >= currentDay;
}

async function load(day) {
  setMsg($("msg"), "");
  try {
    const data = await api("/balances/daily", { query: { day } });
    $("day").value = data.day;
    render(data);
  } catch (err) {
    setMsg($("msg"), err.message);
  }
}

(async () => {
  await App.ready;
  const settings = await api("/settings");
  currentDay = settings.current_day;
  $("day").max = currentDay;

  $("day").onchange = () => $("day").value && load($("day").value);
  $("prev-day").onclick = () => load(shiftDay($("day").value, -1));
  $("next-day").onclick = () => load(shiftDay($("day").value, 1));
  $("export").onclick = async () => {
    try {
      await download("/balances/daily.xlsx", { day: $("day").value });
    } catch (err) {
      setMsg($("msg"), err.message);
    }
  };

  // No day given: the API answers with the last closed one (D-1).
  await load(undefined);
})();
