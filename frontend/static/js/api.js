// Shared API helpers used by every page.

function token() {
  return localStorage.getItem("token");
}

function logout() {
  localStorage.removeItem("token");
  location.href = "/";
}

// Adds query values to URLSearchParams; an array repeats the key.
function appendQuery(params, query) {
  for (const [key, value] of Object.entries(query || {})) {
    if (Array.isArray(value)) value.forEach((v) => params.append(key, v));
    else if (value !== undefined && value !== null && value !== "") params.append(key, value);
  }
}

// Calls the API with the stored token. Returns the JSON body; with
// { withTotal: true } returns { data, total } (total from X-Total-Count).
// Throws an Error whose message is the server's Polish "message".
async function api(path, { method = "GET", body, query, withTotal = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token()) headers["Authorization"] = "Bearer " + token();

  let url = path;
  if (query) {
    const params = new URLSearchParams();
    appendQuery(params, query);
    const qs = params.toString();
    if (qs) url += "?" + qs;
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (res.status === 401 && location.pathname !== "/") {
    logout();
    throw new Error("Sesja wygasła");
  }

  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error((data && data.message) || "Błąd serwera");
  }
  if (withTotal) {
    return { data, total: parseInt(res.headers.get("X-Total-Count") || "0", 10) };
  }
  return data;
}

// Escapes text before it goes into innerHTML.
function esc(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// 1234 -> "1 234" (Polish thousands separator).
function fmt(n) {
  return Number(n).toLocaleString("pl-PL");
}

// "2026-10-03" -> "03.10.2026".
function fmtDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}.${m}.${y}`;
}

// "2026-10-03T14:05:12" -> "03.10.2026 14:05".
function fmtDateTime(iso) {
  if (!iso) return "";
  return `${fmtDate(iso)} ${iso.slice(11, 16)}`;
}

function setMsg(el, text, kind = "error") {
  el.className = "msg " + kind;
  el.textContent = text || "";
}

// Polish plural: plural(1, "pozycja", "pozycje", "pozycji") -> "pozycja";
// 2-4 (but not 12-14) take the second form, the rest the third.
function plural(n, one, few, many) {
  if (n === 1) return one;
  const tens = n % 100;
  const units = n % 10;
  if (units >= 2 && units <= 4 && (tens < 12 || tens > 14)) return few;
  return many;
}

function linesSummary(movement) {
  if (!movement.lines.length) return '<span class="mut">bez różnic</span>';
  return movement.lines
    .map((l) => {
      const sign = l.quantity > 0 ? "+" : "";
      const cls = l.quantity < 0 ? "neg" : "pos";
      return `${esc(l.carrier_type.name)} <span class="${cls}">${sign}${fmt(l.quantity)}</span>`;
    })
    .join(", ");
}

// Downloads a file the API serves to signed-in users (a plain link cannot send
// the token). Saves it under the name from Content-Disposition.
async function download(path, query) {
  const params = new URLSearchParams();
  appendQuery(params, query);
  const url = params.toString() ? `${path}?${params}` : path;
  const res = await fetch(url, { headers: { Authorization: "Bearer " + token() } });
  if (res.status === 401) {
    logout();
    throw new Error("Sesja wygasła");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error((data && data.message) || "Błąd serwera");
  }
  const disposition = res.headers.get("Content-Disposition") || "";
  const name = (disposition.match(/filename="([^"]+)"/) || [])[1] || "plik.xlsx";
  const blob = await res.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

// Which carrier types a report shows: by default those counted in reports; the
// viewer may pick others. The choice is remembered in this browser only.
const TypeFilter = {
  KEY: "monolit.report-types",
  types: [],
  picked: null, // Set of carrier type uuids, or null for the default

  async init(container, onChange) {
    this.types = await api("/carrier-types", { query: { active: true } });
    try {
      const saved = JSON.parse(localStorage.getItem(this.KEY) || "null");
      if (Array.isArray(saved)) this.picked = new Set(saved);
    } catch {
      this.picked = null;
    }
    this.container = container;
    this.onChange = onChange;
    this.render();
  },

  isOn(t) {
    return this.picked ? this.picked.has(t.uuid) : t.count_in_reports;
  },

  isDefault() {
    return this.picked === null;
  },

  // The "type" query values, or undefined for the default.
  query() {
    return this.picked ? [...this.picked] : undefined;
  },

  set(picked) {
    const counted = this.types.filter((t) => t.count_in_reports).map((t) => t.uuid);
    const same = picked.size === counted.length && counted.every((u) => picked.has(u));
    this.picked = same ? null : picked;
    try {
      if (this.picked) localStorage.setItem(this.KEY, JSON.stringify([...this.picked]));
      else localStorage.removeItem(this.KEY);
    } catch {
      // Storage may be blocked; the choice then lasts for this page only.
    }
    this.render();
    this.onChange();
  },

  render() {
    this.container.innerHTML =
      '<span class="mut">Typy:</span>' +
      this.types
        .map(
          (t) =>
            `<button type="button" class="chip ${this.isOn(t) ? "on" : ""}" data-uuid="${t.uuid}"
              title="${t.count_in_reports ? "liczony w raportach" : "poza raportami"}">${esc(t.group.name)} · ${esc(t.name)}</button>`
        )
        .join("") +
      (this.isDefault() ? "" : '<button type="button" class="sm" data-reset>Domyślne</button>');
    this.container.querySelectorAll(".chip").forEach((chip) => {
      chip.onclick = () => {
        const picked = new Set(this.types.filter((t) => this.isOn(t)).map((t) => t.uuid));
        if (picked.has(chip.dataset.uuid)) picked.delete(chip.dataset.uuid);
        else picked.add(chip.dataset.uuid);
        this.set(picked);
      };
    });
    const reset = this.container.querySelector("[data-reset]");
    if (reset) {
      reset.onclick = () => {
        this.picked = null;
        try {
          localStorage.removeItem(this.KEY);
        } catch {
          // ignored, see set()
        }
        this.render();
        this.onChange();
      };
    }
  },
};
