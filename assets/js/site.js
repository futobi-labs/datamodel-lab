/* Data Model Lab — site map and page chrome.
   SITE is the single source of truth for navigation: the header, the
   section landing cards, breadcrumbs, prev/next and "related" links are all
   built from it. Add a page here and it shows up everywhere.

   Each page declares itself on <html>:
     data-root="../"          relative path back to the site root
     data-section="guide"     section id (omit on the home page)
     data-page="medallion"    page slug inside the section (omit on landings)
*/
(function () {
  "use strict";

  var SITE = {
    name: "Data Model Lab",
    tagline: "Structure, lineage and the craft of modeling",
    repo: "https://github.com/tannerspaulding/datamodel-lab",
    sister: {
      name: "Data Viz Lab",
      blurb: "The sibling lab: exploratory charts, Few, Tufte and new forms.",
      // Both labs are project sites under the same user site, so a path
      // relative to this site's root works on github.io and on a custom domain.
      url: (document.documentElement.getAttribute("data-root") || "./") + "../dataviz-lab/",
      // Sections of the sister site. Paths are relative to its root; keep in
      // sync with dataviz-lab as it grows.
      sections: [
        { title: "Home", path: "", blurb: "Start here" },
        { title: "Experimental", path: "experimental/", blurb: "Generative D3 with the data left in" },
        { title: "Stephen Few", path: "few/", blurb: "Bullet graphs, dashboards, table or graph" },
        { title: "Edward Tufte", path: "tufte/", blurb: "Sparklines, slopegraphs, small multiples" },
        { title: "New", path: "new/", blurb: "Forward-looking forms" }
      ]
    },
    sections: [
      {
        id: "guide", title: "Field Guide", path: "guide/",
        blurb: "What's commonplace in modeling today, written down plainly, with opinions where practice has settled and open questions where it hasn't.",
        pages: [
          { slug: "medallion", title: "Medallion architecture", blurb: "Bronze, silver, gold: what each layer owns, what it must never do, and where the lines blur.", layers: ["bronze", "silver", "gold"], related: ["explore/medallion-stack", "explore/lineage-flow"] },
          { slug: "dimensional-modeling", title: "Dimensional modeling", blurb: "Grain first. Facts, dimensions, star versus snowflake, degenerate and junk dimensions.", layers: ["gold"], related: ["explore/star-schema", "explore/bus-matrix"] },
          { slug: "slowly-changing-dimensions", title: "Slowly changing dimensions", blurb: "Type 0 through 7, which ones you actually need, and how to load Type 2 without tears.", layers: ["silver", "gold"], related: ["explore/star-schema"] },
          { slug: "conformed-dimensions", title: "Conformed dimensions & the bus matrix", blurb: "How separate facts share one language, and the matrix that keeps you honest.", layers: ["gold"], related: ["explore/bus-matrix"] },
          { slug: "semantic-models", title: "Semantic model preparation", blurb: "Relationships, cardinality, role-playing dates, measures, hiding keys, and what belongs in the model versus the warehouse.", layers: ["gold", "semantic"], related: ["explore/star-schema", "explore/column-lineage"] },
          { slug: "analytic-engine-layering", title: "Analytic engine layering", blurb: "Storage, compute, semantic engine, query and consumption: who does the work at each layer.", layers: ["gold", "semantic", "report"], related: ["explore/engine-layers"] },
          { slug: "naming-conventions", title: "Naming conventions", blurb: "A naming scheme that survives five years and three teams.", layers: ["bronze", "silver", "gold", "semantic"], related: ["explore/column-lineage"] },
          { slug: "metadata-driven-pipelines", title: "Metadata-driven pipelines", blurb: "Config tables, watermarks, and one pipeline that loads a hundred tables.", layers: ["source", "bronze", "silver"], related: ["explore/lineage-flow"] },
          { slug: "open-questions", title: "Open questions & ideation", blurb: "Where common practice is unsettled, and ideas worth trying.", layers: [], related: ["explore/"] }
        ]
      },
      {
        id: "explore", title: "Explorations", path: "explore/",
        blurb: "Interactive D3 views of model structure, not the data: how tables, columns and measures connect from source to report.",
        pages: [
          { slug: "lineage-flow", title: "Lineage flow", blurb: "A Sankey of every table from source to report, weighted by the columns that flow between them.", layers: ["source", "bronze", "silver", "gold", "semantic", "report"], related: ["guide/medallion", "guide/metadata-driven-pipelines"] },
          { slug: "column-lineage", title: "Column lineage tracer", blurb: "Click any column or measure and trace it all the way upstream and downstream.", layers: ["source", "bronze", "silver", "gold", "semantic", "report"], related: ["guide/naming-conventions", "guide/semantic-models"] },
          { slug: "star-schema", title: "Star schema explorer", blurb: "Each fact at its grain, its dimensions, cardinality, and the role-playing and inactive relationships.", layers: ["gold", "semantic"], related: ["guide/dimensional-modeling", "guide/semantic-models"] },
          { slug: "medallion-stack", title: "Medallion stack", blurb: "A zoomable stack of the lakehouse: layer, table, column. Drill in and back out.", layers: ["bronze", "silver", "gold"], related: ["guide/medallion"] },
          { slug: "bus-matrix", title: "Bus matrix", blurb: "Facts against conformed dimensions, as a matrix you can click through.", layers: ["gold"], related: ["guide/conformed-dimensions"] },
          { slug: "engine-layers", title: "Engine layer cake", blurb: "Follow a report visual down through DAX, the semantic engine, Direct Lake and Delta files.", layers: ["gold", "semantic", "report"], related: ["guide/analytic-engine-layering"] }
        ]
      },
      {
        id: "model", title: "Sample model", path: "model/",
        blurb: "The small, generic order-to-cash model every exploration reads, and how to swap in your own metadata.",
        pages: []
      }
    ]
  };

  window.SITE = SITE;

  var html = document.documentElement;
  var root = html.getAttribute("data-root") || "./";
  var sectionId = html.getAttribute("data-section") || "";
  var pageSlug = html.getAttribute("data-page") || "";

  // ---------- theme ----------
  function getStoredTheme() { try { return localStorage.getItem("dml-theme"); } catch (e) { return null; } }
  function storeTheme(t) { try { localStorage.setItem("dml-theme", t); } catch (e) { /* ignore */ } }
  var stored = getStoredTheme();
  if (stored === "light" || stored === "dark") html.setAttribute("data-theme", stored);

  function currentTheme() {
    var t = html.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  // ---------- helpers ----------
  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") n.textContent = attrs[k];
      else if (k === "html") n.innerHTML = attrs[k];
      else n.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function sectionById(id) { return SITE.sections.filter(function (s) { return s.id === id; })[0]; }
  function href(sec, page) { return root + sec.path + (page ? page.slug + ".html" : ""); }
  function resolveRef(ref) {
    // "explore/star-schema" or "guide/" -> {title, url, section}
    var parts = ref.split("/");
    var sec = sectionById(parts[0]);
    if (!sec) return null;
    if (!parts[1]) return { title: sec.title, url: href(sec), section: sec, blurb: sec.blurb };
    var p = sec.pages.filter(function (x) { return x.slug === parts[1]; })[0];
    return p ? { title: p.title, url: href(sec, p), section: sec, blurb: p.blurb, page: p } : null;
  }
  window.SITE_HELPERS = { resolveRef: resolveRef, href: href, root: root };

  var MARK = '<svg class="brand__mark" viewBox="0 0 32 32" aria-hidden="true">' +
    '<rect x="3" y="21" width="26" height="6" rx="2" fill="var(--l-bronze)"/>' +
    '<rect x="6" y="13.5" width="20" height="6" rx="2" fill="var(--l-silver)"/>' +
    '<rect x="9" y="6" width="14" height="6" rx="2" fill="var(--l-gold)"/>' +
    '<circle cx="16" cy="3.2" r="2.2" fill="var(--l-semantic)"/></svg>';

  // ---------- header ----------
  function buildHeader() {
    var host = document.getElementById("site-header");
    if (!host) return;
    var header = el("header", { class: "site-header" });
    var inner = el("div", { class: "site-header__inner" });
    var brand = el("a", { class: "brand", href: root || "./", html: MARK + "<span>Data Model Lab</span>" + '<span class="brand__sub">/ structure &amp; lineage</span>' });
    var toggle = el("button", { class: "btn nav-toggle", type: "button", "aria-expanded": "false", "aria-label": "Menu", text: "Menu" });
    toggle.addEventListener("click", function () {
      var open = header.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });

    var nav = el("nav", { class: "nav", "aria-label": "Main" });
    SITE.sections.forEach(function (s) {
      var a = el("a", { href: href(s), text: s.title });
      if (s.id === sectionId) { a.classList.add("is-active"); if (!pageSlug) a.setAttribute("aria-current", "page"); }
      nav.appendChild(a);
    });

    // sister-site menu
    var menu = el("div", { class: "nav__menu" });
    var mbtn = el("button", { class: "nav__sister", type: "button", "aria-expanded": "false", "aria-haspopup": "true", text: SITE.sister.name + " ↗" });
    var dd = el("div", { class: "nav__dropdown", role: "menu" });
    SITE.sister.sections.forEach(function (s) {
      dd.appendChild(el("a", { href: SITE.sister.url + s.path, role: "menuitem", html: s.title + (s.blurb ? "<small>" + s.blurb + "</small>" : "") }));
    });
    mbtn.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = menu.classList.toggle("is-open");
      mbtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.addEventListener("click", function () { menu.classList.remove("is-open"); mbtn.setAttribute("aria-expanded", "false"); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") { menu.classList.remove("is-open"); mbtn.setAttribute("aria-expanded", "false"); } });
    menu.appendChild(mbtn); menu.appendChild(dd);
    nav.appendChild(menu);

    var theme = el("button", { type: "button", "aria-label": "Toggle light or dark theme", title: "Toggle theme" });
    function paintTheme() { theme.textContent = currentTheme() === "dark" ? "☀ Light" : "☾ Dark"; }
    theme.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      html.setAttribute("data-theme", next); storeTheme(next); paintTheme();
      document.dispatchEvent(new CustomEvent("themechange", { detail: next }));
    });
    paintTheme();
    nav.appendChild(theme);

    inner.appendChild(brand); inner.appendChild(toggle); inner.appendChild(nav);
    header.appendChild(inner);
    host.replaceWith(header);
  }

  // ---------- breadcrumbs ----------
  function buildCrumbs() {
    var host = document.getElementById("crumbs");
    if (!host) return;
    var sec = sectionById(sectionId);
    var parts = [el("a", { href: root || "./", text: "Home" })];
    if (sec) {
      parts.push(" / ");
      if (pageSlug) parts.push(el("a", { href: href(sec), text: sec.title }));
      else parts.push(sec.title);
    }
    var page = sec && sec.pages.filter(function (p) { return p.slug === pageSlug; })[0];
    if (page) { parts.push(" / "); parts.push(page.title); }
    var n = el("div", { class: "crumbs" }, parts);
    host.replaceWith(n);
  }

  // ---------- table of contents (articles) ----------
  function buildToc() {
    var toc = document.querySelector(".toc");
    var article = document.querySelector(".prose");
    if (!toc || !article) return;
    var hs = article.querySelectorAll("h2");
    if (!hs.length) { toc.remove(); return; }
    var ol = el("ol");
    var links = [];
    hs.forEach(function (h) {
      if (!h.id) h.id = h.textContent.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
      var a = el("a", { href: "#" + h.id, text: h.textContent });
      links.push({ a: a, h: h });
      ol.appendChild(el("li", null, [a]));
    });
    toc.appendChild(el("h4", { text: "On this page" }));
    toc.appendChild(ol);
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            links.forEach(function (l) { l.a.classList.toggle("is-active", l.h === en.target); });
          }
        });
      }, { rootMargin: "-80px 0px -70% 0px" });
      links.forEach(function (l) { io.observe(l.h); });
    }
  }

  // ---------- cards ----------
  function chips(layers) {
    var wrap = el("div", { class: "card__meta" });
    (layers || []).forEach(function (l) { wrap.appendChild(el("span", { class: "chip chip--" + l, text: l })); });
    return wrap;
  }
  function card(url, num, title, blurb, layers, extraClass) {
    return el("a", { class: "card" + (extraClass ? " " + extraClass : ""), href: url }, [
      num ? el("span", { class: "card__num", text: num }) : null,
      el("span", { class: "card__title", text: title }),
      el("span", { class: "card__blurb", text: blurb }),
      layers && layers.length ? chips(layers) : null
    ]);
  }
  function buildCardGrids() {
    document.querySelectorAll("[data-cards]").forEach(function (host) {
      var sec = sectionById(host.getAttribute("data-cards"));
      if (!sec) return;
      var grid = el("div", { class: "cards" });
      sec.pages.forEach(function (p, i) {
        grid.appendChild(card(href(sec, p), String(i + 1).padStart(2, "0"), p.title, p.blurb, p.layers));
      });
      host.appendChild(grid);
    });
    document.querySelectorAll("[data-sister-cards]").forEach(function (host) {
      var grid = el("div", { class: "cards" });
      SITE.sister.sections.forEach(function (s) {
        grid.appendChild(card(SITE.sister.url + s.path, "↗ " + SITE.sister.name, s.title === "Home" ? SITE.sister.name : s.title, s.title === "Home" ? SITE.sister.blurb : (s.blurb || ""), null, "card--sister"));
      });
      host.appendChild(grid);
    });
  }

  // ---------- footer: related + pager ----------
  function buildFooter() {
    var host = document.getElementById("site-footer");
    if (!host) return;
    var frag = document.createDocumentFragment();
    var sec = sectionById(sectionId);
    var idx = sec ? sec.pages.findIndex(function (p) { return p.slug === pageSlug; }) : -1;
    if (sec && idx >= 0) {
      var page = sec.pages[idx];
      if (page.related && page.related.length) {
        var rel = el("div", { class: "related" }, [el("h4", { text: sec.id === "guide" ? "See it in the explorations" : "Read more in the field guide" })]);
        var grid = el("div", { class: "cards" });
        page.related.forEach(function (r) {
          var x = resolveRef(r);
          if (x) grid.appendChild(card(x.url, x.section.title, x.title, x.blurb, x.page && x.page.layers));
        });
        rel.appendChild(grid);
        frag.appendChild(rel);
      }
      var pager = el("nav", { class: "pager", "aria-label": "Previous and next" });
      var prev = sec.pages[idx - 1], next = sec.pages[idx + 1];
      if (prev) pager.appendChild(el("a", { href: href(sec, prev), html: "<small>← Previous</small>" + prev.title }));
      if (next) pager.appendChild(el("a", { class: "pager__next", href: href(sec, next), html: "<small>Next →</small>" + next.title }));
      frag.appendChild(pager);
    }
    var foot = el("footer", { class: "site-footer" });
    foot.appendChild(el("div", { class: "site-footer__inner", html:
      "<span>Data Model Lab &middot; an exploratory notebook on data modeling. Sample data is generic and invented.</span>" +
      '<span><a href="' + SITE.sister.url + '">' + SITE.sister.name + ' ↗</a> &middot; <a href="' + SITE.repo + '">Source on GitHub</a></span>' }));
    frag.appendChild(foot);
    host.replaceWith(frag);
  }

  function init() { buildHeader(); buildCrumbs(); buildToc(); buildCardGrids(); buildFooter(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
