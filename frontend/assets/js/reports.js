const Util = (() => {
  const formatoMoneda = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
  const formatoNumero = new Intl.NumberFormat("es-CO");
  const PATRON_MES_ANIO = /^(0[1-9]|1[0-2])\/(\d{4})$/;

  function vacio(valor) {
    return valor === undefined || valor === null || String(valor).trim() === "";
  }

  function fecha(valor) {
    if (vacio(valor)) return "";
    const texto = String(valor).trim();
    if (/^\d{2}\/\d{2}\/\d{4}$/.test(texto)) return texto;
    const iso = texto.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (iso) return `${iso[3]}/${iso[2]}/${iso[1]}`;
    const marca = Date.parse(texto);
    if (Number.isNaN(marca)) return texto;
    const d = new Date(marca);
    return `${String(d.getUTCDate()).padStart(2, "0")}/${String(d.getUTCMonth() + 1).padStart(2, "0")}/${d.getUTCFullYear()}`;
  }

  function fechaOrdenable(valor) {
    const texto = fecha(valor);
    const partes = texto.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    return partes ? `${partes[3]}-${partes[2]}-${partes[1]}` : texto;
  }

  function fechaIso(valor) {
    const texto = fechaOrdenable(valor);
    return /^\d{4}-\d{2}-\d{2}$/.test(texto) ? texto : "";
  }

  function moneda(valor) {
    if (vacio(valor) || Number.isNaN(Number(valor))) return vacio(valor) ? "" : String(valor);
    return formatoMoneda.format(Number(valor));
  }

  function numero(valor, decimales) {
    if (vacio(valor) || Number.isNaN(Number(valor))) return vacio(valor) ? "" : String(valor);
    if (decimales !== undefined) return Number(valor).toFixed(decimales);
    return formatoNumero.format(Number(valor));
  }

  function mesAnioValido(texto) {
    return PATRON_MES_ANIO.test(String(texto || "").trim());
  }

  function mesAnioComparable(texto) {
    const partes = String(texto).trim().match(PATRON_MES_ANIO);
    return partes ? Number(partes[2]) * 100 + Number(partes[1]) : NaN;
  }

  function isoAMesAnio(iso) {
    const partes = String(iso || "").match(/^(\d{4})-(\d{2})-\d{2}$/);
    return partes ? `${partes[2]}/${partes[1]}` : "";
  }

  function valorDe(fila, ...claves) {
    for (const clave of claves) {
      if (fila && !vacio(fila[clave])) return fila[clave];
    }
    return undefined;
  }

  function columnasPresentes(filas, candidatas) {
    const presentes = candidatas.filter((columna) => {
      const claves = columna.claves || [columna.clave];
      return filas.some((fila) => claves.some((clave) => fila && fila[clave] !== undefined));
    });
    return presentes.length ? presentes : candidatas.filter((columna) => !columna.opcional);
  }

  function contarDistintos(filas, clave) {
    return new Set(filas.map((f) => f[clave]).filter((v) => !vacio(v))).size;
  }

  function sumar(filas, clave) {
    return filas.reduce((total, f) => total + (Number(f[clave]) || 0), 0);
  }

  function datosFormulario(formulario) {
    return Object.fromEntries(new FormData(formulario).entries());
  }

  return {
    vacio,
    fecha,
    fechaOrdenable,
    fechaIso,
    moneda,
    numero,
    mesAnioValido,
    mesAnioComparable,
    isoAMesAnio,
    valorDe,
    columnasPresentes,
    contarDistintos,
    sumar,
    datosFormulario,
  };
})();

const Notificar = (texto, tipo = "info") => {
  const contenedor = document.getElementById("notificaciones");
  if (!contenedor) return;
  const aviso = document.createElement("div");
  aviso.className = `notificacion ${tipo}`;
  aviso.setAttribute("role", tipo === "error" ? "alert" : "status");
  aviso.textContent = texto;
  contenedor.appendChild(aviso);
  setTimeout(() => aviso.remove(), tipo === "error" ? 7000 : 4000);
};

const Confirmar = ({ titulo = "Confirmar", texto = "", boton = "Confirmar", peligro = false } = {}) =>
  new Promise((resolver) => {
    const modal = document.getElementById("modal-confirmar");
    const aceptar = document.getElementById("confirmar-aceptar");
    const cancelar = modal.querySelector('button[value="cancelar"]');
    if (modal.open) {
      resolver(false);
      return;
    }
    document.getElementById("confirmar-titulo").textContent = titulo;
    document.getElementById("confirmar-texto").textContent = texto;
    aceptar.textContent = boton;
    aceptar.className = peligro ? "btn btn-peligro" : "btn";
    let terminado = false;
    const terminar = (decision) => {
      if (terminado) return;
      terminado = true;
      aceptar.removeEventListener("click", alAceptar);
      cancelar.removeEventListener("click", alCancelar);
      modal.removeEventListener("cancel", alCancelar);
      modal.removeEventListener("close", alCerrar);
      if (modal.open) modal.close(decision ? "aceptar" : "cancelar");
      resolver(decision);
    };
    function alAceptar(evento) {
      evento.preventDefault();
      terminar(true);
    }
    function alCancelar(evento) {
      evento.preventDefault();
      terminar(false);
    }
    function alCerrar() {
      terminar(false);
    }
    aceptar.addEventListener("click", alAceptar);
    cancelar.addEventListener("click", alCancelar);
    modal.addEventListener("cancel", alCancelar);
    modal.addEventListener("close", alCerrar);
    modal.showModal();
    aceptar.focus();
  });

