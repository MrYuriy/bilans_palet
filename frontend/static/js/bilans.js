// Bilans dzienny: the balance of one warehouse day per area and in total.
// A closed day shows its stored balance (the D-1 report); the open day is a preview.

const $ = (id) => document.getElementById(id);
const COLUMNS = ["opening", "receipts", "shipments", "corrections", "reclassifications", "closing"];
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
  const manyTypes = new Set(data.total.map((r) => r.pallet_type.uuid)).size > 1;
  const label = (r) => esc(pairLabel(r, manyTypes));

  const status = $("status");
  if (data.closed) {
    status.className = "bg ok";
    status.textContent = `Doba zamknięta · ${fmtDateTime(data.closed_at)}`;
  } else {
    status.className = "bg wr";
    status.textContent = "Podgląd — doba otwarta";
  }

  const head = `<thead><tr><th>Obszar / pozycja</th><th class="num">Stan otwarcia</th>
    <th class="num">Przyjęcia</th><th class="num">Wysyłki</th><th class="num">Korekty</th>
    <th class="num">Przeksięgowania</th><th class="num">Stan zamknięcia</th></tr></thead>`;

  const areas = data.areas
    .map((a) => {
      const rows = a.rows.length
        ? a.rows.map((r) => `<tr><td style="padding-left:24px">${label(r)}</td>${rowCells(r)}</tr>`).join("")
        : '<tr><td colspan="7" class="mut" style="padding-left:24px">brak stanu i ruchu</td></tr>';
      return `<tr><td colspan="7" class="strong" style="background:#fafbf9">${esc(a.area.name)}</td></tr>${rows}`;
    })
    .join("");

  const total = data.areas.length > 1 && data.total.length
    ? `<tr><td colspan="7" class="strong" style="background:#eef5f1">Razem</td></tr>` +
      data.total.map((r) => `<tr class="sum"><td style="padding-left:24px">${label(r)}</td>${rowCells(r)}</tr>`).join("")
    : "";

  $("balance").innerHTML = data.areas.length
    ? `${head}<tbody>${areas}${total}</tbody>`
    : '<tbody><tr><td class="empty">Brak obszarów</td></tr></tbody>';

  $("prev-day").disabled = false;
  $("next-day").disabled = data.day >= currentDay;
}

async function load(day) {
  setMsg($("msg"), "");
  try {
    const data = await api("/balances/daily", { query: { day, area_uuid: $("area").value } });
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

  // Operators read only their areas; the others read every area.
  const areas = App.user.role === "operator" ? App.user.areas : await api("/areas");
  $("area").innerHTML += areas.map((a) => `<option value="${a.uuid}">${esc(a.name)}</option>`).join("");

  $("day").onchange = () => $("day").value && load($("day").value);
  $("area").onchange = () => load($("day").value);
  $("prev-day").onclick = () => load(shiftDay($("day").value, -1));
  $("next-day").onclick = () => load(shiftDay($("day").value, 1));
  $("export").onclick = async () => {
    try {
      await download("/balances/daily.xlsx", { day: $("day").value, area_uuid: $("area").value });
    } catch (err) {
      setMsg($("msg"), err.message);
    }
  };

  // No day given: the API answers with the last closed one (D-1).
  await load(undefined);
})();
