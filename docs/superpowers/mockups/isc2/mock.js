// isc-2 mockups: interactions only. No network calls; every number on these pages is a placeholder.
(function () {
  // Mock notes toggle
  var btn = document.getElementById("notes-toggle");
  if (btn) btn.addEventListener("click", function () {
    var hidden = document.body.classList.toggle("hide-notes");
    btn.textContent = hidden ? "Show mock notes" : "Hide mock notes";
  });

  // Picker: [data-picker] groups; [data-show=x] controls reveal [data-panel=x] inside the same group
  document.querySelectorAll("[data-picker]").forEach(function (group) {
    var controls = group.querySelectorAll("[data-show]");
    function show(key) {
      controls.forEach(function (c) { c.setAttribute("aria-pressed", String(c.dataset.show === key)); });
      group.querySelectorAll("[data-panel]").forEach(function (p) { p.hidden = p.dataset.panel !== key; });
    }
    controls.forEach(function (c) {
      c.addEventListener("click", function () { show(c.dataset.show); });
      c.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); show(c.dataset.show); }
      });
    });
    if (controls.length) show(controls[0].dataset.show);
  });

  // Page 1: concurrency slider over the five measured levels
  var levels = [1, 2, 4, 8, 16];
  var slider = document.getElementById("conc");
  if (slider) {
    var update = function () {
      var c = levels[Number(slider.value)];
      document.querySelectorAll("[data-conc]").forEach(function (el) { el.textContent = c; });
      document.querySelectorAll(".bars rect[data-c]").forEach(function (r) {
        r.classList.toggle("on", Number(r.dataset.c) === c);
      });
    };
    slider.addEventListener("input", update);
    update();
  }

  // Page 4: canned agent reply (the real page calls POST /console/api/agent/ask)
  var form = document.getElementById("ask-form");
  if (form) form.addEventListener("submit", function (e) {
    e.preventDefault();
    var out = document.getElementById("ask-out");
    out.hidden = false;
    document.getElementById("ask-q").textContent = document.getElementById("ask-input").value || "(empty)";
  });

  // Page 6: incident filter by layer
  var filters = document.querySelectorAll("[data-layer-filter]");
  filters.forEach(function (f) {
    f.addEventListener("click", function () {
      var layer = f.dataset.layerFilter;
      filters.forEach(function (x) { x.setAttribute("aria-pressed", String(x === f)); });
      document.querySelectorAll(".card[data-layer]").forEach(function (card) {
        card.hidden = layer !== "all" && card.dataset.layer !== layer;
      });
    });
  });
})();