const Tabla = (() => {
  const POR_PAGINA = 100;

  function valorCelda(columna, fila) {
    const claves = columna.claves || [columna.clave];
    return Util.valorDe(fila, ...claves);
  }

  function textoCelda(columna, fila) {
    const valor = valorCelda(columna, fila);
    if (columna.formato) return columna.formato(valor, fila);
    switch (columna.tipo) {
      case "moneda":
        return Util.moneda(valor);
      case "fecha":
        return Util.fecha(valor);
      case "numero":
        return Util.numero(valor);
      case "rating":
        return Util.vacio(valor) ? "" : Util.numero(valor, 2);
      default:
        return Util.vacio(valor) ? "" : String(valor);
    }
  }

  function comparador(columna, direccion) {
    const signo = direccion === "DESC" ? -1 : 1;
    const numerico = ["moneda", "numero", "rating"].includes(columna.tipo);
    return (a, b) => {
      let x = valorCelda(columna, a);
      let y = valorCelda(columna, b);
      if (Util.vacio(x) && Util.vacio(y)) return 0;
      if (Util.vacio(x)) return 1;
      if (Util.vacio(y)) return -1;
      if (numerico) return (Number(x) - Number(y)) * signo;
      if (columna.tipo === "fecha") {
        x = Util.fechaOrdenable(x);
        y = Util.fechaOrdenable(y);
      }
      return String(x).localeCompare(String(y), "es", { numeric: true, sensitivity: "base" }) * signo;
    };
  }

  function render(contenedor, columnas, filas, opciones = {}) {
    if (typeof contenedor === "string") contenedor = document.getElementById(contenedor);
    if (!contenedor) return;
    const estado = {
      columnas,
      filas: Array.isArray(filas) ? filas : [],
      opciones,
      orden: opciones.ordenInicial || null,
      filtro: "",
      pagina: 1,
    };
    contenedor._tabla = estado;
    dibujar(contenedor);
  }

  function filtrar(contenedor, texto) {
    if (typeof contenedor === "string") contenedor = document.getElementById(contenedor);
    if (!contenedor || !contenedor._tabla) return;
    contenedor._tabla.filtro = String(texto || "").trim().toLowerCase();
    contenedor._tabla.pagina = 1;
    dibujar(contenedor);
  }

  function filasVisibles(estado) {
    const { columnas, opciones } = estado;
    let filas = estado.filas.slice();
    if (estado.filtro) {
      filas = filas.filter((fila) =>
        columnas.some((columna) => textoCelda(columna, fila).toLowerCase().includes(estado.filtro))
      );
    }
    const columnaOrden = estado.orden && columnas.find((c) => c.clave === estado.orden.clave);
    if (columnaOrden || opciones.grupo) {
      const porColumna = columnaOrden ? comparador(columnaOrden, estado.orden.direccion) : () => 0;
      const porGrupo = opciones.grupo
        ? (a, b) => String(opciones.grupo(a)).localeCompare(String(opciones.grupo(b)), "es", { numeric: true })
        : () => 0;
      filas = filas
        .map((fila, indice) => ({ fila, indice }))
        .sort((a, b) => porGrupo(a.fila, b.fila) || porColumna(a.fila, b.fila) || a.indice - b.indice)
        .map((item) => item.fila);
    }
    return filas;
  }

  function dibujar(contenedor) {
    const estado = contenedor._tabla;
    const { columnas, opciones } = estado;
    const filas = filasVisibles(estado);
    const porPagina = opciones.porPagina || POR_PAGINA;
    const paginas = Math.max(1, Math.ceil(filas.length / porPagina));
    estado.pagina = Math.min(estado.pagina, paginas);
    const inicio = (estado.pagina - 1) * porPagina;
    const pagina = filas.slice(inicio, inicio + porPagina);

    const envoltura = document.createElement("div");
    envoltura.className = "tabla-contenedor";
    const tabla = document.createElement("table");
    tabla.className = "tabla";
    const cabecera = tabla.createTHead().insertRow();
    columnas.forEach((columna) => {
      const th = document.createElement("th");
      th.scope = "col";
      if (columna.ordenable === false) {
        th.textContent = columna.titulo;
      } else {
        const activo = estado.orden && estado.orden.clave === columna.clave;
        th.setAttribute("aria-sort", activo ? (estado.orden.direccion === "ASC" ? "ascending" : "descending") : "none");
        const boton = document.createElement("button");
        boton.type = "button";
        boton.title = "Ordenar ASC/DESC";
        boton.textContent = columna.titulo;
        const flecha = document.createElement("span");
        flecha.className = "flecha";
        flecha.textContent = activo ? (estado.orden.direccion === "ASC" ? "▲" : "▼") : "↕";
        boton.appendChild(flecha);
        boton.addEventListener("click", () => {
          const direccion = activo && estado.orden.direccion === "ASC" ? "DESC" : "ASC";
          estado.orden = { clave: columna.clave, direccion };
          if (opciones.alOrdenar) opciones.alOrdenar(estado.orden);
          dibujar(contenedor);
        });
        th.appendChild(boton);
      }
      cabecera.appendChild(th);
    });
    if (opciones.acciones) {
      const th = document.createElement("th");
      th.textContent = "Acciones";
      cabecera.appendChild(th);
    }

    const cuerpo = tabla.createTBody();
    const totalColumnas = columnas.length + (opciones.acciones ? 1 : 0);
    if (!pagina.length) {
      const celda = cuerpo.insertRow().insertCell();
      celda.colSpan = totalColumnas;
      celda.className = "tabla-vacia";
      celda.textContent = opciones.vacio || "No se encontraron registros para los filtros aplicados.";
    }
    let grupoAnterior;
    const conteoGrupos = new Map();
    if (opciones.grupo) {
      filas.forEach((fila) => {
        const grupo = opciones.grupo(fila);
        conteoGrupos.set(grupo, (conteoGrupos.get(grupo) || 0) + 1);
      });
    }
    pagina.forEach((fila) => {
      if (opciones.grupo) {
        const grupo = opciones.grupo(fila);
        if (grupo !== grupoAnterior) {
          const filaGrupo = cuerpo.insertRow();
          filaGrupo.className = "fila-grupo";
          const celda = filaGrupo.insertCell();
          celda.colSpan = totalColumnas;
          celda.textContent = `${grupo} (${conteoGrupos.get(grupo)})`;
          grupoAnterior = grupo;
        }
      }
      const tr = cuerpo.insertRow();
      columnas.forEach((columna) => {
        const td = tr.insertCell();
        if (["moneda", "numero", "rating"].includes(columna.tipo)) td.className = "numero";
        if (columna.etiqueta) {
          const valor = textoCelda(columna, fila);
          const etiqueta = document.createElement("span");
          etiqueta.className = `etiqueta ${columna.etiqueta(valorCelda(columna, fila), fila) || ""}`;
          etiqueta.textContent = valor;
          td.appendChild(etiqueta);
        } else {
          td.textContent = textoCelda(columna, fila);
        }
      });
      if (opciones.acciones) {
        const td = tr.insertCell();
        td.className = "acciones";
        opciones.acciones(fila).forEach((elemento) => td.appendChild(elemento));
      }
      if (opciones.alClic) {
        tr.classList.add("clicable");
        tr.tabIndex = 0;
        tr.addEventListener("click", (evento) => {
          if (!evento.target.closest("button")) opciones.alClic(fila);
        });
        tr.addEventListener("keydown", (evento) => {
          if (evento.key === "Enter") opciones.alClic(fila);
        });
      }
    });
    envoltura.appendChild(tabla);

    const pie = document.createElement("div");
    pie.className = "tabla-pie";
    const resumen = document.createElement("span");
    const totalTexto = opciones.totalServidor !== undefined ? opciones.totalServidor : filas.length;
    resumen.textContent = filas.length
      ? `Mostrando ${inicio + 1}–${inicio + pagina.length} de ${Util.numero(filas.length)} registros${
          totalTexto !== filas.length ? ` (total en servidor: ${Util.numero(totalTexto)})` : ""
        }`
      : "0 registros";
    pie.appendChild(resumen);
    if (paginas > 1) {
      const controles = document.createElement("div");
      controles.className = "paginacion";
      const anterior = document.createElement("button");
      anterior.type = "button";
      anterior.className = "btn btn-secundario btn-chico";
      anterior.textContent = "Anterior";
      anterior.disabled = estado.pagina === 1;
      anterior.addEventListener("click", () => {
        estado.pagina -= 1;
        dibujar(contenedor);
      });
      const indicador = document.createElement("span");
      indicador.textContent = `Página ${estado.pagina} de ${paginas}`;
      const siguiente = document.createElement("button");
      siguiente.type = "button";
      siguiente.className = "btn btn-secundario btn-chico";
      siguiente.textContent = "Siguiente";
      siguiente.disabled = estado.pagina === paginas;
      siguiente.addEventListener("click", () => {
        estado.pagina += 1;
        dibujar(contenedor);
      });
      controles.append(anterior, indicador, siguiente);
      pie.appendChild(controles);
    }
    contenedor.replaceChildren(envoltura, pie);
  }

  function mensaje(contenedor, texto, tipo = "error") {
    if (typeof contenedor === "string") contenedor = document.getElementById(contenedor);
    if (!contenedor) return;
    const caja = document.createElement("div");
    caja.className = `mensaje mensaje-${tipo}`;
    caja.textContent = texto;
    contenedor._tabla = null;
    contenedor.replaceChildren(caja);
  }

  function cargando(contenedor) {
    if (typeof contenedor === "string") contenedor = document.getElementById(contenedor);
    if (!contenedor) return;
    const caja = document.createElement("div");
    caja.className = "tabla-vacia";
    caja.innerHTML = '<span class="spinner" aria-hidden="true"></span> Consultando...';
    contenedor.replaceChildren(caja);
  }

  return { render, filtrar, mensaje, cargando };
})();

