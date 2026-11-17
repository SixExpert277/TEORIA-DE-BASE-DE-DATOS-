const Graficos = (() => {
  const PALETA = [
    "#1f3a5f",
    "#e8a33d",
    "#3a7ca5",
    "#7a9e7e",
    "#c8553d",
    "#6c5b7b",
    "#2a9d8f",
    "#b56576",
    "#8d99ae",
    "#f4a261",
    "#355070",
    "#90be6d",
  ];
  const instancias = new Map();

  if (window.Chart) {
    Chart.defaults.font.family = '"Inter", "Segoe UI", system-ui, sans-serif';
    Chart.defaults.color = "#5b6878";
    Chart.defaults.plugins.legend.labels.boxWidth = 12;
    Chart.defaults.maintainAspectRatio = false;
  }

  function color(indice) {
    return PALETA[indice % PALETA.length];
  }

  function destruir(id) {
    const lienzo = document.getElementById(id);
    const existente = instancias.get(id) || (window.Chart && lienzo ? Chart.getChart(lienzo) : null);
    if (existente) existente.destroy();
    instancias.delete(id);
  }

  function dibujar(id, configuracion) {
    destruir(id);
    const lienzo = document.getElementById(id);
    if (!lienzo || !window.Chart) return null;
    const grafico = new Chart(lienzo, configuracion);
    instancias.set(id, grafico);
    return grafico;
  }

  function sinDatos(id, texto) {
    destruir(id);
    const lienzo = document.getElementById(id);
    if (!lienzo) return;
    const contexto = lienzo.getContext("2d");
    const ancho = lienzo.clientWidth;
    const alto = lienzo.clientHeight;
    lienzo.width = ancho;
    lienzo.height = alto;
    contexto.clearRect(0, 0, ancho, alto);
    contexto.fillStyle = "#5b6878";
    contexto.font = '14px "Inter", "Segoe UI", sans-serif';
    contexto.textAlign = "center";
    contexto.fillText(texto || "Sin datos para graficar", ancho / 2, alto / 2);
  }

  function opcionesTitulo(titulo) {
    return titulo ? { display: true, text: titulo, color: "#152a46", font: { size: 14, weight: "600" } } : { display: false };
  }

  function torta(id, etiquetas, valores, titulo) {
    if (!valores.length) return sinDatos(id);
    const total = valores.reduce((a, b) => a + Number(b || 0), 0);
    return dibujar(id, {
      type: "doughnut",
      data: {
        labels: etiquetas,
        datasets: [
          {
            data: valores,
            backgroundColor: etiquetas.map((_, i) => color(i)),
            borderColor: "#ffffff",
            borderWidth: 2,
          },
        ],
      },
      options: {
        cutout: "52%",
        plugins: {
          title: opcionesTitulo(titulo),
          legend: { position: "right" },
          tooltip: {
            callbacks: {
              label: (item) => {
                const porcentaje = total ? ((item.parsed / total) * 100).toFixed(1) : 0;
                return ` ${item.label}: ${item.parsed} (${porcentaje}%)`;
              },
            },
          },
        },
      },
    });
  }

  function barras(id, etiquetas, series, opciones = {}) {
    if (!etiquetas.length) return sinDatos(id);
    const { titulo, horizontal = false, apiladas = false, ejeX, ejeY } = opciones;
    return dibujar(id, {
      type: "bar",
      data: {
        labels: etiquetas,
        datasets: series.map((serie, i) => ({
          label: serie.etiqueta,
          data: serie.valores,
          backgroundColor: serie.color || color(i),
          borderRadius: 4,
          maxBarThickness: 46,
        })),
      },
      options: {
        indexAxis: horizontal ? "y" : "x",
        plugins: {
          title: opcionesTitulo(titulo),
          legend: { display: series.length > 1, position: "bottom" },
        },
        scales: {
          x: {
            stacked: apiladas,
            title: { display: Boolean(horizontal ? ejeY : ejeX), text: horizontal ? ejeY : ejeX },
            ticks: { precision: 0, autoSkip: true, maxRotation: 50 },
            grid: { display: horizontal },
          },
          y: {
            stacked: apiladas,
            beginAtZero: true,
            title: { display: Boolean(horizontal ? ejeX : ejeY), text: horizontal ? ejeX : ejeY },
            ticks: { precision: 0 },
            grid: { display: !horizontal },
          },
        },
      },
    });
  }

  function frecuencia(id, filas, claveEtiqueta, claveValor, opciones = {}) {
    const etiquetas = filas.map((f) => String(f[claveEtiqueta] ?? "Sin dato"));
    const valores = filas.map((f) => Number(f[claveValor] || 0));
    return barras(id, etiquetas, [{ etiqueta: opciones.serie || "Frecuencia", valores, color: opciones.color }], opciones);
  }

  function comparativo(id, filas, claveGrupo, claveSerie, claveValor, opciones = {}) {
    const grupos = [...new Set(filas.map((f) => String(f[claveGrupo] ?? "Sin dato")))];
    const series = [...new Set(filas.map((f) => String(f[claveSerie] ?? "Sin dato")))];
    const matriz = series.map((serie) => ({
      etiqueta: serie,
      valores: grupos.map((grupo) => {
        const fila = filas.find(
          (f) => String(f[claveGrupo] ?? "Sin dato") === grupo && String(f[claveSerie] ?? "Sin dato") === serie
        );
        return fila ? Number(fila[claveValor] || 0) : 0;
      }),
    }));
    return barras(id, grupos, matriz, opciones);
  }

  return { torta, barras, frecuencia, comparativo, destruir, sinDatos };
})();
