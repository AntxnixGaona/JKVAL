/* Mantiene el menú semánticamente abierto en escritorio y plegado en móvil. */
(function () {
  "use strict";
  var disclosure = document.querySelector(".nav-disclosure");
  if (!disclosure) return;
  var wide = window.matchMedia("(min-width: 981px)");
  function sync() {
    disclosure.open = wide.matches;
  }
  sync();
  if (typeof wide.addEventListener === "function") {
    wide.addEventListener("change", sync);
  }
})();