const Indicadores = (id, elementos) => {
  const contenedor = document.getElementById(id);
  if (!contenedor) return;
  contenedor.replaceChildren(
    ...elementos.map(({ titulo, valor, tipo }) => {
      const caja = document.createElement("div");
      caja.className = `indicador ${tipo || ""}`;
      const etiqueta = document.createElement("span");
      etiqueta.textContent = titulo;
      const dato = document.createElement("strong");
      dato.textContent = valor;
      dato.title = valor;
      caja.append(etiqueta, dato);
      return caja;
    })
  );
};

const VisorPdf = (() => {
  let urlActual = null;
  let nombreActual = "reporte.pdf";
  let solicitudActual = 0;

  function elementos() {
    return {
      modal: document.getElementById("modal-pdf"),
      visor: document.getElementById("visor-pdf"),
      cargando: document.getElementById("pdf-cargando"),
      estado: document.getElementById("pdf-estado"),
      descargar: document.getElementById("btn-pdf-descargar"),
      imprimir: document.getElementById("btn-pdf-imprimir"),
      titulo: document.getElementById("modal-pdf-titulo"),
    };
  }

  function liberar() {
    const { visor } = elementos();
    solicitudActual += 1;
    visor.removeAttribute("src");
    if (urlActual) URL.revokeObjectURL(urlActual);
    urlActual = null;
  }

  async function abrir(tipo, parametros, titulo) {
    const ui = elementos();
    liberar();
    solicitudActual += 1;
    const solicitud = solicitudActual;
    nombreActual = `reporte_${tipo}${parametros && parametros.subtipo ? "_" + parametros.subtipo : ""}.pdf`;
    ui.titulo.textContent = `Vista previa: ${titulo || tipo}`;
    ui.cargando.hidden = false;
    ui.cargando.innerHTML = '<span><span class="spinner" aria-hidden="true"></span> Generando PDF...</span>';
    ui.estado.textContent = "";
    ui.descargar.disabled = true;
    ui.imprimir.disabled = true;
    if (!ui.modal.open) ui.modal.showModal();
    try {
      const blob = await Api.pdf(tipo, parametros);
      if (solicitud !== solicitudActual || !ui.modal.open) return;
      if (blob.type && !blob.type.includes("pdf")) throw new Error("El servidor no devolvió un PDF.");
      urlActual = URL.createObjectURL(blob);
      ui.visor.src = urlActual;
      ui.cargando.hidden = true;
      ui.estado.textContent = `${nombreActual} · ${(blob.size / 1024).toFixed(1)} KB`;
      ui.descargar.disabled = false;
      ui.imprimir.disabled = false;
    } catch (error) {
      if (solicitud !== solicitudActual) return;
      ui.cargando.textContent = `No se pudo generar el PDF: ${error.message}`;
    }
  }

  async function descargar() {
    if (!urlActual) return;
    const confirmado = await Confirmar({
      titulo: "Confirmar descarga",
      texto: `Se descargará el archivo "${nombreActual}". La generación del reporte quedó registrada en la auditoría.`,
      boton: "Descargar",
    });
    if (!confirmado) return;
    const enlace = document.createElement("a");
    enlace.href = urlActual;
    enlace.download = nombreActual;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
    Notificar("Descarga iniciada.", "exito");
  }

  async function imprimir() {
    if (!urlActual) return;
    const confirmado = await Confirmar({
      titulo: "Confirmar impresión",
      texto: `Se enviará "${nombreActual}" al cuadro de impresión del navegador.`,
      boton: "Imprimir",
    });
    if (!confirmado) return;
    const { visor } = elementos();
    try {
      visor.contentWindow.focus();
      visor.contentWindow.print();
    } catch (error) {
      window.open(urlActual, "_blank", "noopener");
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const ui = elementos();
    if (!ui.modal) return;
    ui.descargar.addEventListener("click", descargar);
    ui.imprimir.addEventListener("click", imprimir);
    ui.modal.querySelector("[data-cerrar]").addEventListener("click", () => {
      ui.modal.close();
      liberar();
    });
    ui.modal.addEventListener("close", liberar);
  });

  return { abrir };
})();

