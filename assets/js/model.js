/* Data Model Lab — shared model loader and graph helpers.
   Every exploration calls DML.load() and gets back an indexed model:
     m.tables, m.tableById, m.layers, m.layerById
     m.columnById[colId] -> { id, table, col }
     m.colUp[colId] / m.colDown[colId] -> [edge]
     m.tableEdges -> [{ from, to, count, transforms }]
     m.trace(colIds, {up, down}) -> { cols:Set, edges:Set }
     m.traceTable(tableId) -> { tables:Set, cols:Set, edges:Set }
   Column ids are "<table id>.<column name>". */
(function () {
  "use strict";
  var DML = {};
  var root = document.documentElement.getAttribute("data-root") || "./";

  DML.load = function (url) {
    return fetch(url || root + "data/sample-model.json").then(function (r) {
      if (!r.ok) throw new Error("Could not load model metadata (" + r.status + ")");
      return r.json();
    }).then(index);
  };

  function index(raw) {
    var m = raw;
    m.layerById = {};
    m.layers.forEach(function (l) { m.layerById[l.id] = l; });
    m.tableById = {};
    m.columnById = {};
    m.tables.forEach(function (t) {
      m.tableById[t.id] = t;
      t.columns.forEach(function (c) {
        var id = t.id + "." + c.name;
        c.id = id;
        m.columnById[id] = { id: id, table: t, col: c };
      });
    });
    m.colUp = {}; m.colDown = {};
    m.columnLineage.forEach(function (e, i) {
      e.i = i;
      (m.colDown[e.from] = m.colDown[e.from] || []).push(e);
      (m.colUp[e.to] = m.colUp[e.to] || []).push(e);
      e.fromTable = m.columnById[e.from].table.id;
      e.toTable = m.columnById[e.to].table.id;
    });
    var te = {};
    m.columnLineage.forEach(function (e) {
      if (e.fromTable === e.toTable) return;
      var k = e.fromTable + "|" + e.toTable;
      if (!te[k]) te[k] = { from: e.fromTable, to: e.toTable, count: 0, transforms: {} };
      te[k].count++;
      te[k].transforms[e.transform] = (te[k].transforms[e.transform] || 0) + 1;
    });
    m.tableEdges = Object.keys(te).map(function (k) { return te[k]; });

    m.trace = function (ids, opts) {
      opts = opts || { up: true, down: true };
      var cols = new Set(), edges = new Set();
      function walk(id, dir) {
        var list = dir === "up" ? m.colUp[id] : m.colDown[id];
        (list || []).forEach(function (e) {
          edges.add(e.i);
          var next = dir === "up" ? e.from : e.to;
          if (!cols.has(next + dir)) { cols.add(next + dir); walk(next, dir); }
        });
      }
      ids.forEach(function (id) {
        if (opts.up) walk(id, "up");
        if (opts.down) walk(id, "down");
      });
      var out = new Set(ids);
      cols.forEach(function (x) { out.add(x.replace(/(up|down)$/, "")); });
      return { cols: out, edges: edges };
    };
    m.traceTable = function (tableId) {
      var t = m.tableById[tableId];
      var r = m.trace(t.columns.map(function (c) { return c.id; }));
      var tables = new Set();
      r.cols.forEach(function (c) { tables.add(m.columnById[c].table.id); });
      return { tables: tables, cols: r.cols, edges: r.edges };
    };
    m.relationshipsFor = function (semTableName) {
      return m.relationships.filter(function (r) { return r.fact === semTableName || r.dim === semTableName; });
    };
    return m;
  }

  // CSS-variable aware colors so diagrams follow light/dark theme
  DML.css = function (name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  };
  DML.layerColor = function (layerId) { return DML.css("--l-" + layerId) || "#888"; };

  // one shared tooltip
  var tip;
  DML.tip = {
    show: function (html, evt) {
      if (!tip) { tip = document.createElement("div"); tip.className = "viz-tooltip"; document.body.appendChild(tip); }
      tip.innerHTML = html;
      tip.classList.add("is-on");
      DML.tip.move(evt);
    },
    move: function (evt) {
      if (!tip || !evt) return;
      var x = evt.clientX + 14, y = evt.clientY + 14;
      var w = tip.offsetWidth, h = tip.offsetHeight;
      if (x + w > window.innerWidth - 8) x = evt.clientX - w - 14;
      if (y + h > window.innerHeight - 8) y = evt.clientY - h - 14;
      tip.style.left = x + "px"; tip.style.top = y + "px";
    },
    hide: function () { if (tip) tip.classList.remove("is-on"); }
  };

  DML.esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  };
  DML.keyTag = function (c) {
    if (c.isMeasure) return '<span class="tag tag--sk">fx</span>';
    if (!c.key) return "";
    var cls = { PK: "pk", FK: "fk", SK: "sk", BK: "bk", DD: "bk" }[c.key] || "";
    return '<span class="tag tag--' + cls + '">' + c.key + "</span>";
  };
  DML.tableLabel = function (t) {
    if (t.layer === "source") return t.schema + "." + t.name;
    if (t.layer === "semantic" || t.layer === "report") return t.name;
    return t.name;
  };
  DML.tablePanel = function (m, t) {
    var L = m.layerById[t.layer];
    var h = '<p class="eyebrow" style="color:' + DML.layerColor(t.layer) + '">' + DML.esc(L.name) + "</p>";
    h += "<h3>" + DML.esc(DML.tableLabel(t)) + "</h3>";
    if (t.description) h += "<p>" + DML.esc(t.description) + "</p>";
    var kv = [];
    if (t.system) kv.push(["System", t.system]);
    if (t.ingest) kv.push(["Ingest", t.ingest]);
    if (t.grain) kv.push(["Grain", t.grain]);
    if (t.fact_type) kv.push(["Fact type", t.fact_type]);
    if (t.additivity) kv.push(["Additivity", t.additivity]);
    if (t.scd) kv.push(["SCD", t.scd]);
    if (t.storage) kv.push(["Storage", t.storage]);
    if (kv.length) h += '<dl class="kv">' + kv.map(function (x) { return "<dt>" + x[0] + "</dt><dd>" + DML.esc(x[1]) + "</dd>"; }).join("") + "</dl>";
    h += "<h4>Columns (" + t.columns.length + ")</h4><table class=\"coltable\">";
    t.columns.forEach(function (c) {
      h += "<tr><td>" + DML.esc(c.name) + " " + DML.keyTag(c) + (c.hidden ? ' <span class="tag">hidden</span>' : "") + "</td><td class=\"muted\">" + DML.esc(c.expression || c.type) + "</td></tr>";
    });
    return h + "</table>";
  };

  window.DML = DML;
})();
