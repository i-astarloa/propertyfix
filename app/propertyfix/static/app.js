// Ejemplos de incidencias en el formulario
document.querySelectorAll(".ejemplos button").forEach((b) => {
  b.addEventListener("click", () => {
    const t = document.getElementById("descripcion");
    t.value = b.dataset.ej;
    t.focus();
  });
});

// Filtro del directorio de proveedores
const filtro = document.getElementById("filtro-especialidad");
if (filtro) {
  filtro.addEventListener("change", () => {
    document.querySelectorAll("#tabla-proveedores tr[data-esp]").forEach((tr) => {
      tr.style.display = !filtro.value || tr.dataset.esp.split(" ").includes(filtro.value) ? "" : "none";
    });
  });
}

// Actualización en vivo de la incidencia mientras los agentes trabajan
const detalle = document.getElementById("detalle");
if (detalle) {
  const id = detalle.dataset.id;
  let vueltasQuieto = 0;
  const refrescar = async () => {
    try {
      const r = await fetch(`/incidencias/${id}/fragmento`, { cache: "no-store" });
      if (r.ok) {
        const html = await r.text();
        detalle.innerHTML = html;
        const marca = document.getElementById("marca-procesando");
        vueltasQuieto = marca && marca.textContent.trim() === "1" ? 0 : vueltasQuieto + 1;
      }
    } catch (e) { /* sin conexión momentánea */ }
    // Tras terminar se hacen dos refrescos más por si acaba de cambiar de estado
    if (vueltasQuieto < 2) setTimeout(refrescar, 2000);
  };
  if (detalle.dataset.procesando === "1" || true) setTimeout(refrescar, 1500);
}