const Reportes = (() => {
  const $ = (id) => document.getElementById(id);
  const valor = (id) => ($(id) ? $(id).value.trim() : "");
  let empleadosCache = null;
  let empleadoSeleccionado = null;

  function avisarError(contenedores, error) {
    contenedores.forEach((id) => Tabla.mensaje(id, error.message));
    Notificar(error.message, "error");
  }

  async function listaEmpleados() {
    if (!empleadosCache) {
      const datos = await Api.get(Api.RUTAS.empleados, { orden: "ASC" });
      empleadosCache = Api.listaDesde(datos, "empleados");
    }
    return empleadosCache;
  }

  function invalidarEmpleados() {
    empleadosCache = null;
  }

  const COLUMNAS_EMPLEADO = [
    { clave: "codigo_personal", titulo: "Código" },
    { clave: "nombre_completo", titulo: "Nombre completo" },
    { clave: "dependencia", titulo: "Dependencia" },
    { clave: "cargo", titulo: "Cargo" },
    { clave: "fecha_ingreso", titulo: "Fecha ingreso", tipo: "fecha" },
    { clave: "salario", titulo: "Salario", tipo: "moneda" },
  ];

  async function nomina() {
    const modalidad = valor("nomina-modalidad");
    const orden = valor("nomina-orden");
    Tabla.cargando("tabla-nomina");
    const [empleados, torta, barras] = await Promise.allSettled([
      Api.get(Api.RUTAS.empleados, { orden, modalidad }),
      Api.get(Api.RUTAS.reporteDependencias),
      Api.get(Api.RUTAS.reporteDependenciasCargos),
    ]);
    if (empleados.status === "rejected") {
      avisarError(["tabla-nomina"], empleados.reason);
      return;
    }
    const filas = Api.listaDesde(empleados.value, "empleados");
    const total = empleados.value.total ?? filas.length;
    const porDependencia = torta.status === "fulfilled" ? Api.listaDesde(torta.value, "grafico_torta", "dependencias") : [];
    const porCargo = barras.status === "fulfilled" ? Api.listaDesde(barras.value, "grafico_barras", "dependencias_cargos") : [];
    Indicadores("indicadores-nomina", [
      { titulo: "Total de empleados", valor: Util.numero(total) },
      { titulo: "Dependencias", valor: Util.numero(Util.contarDistintos(filas, "dependencia")), tipo: "acento" },
      { titulo: "Cargos", valor: Util.numero(Util.contarDistintos(filas, "cargo")), tipo: "acento" },
      { titulo: "Suma de salarios", valor: Util.moneda(Util.sumar(filas, "salario")), tipo: "exito" },
    ]);
    if (porDependencia.length) {
      Graficos.torta(
        "grafico-nomina-torta",
        porDependencia.map((f) => f.dependencia ?? "Sin dependencia"),
        porDependencia.map((f) => Number(f.total ?? f.cantidad ?? 0))
      );
    } else {
      Graficos.sinDatos("grafico-nomina-torta", torta.status === "rejected" ? torta.reason.message : undefined);
    }
    if (porCargo.length) {
      Graficos.comparativo("grafico-nomina-barras", porCargo, "dependencia", "cargo", "total", { ejeY: "Empleados", apiladas: true });
    } else {
      Graficos.sinDatos("grafico-nomina-barras", barras.status === "rejected" ? barras.reason.message : undefined);
    }
    const grupos = {
      general: null,
      por_dependencia: (f) => `Dependencia: ${f.dependencia ?? "Sin dependencia"}`,
      por_cargo_dependencia: (f) => `${f.dependencia ?? "Sin dependencia"} / ${f.cargo ?? "Sin cargo"}`,
    };
    const titulos = {
      general: "Listado general de empleados",
      por_dependencia: "Empleados agrupados por dependencia",
      por_cargo_dependencia: "Empleados agrupados por dependencia y cargo",
    };
    $("titulo-nomina-listado").textContent = titulos[modalidad];
    Tabla.render("tabla-nomina", COLUMNAS_EMPLEADO, filas, {
      grupo: grupos[modalidad],
      ordenInicial: { clave: "nombre_completo", direccion: orden },
      totalServidor: total,
    });
    Tabla.filtrar("tabla-nomina", valor("nomina-buscar"));
    const tarjetaConteo = $("tarjeta-nomina-conteo");
    if (modalidad === "general") {
      tarjetaConteo.hidden = true;
    } else {
      tarjetaConteo.hidden = false;
      const esDependencia = modalidad === "por_dependencia";
      $("titulo-nomina-conteo").textContent = esDependencia ? "Conteo por dependencia" : "Conteo por dependencia y cargo";
      const columnas = esDependencia
        ? [
            { clave: "dependencia", titulo: "Dependencia" },
            { clave: "total", titulo: "Empleados", tipo: "numero" },
          ]
        : [
            { clave: "dependencia", titulo: "Dependencia" },
            { clave: "cargo", titulo: "Cargo" },
            { clave: "total", titulo: "Empleados", tipo: "numero" },
          ];
      Tabla.render("tabla-nomina-conteo", columnas, esDependencia ? porDependencia : porCargo, {
        ordenInicial: { clave: "dependencia", direccion: "ASC" },
      });
    }
  }

  async function prepararPersonal() {
    try {
      const empleados = await listaEmpleados();
      $("lista-empleados").replaceChildren(
        ...empleados.map((e) => {
          const opcion = document.createElement("option");
          opcion.value = `${e.codigo_personal} - ${e.nombre_completo}`;
          return opcion;
        })
      );
    } catch (error) {
      Notificar(error.message, "error");
    }
  }

  async function personal() {
    const texto = valor("personal-empleado");
    if (!texto) {
      Tabla.mensaje("tabla-personal-novedades", "Seleccione un empleado de la lista.", "aviso");
      return;
    }
    let empleados;
    try {
      empleados = await listaEmpleados();
    } catch (error) {
      avisarError(["tabla-personal-novedades"], error);
      return;
    }
    const codigo = texto.split(" - ")[0].trim().toLowerCase();
    const encontrado =
      empleados.find((e) => String(e.codigo_personal).toLowerCase() === codigo) ||
      empleados.find((e) => String(e.nombre_completo || "").toLowerCase().includes(texto.toLowerCase()));
    if (!encontrado) {
      Tabla.mensaje("tabla-personal-novedades", "No existe un empleado con ese código o nombre.", "aviso");
      return;
    }
    Tabla.cargando("tabla-personal-novedades");
    try {
      const datos = await Api.get(Api.RUTAS.reporteEmpleado(encontrado.id_empleado));
      empleadoSeleccionado = { ...encontrado, ...datos };
      const ficha = [
        ["Código Personal", datos.codigo_personal],
        ["Nombre completo", datos.nombre_completo],
        ["Dependencia", datos.dependencia],
        ["Cargo", datos.cargo],
        ["Fecha de ingreso", Util.fecha(datos.fecha_ingreso)],
        ["EPS", datos.eps],
        ["Fondo de pensión", datos.fondo_pension],
        ["Aporte Pensión", Util.moneda(datos.aporte_pension)],
        ["Salario", Util.moneda(datos.salario)],
      ].filter(([, v]) => !Util.vacio(v));
      $("ficha-empleado").replaceChildren(
        ...ficha.map(([titulo, dato]) => {
          const caja = document.createElement("div");
          const etiqueta = document.createElement("span");
          etiqueta.textContent = titulo;
          const fuerte = document.createElement("strong");
          fuerte.textContent = dato;
          caja.append(etiqueta, fuerte);
          return caja;
        })
      );
      const novedades = Api.listaDesde(datos, "novedades");
      $("total-novedades-empleado").textContent = `${novedades.length} novedades`;
      const columnas = Util.columnasPresentes(novedades, [
        { clave: "periodo_fecha", titulo: "Período", tipo: "fecha" },
        { clave: "fecha_inicio", titulo: "Fecha inicio", tipo: "fecha", opcional: true },
        { clave: "fecha_fin", titulo: "Fecha fin", tipo: "fecha", opcional: true },
        { clave: "tipo_novedad", titulo: "Tipo de novedad" },
        { clave: "detalle", claves: ["detalle", "descripcion"], titulo: "Detalle" },
        { clave: "dias_reportados", titulo: "Días", tipo: "numero" },
        { clave: "valor", titulo: "Valor", tipo: "moneda", opcional: true },
      ]);
      Tabla.render("tabla-personal-novedades", columnas, novedades, {
        vacio: "El empleado no registra novedades.",
      });
    } catch (error) {
      empleadoSeleccionado = null;
      avisarError(["tabla-personal-novedades"], error);
    }
  }

  async function salud() {
    const orden = valor("salud-orden");
    Tabla.cargando("tabla-cargo-eps");
    Tabla.cargando("tabla-cargo-pension");
    const [metricas, eps, pension] = await Promise.allSettled([
      Api.get(Api.RUTAS.reporteSaludPension),
      Api.get(Api.RUTAS.reporteCargoEps, { orden }),
      Api.get(Api.RUTAS.reporteCargoPension, { orden }),
    ]);
    if (metricas.status === "fulfilled") {
      const m = metricas.value;
      Graficos.frecuencia("grafico-eps", Api.listaDesde(m.frecuencias_eps), "entidad", "total", { ejeY: "Empleados", serie: "Empleados" });
      Graficos.frecuencia("grafico-pension", Api.listaDesde(m.frecuencias_pension), "entidad", "total", {
        ejeY: "Empleados",
        serie: "Empleados",
        color: "#e8a33d",
      });
      Graficos.comparativo("grafico-eps-dependencia", Api.listaDesde(m.eps_por_dependencia), "dependencia", "entidad", "total", {
        ejeY: "Empleados",
      });
      Graficos.comparativo(
        "grafico-pension-dependencia",
        Api.listaDesde(m.pension_por_dependencia),
        "dependencia",
        "entidad",
        "total",
        { ejeY: "Empleados" }
      );
    } else {
      ["grafico-eps", "grafico-pension", "grafico-eps-dependencia", "grafico-pension-dependencia"].forEach((id) =>
        Graficos.sinDatos(id, metricas.reason.message)
      );
      Notificar(metricas.reason.message, "error");
    }
    const pintar = (resultado, id, idTotal, titulo) => {
      if (resultado.status === "rejected") {
        Tabla.mensaje(id, resultado.reason.message);
        return;
      }
      const filas = Api.listaDesde(resultado.value, "empleados");
      $(idTotal).textContent = `${filas.length} empleados`;
      Tabla.render(
        id,
        [
          { clave: "cargo", titulo: "Cargo" },
          { clave: "entidad", titulo },
          { clave: "codigo_personal", titulo: "Código" },
          { clave: "nombre_completo", titulo: "Empleado" },
        ],
        filas,
        {
          grupo: (f) => `${f.cargo ?? "Sin cargo"} / ${f.entidad ?? "Sin entidad"}`,
          ordenInicial: { clave: "nombre_completo", direccion: orden },
        }
      );
    };
    pintar(eps, "tabla-cargo-eps", "total-cargo-eps", "EPS");
    pintar(pension, "tabla-cargo-pension", "total-cargo-pension", "Fondo de pensión");
  }

  function rangoNovedades() {
    const f1 = valor("novedades-f1");
    const f2 = valor("novedades-f2");
    if (!Util.mesAnioValido(f1) || !Util.mesAnioValido(f2)) {
      throw new Error("F1 y F2 deben tener el formato MM/AAAA, por ejemplo 03/2022.");
    }
    if (Util.mesAnioComparable(f1) > Util.mesAnioComparable(f2)) {
      throw new Error("F1 no puede ser posterior a F2.");
    }
    return { f1, f2 };
  }

  async function novedades() {
    const caja = $("novedades-mensaje");
    caja.hidden = true;
    let rango;
    try {
      rango = rangoNovedades();
    } catch (error) {
      caja.textContent = error.message;
      caja.className = "mensaje mensaje-error";
      caja.hidden = false;
      return;
    }
    const orden = valor("novedades-orden");
    Tabla.cargando("tabla-novedades");
    try {
      const datos = await Api.get(Api.RUTAS.reporteNovedades, { ...rango, orden });
      const listado = Api.listaDesde(datos, "empleados_con_novedades", "novedades");
      const conteo = Api.listaDesde(datos, "conteo_dependencia_cargo", "conteo");
      Indicadores("indicadores-novedades", [
        { titulo: "Novedades en el rango", valor: Util.numero(listado.length) },
        { titulo: "Empleados con novedades", valor: Util.numero(Util.contarDistintos(listado, "codigo_personal")), tipo: "acento" },
        { titulo: "Dependencias", valor: Util.numero(Util.contarDistintos(conteo, "dependencia")), tipo: "acento" },
        { titulo: "Rango", valor: `${rango.f1} – ${rango.f2}`, tipo: "exito" },
      ]);
      Graficos.comparativo("grafico-novedades", conteo, "dependencia", "cargo", "total", { ejeY: "Novedades", apiladas: true });
      Tabla.render(
        "tabla-novedades-conteo",
        [
          { clave: "dependencia", titulo: "Dependencia" },
          { clave: "cargo", titulo: "Cargo" },
          { clave: "total", titulo: "Novedades", tipo: "numero" },
        ],
        conteo,
        { ordenInicial: { clave: "dependencia", direccion: "ASC" } }
      );
      const columnas = Util.columnasPresentes(listado, [
        { clave: "codigo_personal", titulo: "Código" },
        { clave: "nombre_completo", titulo: "Empleado" },
        { clave: "dependencia", titulo: "Dependencia" },
        { clave: "cargo", titulo: "Cargo" },
        { clave: "periodo_fecha", titulo: "Período", tipo: "fecha" },
        { clave: "fecha_inicio", titulo: "Fecha inicio", tipo: "fecha", opcional: true },
        { clave: "fecha_fin", titulo: "Fecha fin", tipo: "fecha", opcional: true },
        { clave: "tipo_novedad", titulo: "Tipo" },
        { clave: "detalle", claves: ["detalle", "descripcion"], titulo: "Detalle" },
        { clave: "dias_reportados", titulo: "Días", tipo: "numero" },
        { clave: "valor", titulo: "Valor", tipo: "moneda", opcional: true },
      ]);
      Tabla.render("tabla-novedades", columnas, listado, {
        grupo: (f) => `${f.dependencia ?? "Sin dependencia"} / ${f.cargo ?? "Sin cargo"}`,
        ordenInicial: { clave: "nombre_completo", direccion: orden },
        vacio: "No hay empleados con novedades en el rango indicado.",
      });
    } catch (error) {
      Graficos.sinDatos("grafico-novedades", error.message);
      avisarError(["tabla-novedades", "tabla-novedades-conteo"], error);
    }
  }

  function rangoFechas(idF1, idF2) {
    const f1 = valor(idF1);
    const f2 = valor(idF2);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(f1) || !/^\d{4}-\d{2}-\d{2}$/.test(f2)) {
      throw new Error("F1 y F2 deben tener el formato YYYY-MM-DD.");
    }
    if (f1 > f2) throw new Error("F1 no puede ser posterior a F2.");
    return { f1, f2 };
  }

  async function peliculasGenero() {
    let rango;
    try {
      rango = rangoFechas("pg-f1", "pg-f2");
    } catch (error) {
      Tabla.mensaje("tabla-peliculas-genero", error.message, "aviso");
      return;
    }
    const orden = valor("pg-orden");
    const genero = valor("pg-genero");
    Tabla.cargando("tabla-peliculas-genero");
    $("rango-peliculas-genero").textContent = `${Util.fecha(rango.f1)} a ${Util.fecha(rango.f2)}`;
    const [listado, frecuencia] = await Promise.allSettled([
      Api.get(Api.RUTAS.peliculasGeneroFechas, { ...rango, orden, genero }),
      Api.get(Api.RUTAS.graficoPeliculasGenero, rango),
    ]);
    let filasFrecuencia = frecuencia.status === "fulfilled" ? Api.listaDesde(frecuencia.value, "generos", "frecuencias") : [];
    if (listado.status === "fulfilled") {
      const filas = Api.listaDesde(listado.value, "peliculas");
      if (!filasFrecuencia.length && !genero) {
        const conteo = new Map();
        filas.forEach((f) => conteo.set(f.genero, (conteo.get(f.genero) || 0) + 1));
        filasFrecuencia = [...conteo].map(([g, total]) => ({ genero: g, total }));
      }
      $("total-peliculas-genero").textContent = `${Util.numero(listado.value.total ?? filas.length)} registros`;
      Tabla.render(
        "tabla-peliculas-genero",
        [
          { clave: "genero", titulo: "Género" },
          { clave: "titulo", titulo: "Película" },
          { clave: "fecha_estreno", titulo: "Fecha de estreno", tipo: "fecha" },
        ],
        filas,
        { grupo: (f) => f.genero ?? "Sin género", ordenInicial: { clave: "titulo", direccion: orden } }
      );
    } else {
      avisarError(["tabla-peliculas-genero"], listado.reason);
    }
    if (filasFrecuencia.length) {
      filasFrecuencia.sort((a, b) => Number(b.total) - Number(a.total));
      Graficos.frecuencia("grafico-peliculas-genero", filasFrecuencia, "genero", "total", {
        ejeY: "Películas",
        serie: "Películas",
      });
      const selector = $("pg-genero");
      const seleccionado = selector.value;
      const opciones = filasFrecuencia
        .map((f) => f.genero)
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b, "es"));
      selector.replaceChildren(
        new Option("Todos los géneros", ""),
        ...opciones.map((g) => new Option(g, g, false, g === seleccionado))
      );
    } else {
      Graficos.sinDatos("grafico-peliculas-genero", frecuencia.status === "rejected" ? frecuencia.reason.message : undefined);
    }
  }

  async function peliculasNGeneros() {
    const n = Number(valor("ng-n"));
    const orden = valor("ng-orden");
    if (!Number.isInteger(n) || n < 1) {
      Tabla.mensaje("tabla-n-generos", "N debe ser un entero mayor o igual a 1.", "aviso");
      return;
    }
    $("titulo-n-generos").textContent = `Películas con exactamente ${n} ${n === 1 ? "género" : "géneros"}`;
    Tabla.cargando("tabla-n-generos");
    try {
      const datos = await Api.get(Api.RUTAS.peliculasNGeneros, { n, orden });
      const filas = Api.listaDesde(datos, "peliculas");
      const total = datos.total ?? filas.length;
      Indicadores("indicadores-n-generos", [
        { titulo: "Conteo total de películas", valor: Util.numero(total) },
        { titulo: "Géneros por película (N)", valor: String(n), tipo: "acento" },
      ]);
      const columnas = Util.columnasPresentes(filas, [
        { clave: "id_pelicula", titulo: "ID" },
        { clave: "titulo", titulo: "Película" },
        { clave: "fecha_estreno", titulo: "Fecha de estreno", tipo: "fecha" },
        { clave: "generos", titulo: "Géneros" },
        { clave: "cantidad_generos", titulo: "Cantidad", tipo: "numero" },
      ]);
      Tabla.render("tabla-n-generos", columnas, filas, {
        ordenInicial: { clave: "titulo", direccion: orden },
        totalServidor: total,
      });
    } catch (error) {
      avisarError(["tabla-n-generos"], error);
    }
  }

  const COLUMNAS_LIBRO = [
    { clave: "titulo", titulo: "Título" },
    { clave: "autor", titulo: "Autor" },
    { clave: "rating", titulo: "Rating", tipo: "rating" },
    { clave: "numero_resenas", titulo: "Reseñas", tipo: "numero" },
    { clave: "anio_publicacion", titulo: "Año" },
  ];

  async function topLibros() {
    const n = Number(valor("tl-n"));
    const orden = valor("tl-orden");
    if (!Number.isInteger(n) || n < 1) {
      Tabla.mensaje("tabla-top-libros", "N debe ser un entero mayor o igual a 1.", "aviso");
      return;
    }
    $("titulo-top-libros").textContent = `Top ${n} libros con mejor rating`;
    Tabla.cargando("tabla-top-libros");
    try {
      const datos = await Api.get(Api.RUTAS.topLibros, { n, orden });
      const filas = Api.listaDesde(datos, "libros");
      Tabla.render("tabla-top-libros", Util.columnasPresentes(filas, COLUMNAS_LIBRO), filas, {
        ordenInicial: { clave: "titulo", direccion: orden },
      });
      const grafico = filas.slice(0, 25);
      Graficos.barras(
        "grafico-top-libros",
        grafico.map((f) => (String(f.titulo).length > 38 ? String(f.titulo).slice(0, 36) + "…" : f.titulo)),
        [{ etiqueta: "Rating", valores: grafico.map((f) => Number(f.rating)) }],
        { horizontal: true, ejeX: "Rating" }
      );
    } catch (error) {
      Graficos.sinDatos("grafico-top-libros", error.message);
      avisarError(["tabla-top-libros"], error);
    }
  }

  async function top5Anio() {
    let rango;
    try {
      rango = rangoFechas("t5-f1", "t5-f2");
    } catch (error) {
      Tabla.mensaje("tabla-top5-mejores", error.message, "aviso");
      return;
    }
    const orden = valor("t5-orden");
    $("rango-libros-anio").textContent = `${Util.fecha(rango.f1)} a ${Util.fecha(rango.f2)}`;
    Tabla.cargando("tabla-top5-mejores");
    Tabla.cargando("tabla-top5-peores");
    const [top, frecuencia] = await Promise.allSettled([
      Api.get(Api.RUTAS.top5LibrosAnio, { ...rango, orden }),
      Api.get(Api.RUTAS.graficoLibrosAnio, rango),
    ]);
    if (frecuencia.status === "fulfilled") {
      const filas = Api.listaDesde(frecuencia.value, "anios", "frecuencias");
      Graficos.frecuencia("grafico-libros-anio", filas, filas.length && filas[0].anio !== undefined ? "anio" : "anio_publicacion", "total", {
        ejeY: "Libros",
        ejeX: "Año de publicación",
        serie: "Libros",
        color: "#3a7ca5",
      });
    } else {
      Graficos.sinDatos("grafico-libros-anio", frecuencia.reason.message);
    }
    if (top.status === "rejected") {
      avisarError(["tabla-top5-mejores", "tabla-top5-peores"], top.reason);
      return;
    }
    const columnas = [
      { clave: "anio_publicacion", titulo: "Año" },
      { clave: "titulo", titulo: "Título" },
      { clave: "autor", titulo: "Autor" },
      { clave: "rating", titulo: "Rating", tipo: "rating" },
    ];
    const pintar = (filas, id, idTotal) => {
      $(idTotal).textContent = `${Util.numero(filas.length)} libros`;
      Tabla.render(id, columnas, filas, {
        grupo: (f) => `Año ${f.anio_publicacion ?? "sin dato"}`,
        ordenInicial: { clave: "titulo", direccion: orden },
        porPagina: 60,
      });
    };
    pintar(Api.listaDesde(top.value, "mejores"), "tabla-top5-mejores", "total-top5-mejores");
    pintar(Api.listaDesde(top.value, "peores"), "tabla-top5-peores", "total-top5-peores");
  }

  const SUBPANELES = {
    peliculas_genero_fechas: peliculasGenero,
    peliculas_n_generos: peliculasNGeneros,
    top_n_libros: topLibros,
    top_5_libros_anio: top5Anio,
  };
  const subpanelesCargados = new Set();

  function subpanelActivo() {
    const activa = document.querySelector('[data-vista="entretenimiento"] .pestana.activa');
    return activa ? activa.dataset.panel : "peliculas_genero_fechas";
  }

  function mostrarSubpanel(nombre) {
    document.querySelectorAll('[data-vista="entretenimiento"] .pestana').forEach((pestana) => {
      const activa = pestana.dataset.panel === nombre;
      pestana.classList.toggle("activa", activa);
      pestana.setAttribute("aria-selected", String(activa));
    });
    document.querySelectorAll("[data-subpanel]").forEach((panel) => {
      panel.hidden = panel.dataset.subpanel !== nombre;
    });
    if (!subpanelesCargados.has(nombre)) {
      subpanelesCargados.add(nombre);
      SUBPANELES[nombre]();
    }
  }

  function entretenimiento() {
    subpanelesCargados.add(subpanelActivo());
    return SUBPANELES[subpanelActivo()]();
  }

  function parametrosPdf(tipo) {
    switch (tipo) {
      case "nomina":
        return { parametros: { modalidad: valor("nomina-modalidad"), orden: valor("nomina-orden") }, titulo: "Reporte de Nómina" };
      case "informacion_personal": {
        if (!empleadoSeleccionado) throw new Error("Primero consulte un empleado para generar su PDF.");
        return {
          parametros: { codigo_personal: empleadoSeleccionado.codigo_personal },
          titulo: `Información personal ${empleadoSeleccionado.codigo_personal}`,
        };
      }
      case "salud_pension":
        return { parametros: { orden: valor("salud-orden") }, titulo: "Reporte de Salud y Pensión" };
      case "novedades":
        return { parametros: { ...rangoNovedades(), orden: valor("novedades-orden") }, titulo: "Reporte de Novedades" };
      case "entretenimiento": {
        const subtipo = subpanelActivo();
        const nombres = {
          peliculas_genero_fechas: "Películas por género",
          peliculas_n_generos: "Películas con N géneros",
          top_n_libros: "Top N libros",
          top_5_libros_anio: "Top 5 libros por año",
        };
        const parametros = { subtipo };
        if (subtipo === "peliculas_genero_fechas") {
          const rango = rangoFechas("pg-f1", "pg-f2");
          Object.assign(parametros, { f1: Util.isoAMesAnio(rango.f1), f2: Util.isoAMesAnio(rango.f2), orden: valor("pg-orden") });
        } else if (subtipo === "peliculas_n_generos") {
          Object.assign(parametros, { n: valor("ng-n"), orden: valor("ng-orden") });
        } else if (subtipo === "top_n_libros") {
          Object.assign(parametros, { n: valor("tl-n"), orden: valor("tl-orden") });
        } else {
          Object.assign(parametros, { orden: valor("t5-orden") });
        }
        return { parametros, titulo: nombres[subtipo] };
      }
      default:
        throw new Error("Reporte no reconocido.");
    }
  }

  function abrirPdf(tipo) {
    try {
      const { parametros, titulo } = parametrosPdf(tipo);
      VisorPdf.abrir(tipo, parametros, titulo);
    } catch (error) {
      Notificar(error.message, "error");
    }
  }

  const CONSULTAS = {
    nomina,
    personal,
    salud,
    novedades,
    entretenimiento,
  };

  function enlazar() {
    const formularios = {
      "filtros-nomina": nomina,
      "filtros-personal": personal,
      "filtros-salud": salud,
      "filtros-novedades": novedades,
      "filtros-peliculas-genero": peliculasGenero,
      "filtros-n-generos": peliculasNGeneros,
      "filtros-top-libros": topLibros,
      "filtros-top5": top5Anio,
    };
    Object.entries(formularios).forEach(([id, accion]) => {
      $(id).addEventListener("submit", (evento) => {
        evento.preventDefault();
        accion();
      });
    });
    $("nomina-buscar").addEventListener("input", (evento) => Tabla.filtrar("tabla-nomina", evento.target.value));
    $("nomina-modalidad").addEventListener("change", nomina);
    $("nomina-orden").addEventListener("change", nomina);
    $("personal-empleado").addEventListener("change", personal);
    document.querySelectorAll("[data-pdf]").forEach((boton) => {
      boton.addEventListener("click", () => abrirPdf(boton.dataset.pdf));
    });
    document.querySelectorAll('[data-vista="entretenimiento"] .pestana').forEach((pestana) => {
      pestana.addEventListener("click", () => mostrarSubpanel(pestana.dataset.panel));
    });
    ["novedades-f1", "novedades-f2"].forEach((id) => {
      $(id).addEventListener("input", (evento) => {
        let texto = evento.target.value.replace(/[^\d]/g, "").slice(0, 6);
        if (texto.length > 2) texto = `${texto.slice(0, 2)}/${texto.slice(2)}`;
        evento.target.value = texto;
      });
    });
  }

  function alMostrar(nombre) {
    if (nombre === "personal") prepararPersonal();
  }

  return { CONSULTAS, enlazar, alMostrar, invalidarEmpleados, abrirPdf };
})();

