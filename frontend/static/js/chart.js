// A column chart of one series (the stock day by day): thin columns from one
// baseline, a tooltip per column on hover and focus, the values also in a table.

const SVG_NS = "http://www.w3.org/2000/svg";

function svgEl(name, attrs) {
  const el = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  return el;
}

// Clean tick step for a range: 1, 2, 5 x 10^n.
function niceStep(range, count) {
  const raw = range / count || 1;
  const power = 10 ** Math.floor(Math.log10(raw));
  const unit = raw / power;
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 5 ? 5 : 10) * power;
}

// A column rounded (4px) at its data end, square at the baseline.
function columnPath(x, width, yBase, yValue) {
  const up = yValue < yBase;
  const height = Math.abs(yBase - yValue);
  const r = Math.min(4, width / 2, height);
  if (height === 0) return "";
  if (up) {
    return `M${x},${yBase} V${yValue + r} Q${x},${yValue} ${x + r},${yValue}
      H${x + width - r} Q${x + width},${yValue} ${x + width},${yValue + r} V${yBase} Z`;
  }
  return `M${x},${yBase} V${yValue - r} Q${x},${yValue} ${x + r},${yValue}
    H${x + width - r} Q${x + width},${yValue} ${x + width},${yValue - r} V${yBase} Z`;
}

// points: [{ day: "2026-10-14", quantity: 123 }]; unit: e.g. "szt."
function columnChart(container, points, unit) {
  container.innerHTML = "";
  container.classList.add("chart");
  const width = Math.max(container.clientWidth, 280);
  const height = 220;
  const m = { top: 12, right: 8, bottom: 26, left: 56 };
  const plotW = width - m.left - m.right;
  const plotH = height - m.top - m.bottom;

  const values = points.map((p) => p.quantity);
  let lo = Math.min(0, ...values);
  let hi = Math.max(0, ...values);
  if (lo === hi) hi = lo + 1;
  const step = niceStep(hi - lo, 4);
  lo = Math.floor(lo / step) * step;
  hi = Math.ceil(hi / step) * step;
  const y = (v) => m.top + plotH - ((v - lo) / (hi - lo)) * plotH;

  const svg = svgEl("svg", {
    width,
    height,
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": "Stan nośników dzień po dniu",
  });

  // Recessive grid and y ticks.
  for (let v = lo; v <= hi + step / 2; v += step) {
    svg.appendChild(
      svgEl("line", {
        x1: m.left,
        x2: width - m.right,
        y1: y(v),
        y2: y(v),
        stroke: v === 0 ? "var(--muted)" : "var(--rule)",
        "stroke-width": 1,
      })
    );
    const tick = svgEl("text", {
      x: m.left - 8,
      y: y(v) + 4,
      "text-anchor": "end",
      "font-size": 11,
      fill: "var(--label)",
    });
    tick.textContent = fmt(v);
    svg.appendChild(tick);
  }

  const band = plotW / points.length;
  const columnW = Math.max(1, Math.min(24, band - 2)); // 2px surface gap
  const labelEvery = Math.ceil(points.length / 8);

  const tip = document.createElement("div");
  tip.className = "chart-tip hidden";
  const tipValue = document.createElement("strong");
  const tipDay = document.createElement("span");
  tip.append(tipValue, tipDay);

  points.forEach((p, i) => {
    const x = m.left + i * band + (band - columnW) / 2;
    const d = columnPath(x, columnW, y(0), y(p.quantity));
    if (d) svg.appendChild(svgEl("path", { d, fill: p.quantity < 0 ? "var(--err-ink)" : "var(--accent)" }));

    // Every n-th day and the last one, unless it would touch its neighbour.
    const lastIndex = points.length - 1;
    const labelled =
      i === lastIndex || (i % labelEvery === 0 && lastIndex - i >= Math.max(labelEvery / 2, 1));
    if (labelled) {
      const label = svgEl("text", {
        x: m.left + i * band + band / 2,
        y: height - 8,
        "text-anchor": "middle",
        "font-size": 11,
        fill: "var(--label)",
      });
      label.textContent = fmtDate(p.day).slice(0, 5);
      svg.appendChild(label);
    }

    // The hit target is the whole band, bigger than the column.
    const hit = svgEl("rect", {
      x: m.left + i * band,
      y: m.top,
      width: band,
      height: plotH,
      fill: "transparent",
      tabindex: 0,
      "aria-label": `${fmtDate(p.day)}: ${fmt(p.quantity)} ${unit}`,
    });
    const show = () => {
      tipValue.textContent = `${fmt(p.quantity)} ${unit}`;
      tipDay.textContent = fmtDate(p.day);
      tip.classList.remove("hidden");
      const left = Math.min(Math.max(m.left + i * band + band / 2, 60), width - 60);
      tip.style.left = `${left}px`;
      tip.style.top = `${Math.max(y(Math.max(p.quantity, 0)) - 8, 0)}px`;
    };
    hit.addEventListener("pointerenter", show);
    hit.addEventListener("focus", show);
    hit.addEventListener("pointerleave", () => tip.classList.add("hidden"));
    hit.addEventListener("blur", () => tip.classList.add("hidden"));
    svg.appendChild(hit);
  });

  container.append(svg, tip);
}

// The same values as a table (the chart's accessible twin).
function chartTable(table, points, unit) {
  table.innerHTML = `<thead><tr><th>Dzień</th><th class="num">Stan (${esc(unit)})</th></tr></thead>
    <tbody>${points
      .slice()
      .reverse()
      .map((p) => `<tr><td>${fmtDate(p.day)}</td><td class="num">${fmt(p.quantity)}</td></tr>`)
      .join("")}</tbody>`;
}
