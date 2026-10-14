// Shared API helpers used by every page.

function token() {
  return localStorage.getItem("token");
}

function logout() {
  localStorage.removeItem("token");
  location.href = "/";
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
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "") params.append(key, value);
    }
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
  for (const [key, value] of Object.entries(query || {})) {
    if (value !== undefined && value !== null && value !== "") params.append(key, value);
  }
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
