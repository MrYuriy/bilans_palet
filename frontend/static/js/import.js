// Import z Transplanera: check the file (a preview books nothing), then book
// the chosen operations. Only what changed since earlier uploads is booked.

const $ = (id) => document.getElementById(id);

function chosen() {
  return [...$("kinds").querySelectorAll("input:checked")].map((i) => i.value);
}

function signed(n) {
  if (!n) return '<span class="mut">0</span>';
  return `<span class="${n < 0 ? "neg" : "pos"}">${n > 0 ? "+" : ""}${fmt(n)}</span>`;
}

// Uploads the file with fetch: api() sends JSON only.
async function upload(path, extra) {
  const file = $("file").files[0];
  if (!file) throw new Error("Wybierz plik");
  const form = new FormData();
  form.append("file", file);
  for (const type of extra || []) form.append("type", type);
  const res = await fetch(path, {
    method: "POST",
    headers: { Authorization: "Bearer " + token() },
    body: form,
  });
  if (res.status === 401) {
    logout();
    throw new Error("Sesja wygasła");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error((data && data.message) || "Błąd serwera");
  return data;
}

function renderPreview(p) {
  $("preview-card").classList.remove("hidden");
  $("preview-title").textContent = `Podgląd: ${p.carrier} → ${p.carrier_type.name}`;
  $("preview-sub").textContent =
    `miesiąc ${p.month.slice(5, 7)}.${p.month.slice(0, 4)} · ${p.recipients} ` +
    `${plural(p.recipients, "odbiorca", "odbiorców", "odbiorców")}` +
    (p.last_day ? ` · dane do ${fmtDate(p.last_day)}` : "");

  $("warnings").innerHTML = p.warnings
    .map((w) => `<div class="bg wr" style="align-self:flex-start">${esc(w)}</div>`)
    .join("");

  const picked = new Set(chosen());
  $("preview").innerHTML = `
    <thead><tr><th>Operacja</th><th class="num">W pliku (miesiąc)</th>
      <th class="num">Zaksięgowano wcześniej</th><th class="num">Zmiana stanu teraz</th>
      <th>Dni ze zmianą</th></tr></thead>
    <tbody>${p.kinds
      .map(
        (k) => `<tr class="${picked.has(k.type) ? "" : "mut"}">
          <td class="strong">${esc(k.label)}${picked.has(k.type) ? "" : ' <span class="bg nu">pominięta</span>'}</td>
          <td class="num">${fmt(k.in_file)}</td>
          <td class="num">${fmt(k.booked)}</td>
          <td class="num strong">${signed(k.change)}</td>
          <td class="mut">${k.days.length
            ? k.days.slice(0, 8).map((d) => `${fmtDate(d.day).slice(0, 5)}: ${fmt(d.booked)} → ${fmt(d.in_file)}`).join(", ") +
              (k.days.length > 8 ? ` … (+${k.days.length - 8})` : "")
            : "bez zmian"}</td>
        </tr>`
      )
      .join("")}</tbody>`;
  const anything = p.kinds.some((k) => picked.has(k.type) && k.change);
  $("book").textContent = anything ? "Zaksięguj" : "Zapisz wgranie (bez zmian stanu)";
}

async function loadHistory() {
  const rows = await api("/imports/transplaner", { query: { limit: 10 } });
  $("history").innerHTML = rows.length
    ? `<thead><tr><th>Wgrano</th><th>Plik</th><th>Miesiąc</th><th>Zmiany</th><th>Użytkownik</th></tr></thead>
       <tbody>${rows
         .map((r) => {
           const s = r.summary || { kinds: {} };
           const changes = Object.values(s.kinds)
             .filter((k) => k.change)
             .map((k) => `${esc(k.label)} ${signed(k.change)}`)
             .join(", ");
           return `<tr>
             <td class="mut">${fmtDateTime(r.created_at)}</td>
             <td>${esc(r.file_name || "")}</td>
             <td>${esc(s.month || "")}</td>
             <td>${changes || '<span class="mut">bez zmian</span>'}</td>
             <td class="mut">${esc(r.user.username)}</td>
           </tr>`;
         })
         .join("")}</tbody>`
    : `<tbody><tr><td class="empty">Jeszcze nic nie wgrano</td></tr></tbody>`;
}

async function check() {
  setMsg($("msg"), "");
  setMsg($("book-msg"), "");
  $("preview-card").classList.add("hidden");
  try {
    renderPreview(await upload("/imports/transplaner/preview"));
  } catch (err) {
    setMsg($("msg"), err.message);
  }
}

(async () => {
  await App.ready;
  if (!App.can("operations")) {
    document.querySelector(".wrap").innerHTML =
      '<div class="card"><div class="empty">Brak uprawnień do importu</div></div>';
    return;
  }
  const settings = await api("/settings");
  $("day").textContent = `Księgowanie na dobę: ${fmtDate(settings.current_day)}`;

  $("kinds").querySelectorAll("label.chip").forEach((chip) => {
    chip.querySelector("input").onchange = (e) => {
      chip.classList.toggle("on", e.target.checked);
      if (!$("preview-card").classList.contains("hidden")) check();
    };
  });
  $("file").onchange = check;
  $("check").onclick = check;
  $("book").onclick = async () => {
    $("book").disabled = true;
    try {
      const result = await upload("/imports/transplaner", chosen());
      const changes = Object.values(result.summary.kinds).filter((k) => k.change);
      $("preview-card").classList.add("hidden");
      $("file").value = "";
      $("msg").className = "msg success";
      $("msg").innerHTML = changes.length
        ? `Zaksięgowano: ${changes.map((k) => `${esc(k.label)} ${signed(k.change)}`).join(", ")} ·
           <a href="/app/ruchy">zobacz w rejestrze</a>`
        : "Wgranie zapisane — bez zmian stanu.";
      await loadHistory();
    } catch (err) {
      setMsg($("book-msg"), err.message);
    } finally {
      $("book").disabled = false;
    }
  };
  await loadHistory();
})();