const Panel = (() => {
  const consultados = new Set();
  let vistaActual = null;

  function marcarMenu(nombre) {
    document.querySelectorAll(".nav-item").forEach((item) => {
      const activo = item.dataset.ir === nombre;
      item.classList.toggle("activo", activo);
      if (activo) item.setAttribute("aria-current", "page");
      else item.removeAttribute("aria-current");
    });
  }

  async function mostrar(nombre) {
    const boton = document.querySelector(`.nav-item[data-ir="${nombre}"]`);
    if (!boton) nombre = "nomina";
    const item = document.querySelector(`.nav-item[data-ir="${nombre}"]`);
    vistaActual = nombre;
    marcarMenu(nombre);
    document.getElementById("menu-lateral").classList.remove("abierto");
    document.getElementById("btn-menu").setAttribute("aria-expanded", "false");
    document.querySelectorAll("[data-vista]").forEach((seccion) => {
      seccion.hidden = true;
    });
    if (history.replaceState) history.replaceState(null, "", `#${nombre}`);
    const plantilla = item.dataset.plantilla;
    if (plantilla) {
      const contenedor = document.getElementById("vista-dinamica");
      contenedor.hidden = false;
      contenedor.innerHTML = '<div class="tarjeta tabla-vacia"><span class="spinner" aria-hidden="true"></span> Cargando vista...</div>';
      try {
        const respuesta = await fetch(plantilla, { cache: "no-cache" });
        if (!respuesta.ok) throw new Error(`No se encontró la vista ${plantilla}`);
        const html = await respuesta.text();
        if (vistaActual !== nombre) return;
        contenedor.innerHTML = html;
        Vistas.iniciar(nombre, contenedor);
      } catch (error) {
        contenedor.innerHTML = "";
        const caja = document.createElement("div");
        caja.className = "mensaje mensaje-error";
        caja.textContent = `${error.message}. Abra el frontend con un servidor local (Live Server).`;
        contenedor.appendChild(caja);
      }
    } else {
      document.querySelector(`[data-vista="${nombre}"]`).hidden = false;
      Reportes.alMostrar(nombre);
      if (!consultados.has(nombre) && Reportes.CONSULTAS[nombre]) {
        consultados.add(nombre);
        if (nombre !== "personal") Reportes.CONSULTAS[nombre]();
      }
    }
    document.getElementById("contenido").scrollTo?.(0, 0);
    window.scrollTo(0, 0);
  }

  function iniciar() {
    const usuario = Auth.requerirSesion();
    if (!usuario) return;
    document.getElementById("usuario-nombre").textContent = usuario.username || "";
    document.getElementById("usuario-rol").textContent = usuario.rol || "";
    document.getElementById("btn-salir").addEventListener("click", async () => {
      const salir = await Confirmar({ titulo: "Cerrar sesión", texto: "¿Desea cerrar la sesión actual?", boton: "Cerrar sesión" });
      if (salir) Auth.cerrarSesion("salida");
    });
    const menu = document.getElementById("menu-lateral");
    const botonMenu = document.getElementById("btn-menu");
    botonMenu.addEventListener("click", () => {
      const abierto = menu.classList.toggle("abierto");
      botonMenu.setAttribute("aria-expanded", String(abierto));
    });
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.addEventListener("click", () => mostrar(item.dataset.ir));
    });
    Reportes.enlazar();
    mostrar((window.location.hash || "#nomina").slice(1));
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (document.querySelector(".app")) iniciar();
  });

  return { mostrar, recargar: (nombre) => consultados.delete(nombre) };
})();
