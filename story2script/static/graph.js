/* 自包含的人物关系图：纯 SVG + 轻量力导向布局，无任何外部依赖（内网友好）。 */
(function () {
  const mount = document.getElementById("story-graph");
  if (!mount) return;
  const SVG_NS = "http://www.w3.org/2000/svg";

  fetch(mount.dataset.src).then(r => r.json()).then(draw).catch(() => {
    mount.innerHTML = '<p class="muted">关系图加载失败。</p>';
  });

  function draw(graph) {
    const nodes = (graph.nodes || []).map((n, i) => ({ ...n, i }));
    const idx = Object.fromEntries(nodes.map(n => [n.id, n]));
    const edges = (graph.edges || [])
      .filter(e => idx[e.from] && idx[e.to])
      .map(e => ({ ...e, s: idx[e.from], t: idx[e.to] }));
    if (!nodes.length) { mount.innerHTML = '<p class="muted">暂无人物关系。</p>'; return; }

    const W = mount.clientWidth || 600, H = mount.clientHeight || 420;
    // 初始位置：按序号铺在圆上（确定性，不用随机）
    const R0 = Math.min(W, H) * 0.36;
    nodes.forEach((n, i) => {
      const a = (2 * Math.PI * i) / nodes.length;
      n.x = W / 2 + R0 * Math.cos(a);
      n.y = H / 2 + R0 * Math.sin(a);
    });

    // 力导向迭代
    const K = Math.sqrt((W * H) / nodes.length) * 0.55;
    for (let iter = 0; iter < 320; iter++) {
      const cool = 1 - iter / 320;
      for (let a = 0; a < nodes.length; a++) {
        let fx = 0, fy = 0;
        for (let b = 0; b < nodes.length; b++) {
          if (a === b) continue;
          let dx = nodes[a].x - nodes[b].x, dy = nodes[a].y - nodes[b].y;
          let d = Math.hypot(dx, dy) || 0.01;
          const rep = (K * K) / d;                 // 斥力
          fx += (dx / d) * rep; fy += (dy / d) * rep;
        }
        nodes[a].fx = fx; nodes[a].fy = fy;
      }
      edges.forEach(e => {                          // 弹簧引力
        let dx = e.t.x - e.s.x, dy = e.t.y - e.s.y;
        let d = Math.hypot(dx, dy) || 0.01;
        const att = (d * d) / K / 14;
        const ux = dx / d, uy = dy / d;
        e.s.fx += ux * att; e.s.fy += uy * att;
        e.t.fx -= ux * att; e.t.fy -= uy * att;
      });
      nodes.forEach(n => {
        n.fx += (W / 2 - n.x) * 0.015; n.fy += (H / 2 - n.y) * 0.015;  // 向心
        n.x += Math.max(-18, Math.min(18, n.fx)) * cool;
        n.y += Math.max(-18, Math.min(18, n.fy)) * cool;
        n.x = Math.max(24, Math.min(W - 24, n.x));
        n.y = Math.max(20, Math.min(H - 20, n.y));
      });
    }

    const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
    const gEdges = el("g"), gNodes = el("g");
    svg.append(gEdges, gNodes);

    edges.forEach(e => {
      const ln = el("line", { class: "gedge", x1: e.s.x, y1: e.s.y, x2: e.t.x, y2: e.t.y });
      e._line = ln; gEdges.append(ln);
      if (e.type) {
        const lb = el("text", { class: "gedge-label",
          x: (e.s.x + e.t.x) / 2, y: (e.s.y + e.t.y) / 2 });
        lb.textContent = e.type; e._lbl = lb; gEdges.append(lb);
      }
    });

    nodes.forEach(n => {
      const g = el("g", { class: "gnode" });
      const r = 6 + (n.importance || 0) * 16;
      const c = el("circle", { cx: n.x, cy: n.y, r,
        fill: n.role === "protagonist" ? "#ffb454" : "#6cb6ff", "fill-opacity": .85 });
      const tx = el("text", { x: n.x + r + 3, y: n.y + 4 });
      tx.textContent = n.name;
      n._g = g;
      g.append(c, tx); gNodes.append(g);
      g.addEventListener("click", () => highlight(n));
    });

    let active = null;
    function highlight(n) {
      active = active === n ? null : n;
      const neighbors = new Set([active && active.id]);
      edges.forEach(e => {
        const on = !active || e.s === active || e.t === active;
        e._line.classList.toggle("hl", !!active && on);
        e._line.classList.toggle("dim", !!active && !on);
        if (e._lbl) e._lbl.classList.toggle("dim", !!active && !on);
        if (active && on) { neighbors.add(e.s.id); neighbors.add(e.t.id); }
      });
      nodes.forEach(m =>
        m._g.classList.toggle("dim", !!active && !neighbors.has(m.id)));
    }

    mount.innerHTML = ""; mount.append(svg);
  }

  function el(tag, attrs) {
    const e = document.createElementNS(SVG_NS, tag);
    for (const k in (attrs || {})) e.setAttribute(k, attrs[k]);
    return e;
  }
})();
