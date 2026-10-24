(function () {
  const NS = "http://www.w3.org/2000/svg";
  const C = {
    ink: "#d4d4d8", muted: "#71717a", green: "#4ade80", amber: "#fbbf24",
    red: "#f87171", blue: "#60a5fa", violet: "#a78bfa", white: "#fafafa",
  };
  const tint = (hex, a) => {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`;
  };

  function make(svg) {
    const rc = window.rough ? window.rough.svg(svg) : null;
    let seed = 1;
    const add = (n) => (svg.appendChild(n), n);
    const el = (tag, attrs) => {
      const n = document.createElementNS(NS, tag);
      Object.entries(attrs).forEach(([k, v]) => v !== undefined && n.setAttribute(k, v));
      return n;
    };
    const opts = (o = {}) => ({
      roughness: o.roughness ?? 1.3, bowing: 1.2, seed: seed++,
      stroke: o.color || C.ink, strokeWidth: o.sw || 1.5,
      fill: o.fill, fillStyle: o.fillStyle || "hachure", hachureGap: o.gap || 6,
      fillWeight: 0.7, hachureAngle: -41, strokeLineDash: o.dash,
    });

    const api = {
      C, tint,
      rect(x, y, w, h, o = {}) {
        if (rc) return add(rc.rectangle(x, y, w, h, opts(o)));
        return add(el("rect", { x, y, width: w, height: h, rx: 8, fill: o.fill || "none", stroke: o.color || C.ink, "stroke-dasharray": o.dash && o.dash.join(" ") }));
      },
      ellipse(cx, cy, w, h, o = {}) {
        if (rc) return add(rc.ellipse(cx, cy, w, h, opts(o)));
        return add(el("ellipse", { cx, cy, rx: w / 2, ry: h / 2, fill: o.fill || "none", stroke: o.color || C.ink }));
      },
      line(x1, y1, x2, y2, o = {}) {
        if (rc) return add(rc.line(x1, y1, x2, y2, opts(o)));
        return add(el("line", { x1, y1, x2, y2, stroke: o.color || C.ink, "stroke-dasharray": o.dash && o.dash.join(" ") }));
      },
      curve(points, o = {}) {
        if (rc) return add(rc.curve(points, opts(o)));
        return add(el("polyline", { points: points.map((p) => p.join(",")).join(" "), fill: "none", stroke: o.color || C.ink }));
      },
      text(x, y, s, o = {}) {
        const family = o.mono ? "Geist Mono, monospace" : o.sans ? "Geist, sans-serif" : "Caveat, cursive";
        const t = el("text", {
          x, y, fill: o.color || C.white, "font-size": o.size || (o.mono || o.sans ? 13 : 20),
          "text-anchor": o.anchor || "middle", "font-family": family, "font-weight": o.weight || (o.mono || o.sans ? 500 : 600),
        });
        String(s).split("\n").forEach((ln, i) => {
          const ts = el("tspan", { x, dy: i === 0 ? 0 : (o.lh || 1.2) + "em" });
          ts.textContent = ln;
          t.appendChild(ts);
        });
        return add(t);
      },
      box(x, y, w, h, title, sub, o = {}) {
        const color = o.color || C.ink;
        api.rect(x, y, w, h, { color, fill: o.fill === false ? undefined : tint(color, 0.16), dash: o.dash, gap: o.gap });
        const lines = sub ? sub.split("\n").length : 0;
        const ty = y + h / 2 - (lines ? lines * 8 : -6);
        api.text(x + w / 2, ty, title, { size: o.size || 21, color: o.titleColor || C.white });
        if (sub) api.text(x + w / 2, ty + 20, sub, { sans: true, size: 12, color: C.muted, lh: 1.35, weight: 400 });
      },
      arrow(x1, y1, x2, y2, o = {}) {
        const color = o.color || C.ink;
        if (o.bend) {
          const mx = (x1 + x2) / 2 + (o.bend.x || 0), my = (y1 + y2) / 2 + (o.bend.y || 0);
          api.curve([[x1, y1], [mx, my], [x2, y2]], { color, dash: o.dash });
          var ax = mx, ay = my;
        } else {
          api.line(x1, y1, x2, y2, { color, dash: o.dash });
          var ax = x1, ay = y1;
        }
        const ang = Math.atan2(y2 - ay, x2 - ax), L = 11;
        [0.45, -0.45].forEach((d) => api.line(x2, y2, x2 - L * Math.cos(ang + d), y2 - L * Math.sin(ang + d), { color }));
        if (o.label) {
          const lx = o.bend ? (x1 + x2) / 2 + (o.bend.x || 0) / 2 : (x1 + x2) / 2;
          const ly = o.bend ? (y1 + y2) / 2 + (o.bend.y || 0) / 2 : (y1 + y2) / 2;
          api.text(lx + (o.lx || 0), ly + (o.ly ?? -8), o.label, { size: o.lsize || 17, color: o.lcolor || C.amber });
        }
      },
      dot(cx, cy, r, color) {
        return add(el("circle", { cx, cy, r, fill: color || C.ink }));
      },
    };
    return api;
  }

  window.sketch = function (id, draw) {
    const svg = document.getElementById(id);
    if (!svg) return;
    const go = () => {
      svg.innerHTML = "";
      try { draw(make(svg)); } catch (e) { console.error("sketch " + id, e); }
    };
    (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(go);
  };
})();
