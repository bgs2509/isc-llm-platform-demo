// isc-2 site: interactions (pickers, slider, filter). Plain JavaScript, no external scripts.
(function () {
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
