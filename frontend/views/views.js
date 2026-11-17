const Vistas = (() => {
  const EXTENSIONES = { xlsx: "XLSX", dat: "DAT", json: "JSON" };
  const TAMANO_MAXIMO = 25 * 1024 * 1024;
  const REPORTES_AFECTADOS = {
    empleados: ["nomina", "salud", "novedades", "personal"],
    "novedades-crud": ["novedades", "personal"],
    peliculas: ["entretenimiento"],
    libros: ["entretenimiento"],
  };

  function leerJson(texto, defecto) {
    try {
      return JSON.parse(texto);
    } catch (error) {
      return defecto;
    }
  }

  function boton(texto, clase, accion) {
    const elemento = document.createElement("button");
    elemento.type = "button";
    elemento.className = `btn btn-chico ${clase || ""}`;
    elemento.textContent = texto;
    elemento.addEventListener("click", accion);
    return elemento;
  }

  function mostrarMensaje(elemento, texto, tipo = "error") {
    if (!elemento) return;
    elemento.textContent = texto || "";
    elemento.classList.remove("mensaje-error", "mensaje-exito", "mensaje-aviso");
    elemento.classList.add("mensaje", `mensaje-${tipo}`);
    elemento.hidden = !texto;
  }

  function convertir(campo, crudo) {
    const texto = String(crudo ?? "").trim();
    const tipo = campo.dataset.tipo;
    if (texto === "") return campo.required ? texto : null;
    if (tipo === "entero") return parseInt(texto, 10);
    if (tipo === "decimal") return Number(texto);
    if (tipo === "lista") return texto.split(",").map((t) => t.trim()).filter(Boolean);
    if (campo.type === "month") return `${texto}-01`;
    return texto;
  }

  function valorParaCampo(campo, fila) {
    const claves = [campo.name, ...(campo.dataset.alias ? campo.dataset.alias.split(",") : [])];
    const valor = Util.valorDe(fila, ...claves);
    if (valor === undefined) return "";
    if (Array.isArray(valor)) return valor.join(", ");
    if (campo.type === "date") return Util.fechaIso(valor);
    if (campo.type === "month") return Util.fechaIso(valor).slice(0, 7);
    return String(valor);
  }

  function seleccionarPorTexto(select, texto) {
    if (Util.vacio(texto)) return;
    const opcion = [...select.options].find((o) => o.textContent.trim().toLowerCase() === String(texto).trim().toLowerCase());
    if (opcion) select.value = opcion.value;
  }

  async function poblarCatalogos(raiz) {
    const selects = [...raiz.querySelectorAll("select[data-catalogo]")];
    const desdeEmpleados = [...raiz.querySelectorAll("select[data-opciones-desde='empleados']")];
    if (selects.length) {
      try {
        const catalogos = await Api.get(Api.RUTAS.catalogos);
        selects.forEach((select) => {
          const lista = Api.listaDesde(catalogos[select.dataset.catalogo] || []);
          const idClave = select.dataset.id || "id";
          select.replaceChildren(
            new Option("Seleccione...", ""),
            ...lista.map((item) => new Option(item.nombre ?? item[select.dataset.textoClave] ?? "", item[idClave] ?? item.id))
          );
        });
      } catch (error) {
        Notificar(`Catálogos no disponibles: ${error.message}`, "error");
      }
    }
    if (desdeEmpleados.length) {
      try {
        const datos = await Api.get(Api.RUTAS.empleados, { orden: "ASC" });
        const empleados = Api.listaDesde(datos, "empleados");
        desdeEmpleados.forEach((select) => {
          const inicial = select.dataset.vacio || "Seleccione...";
          select.replaceChildren(
            new Option(inicial, ""),
            ...empleados.map((e) => new Option(`${e.codigo_personal} - ${e.nombre_completo}`, e.id_empleado))
          );
        });
      } catch (error) {
        Notificar(`No se pudo cargar la lista de empleados: ${error.message}`, "error");
      }
    }
  }

  function iniciarCrud(nombre, raiz) {
    const vista = raiz.querySelector("[data-recurso]");
    const recurso = vista.dataset.recurso;
    const item = vista.dataset.item;
    const clave = vista.dataset.clave;
    const listas = (vista.dataset.lista || recurso).split(",");
    const entidad = vista.dataset.entidad || "registro";
    const paginadoServidor = vista.dataset.paginado === "servidor";
    const limite = Number(vista.dataset.limite || 25);
    const tabla = vista.querySelector(".crud-tabla");
    const columnas = leerJson(tabla.dataset.columnas, []);
    const filtros = vista.querySelector(".crud-filtros");
    const modal = vista.querySelector(".crud-modal");
    const formulario = modal.querySelector("form");
    const mensaje = modal.querySelector(".crud-mensaje");
    const tituloModal = modal.querySelector(".crud-modal-titulo");
    const paginacion = vista.querySelector(".crud-paginacion");
    let pagina = 1;
    let editando = null;

    columnas.forEach((columna) => {
      if (columna.tipo === "lista") {
        columna.formato = (valor) => (Array.isArray(valor) ? valor.join(", ") : valor ?? "");
        columna.tipo = "texto";
      }
    });

    function parametros() {
      const datos = filtros ? Util.datosFormulario(filtros) : {};
      if (paginadoServidor) Object.assign(datos, { pagina, limite });
      return datos;
    }

    function pintarPaginacion(total) {
      if (!paginacion) return;
      const paginas = Math.max(1, Math.ceil(total / limite));
      paginacion.replaceChildren();
      if (!paginadoServidor) return;
      const texto = document.createElement("span");
      texto.textContent = `Página ${pagina} de ${Util.numero(paginas)} · ${Util.numero(total)} ${entidad === "libro" ? "libros" : "películas"}`;
      const anterior = boton("Anterior", "btn-secundario", () => {
        pagina -= 1;
        listar();
      });
      anterior.disabled = pagina <= 1;
      const siguiente = boton("Siguiente", "btn-secundario", () => {
        pagina += 1;
        listar();
      });
      siguiente.disabled = pagina >= paginas;
      paginacion.append(anterior, texto, siguiente);
    }

    async function listar() {
      Tabla.cargando(tabla);
      try {
        const datos = await Api.get(Api.RUTAS[recurso], parametros());
        const filas = Api.listaDesde(datos, ...listas);
        const total = Number((datos && datos.total) ?? filas.length);
        Tabla.render(tabla, columnas, filas, {
          porPagina: paginadoServidor ? limite : 50,
          totalServidor: total,
          acciones: (fila) => [
            boton("Editar", "btn-secundario", () => abrir(fila)),
            boton("Eliminar", "btn-peligro", () => eliminar(fila)),
          ],
        });
        pintarPaginacion(total);
      } catch (error) {
        Tabla.mensaje(tabla, error.message);
        if (paginacion) paginacion.replaceChildren();
      }
    }

    async function abrir(fila) {
      editando = fila || null;
      formulario.reset();
      mostrarMensaje(mensaje, "");
      tituloModal.textContent = fila ? `Editar ${entidad}` : `Crear ${entidad}`;
      formulario.querySelectorAll("[data-solo-crear]").forEach((campo) => {
        campo.disabled = Boolean(fila);
      });
      if (fila) {
        let completo = fila;
        try {
          const detalle = await Api.get(Api.RUTAS[item](fila[clave]));
          if (detalle && typeof detalle === "object" && !Array.isArray(detalle)) completo = { ...fila, ...detalle };
        } catch (error) {
          completo = fila;
        }
        formulario.querySelectorAll("[name]").forEach((campo) => {
          campo.value = valorParaCampo(campo, completo);
          if (campo.tagName === "SELECT" && !campo.value && campo.dataset.texto) {
            seleccionarPorTexto(campo, completo[campo.dataset.texto]);
          }
        });
      }
      modal.showModal();
      const primero = formulario.querySelector("input:not([disabled]), select:not([disabled])");
      if (primero) primero.focus();
    }

    async function guardar(evento) {
      evento.preventDefault();
      if (!formulario.reportValidity()) return;
      const cuerpo = {};
      formulario.querySelectorAll("[name]").forEach((campo) => {
        if (campo.disabled) return;
        cuerpo[campo.name] = convertir(campo, campo.value);
      });
      const enviar = formulario.querySelector('button[value="guardar"]');
      enviar.disabled = true;
      try {
        if (editando) {
          await Api.put(Api.RUTAS[item](editando[clave]), cuerpo);
          Notificar(`${entidad[0].toUpperCase()}${entidad.slice(1)} actualizado correctamente.`, "exito");
        } else {
          await Api.post(Api.RUTAS[recurso], cuerpo);
          Notificar(`${entidad[0].toUpperCase()}${entidad.slice(1)} creado correctamente.`, "exito");
        }
        modal.close();
        refrescarDependientes(nombre);
        listar();
      } catch (error) {
        mostrarMensaje(mensaje, error.message, "error");
      } finally {
        enviar.disabled = false;
      }
    }

    async function eliminar(fila) {
      const descripcion = fila.titulo || fila.nombre_completo || fila.tipo_novedad || `#${fila[clave]}`;
      const confirmado = await Confirmar({
        titulo: `Eliminar ${entidad}`,
        texto: `¿Desea eliminar "${descripcion}" (ID ${fila[clave]})? La operación queda registrada en la auditoría y no se puede deshacer.`,
        boton: "Eliminar",
        peligro: true,
      });
      if (!confirmado) return;
      try {
        await Api.eliminar(Api.RUTAS[item](fila[clave]));
        Notificar(`Registro ${fila[clave]} eliminado.`, "exito");
        refrescarDependientes(nombre);
        listar();
      } catch (error) {
        Notificar(error.message, "error");
      }
    }

    vista.querySelector(".crud-nuevo").addEventListener("click", () => abrir(null));
    formulario.addEventListener("submit", guardar);
    modal.querySelectorAll("[data-cerrar]").forEach((cerrar) => cerrar.addEventListener("click", () => modal.close()));
    if (filtros) {
      filtros.addEventListener("submit", (evento) => {
        evento.preventDefault();
        pagina = 1;
        listar();
      });
      filtros.addEventListener("reset", () => {
        setTimeout(() => {
          pagina = 1;
          listar();
        });
      });
    }
    poblarCatalogos(raiz).then(listar);
  }

  function refrescarDependientes(nombre) {
    (REPORTES_AFECTADOS[nombre] || []).forEach((reporte) => Panel.recargar(reporte));
    if (nombre === "empleados") Reportes.invalidarEmpleados();
  }

  function iniciarCarga(raiz) {
    const formulario = raiz.querySelector("#form-carga");
    const entrada = raiz.querySelector("#archivo-carga");
    const zona = raiz.querySelector("#zona-archivo");
    const detalle = raiz.querySelector("#archivo-detalle");
    const periodo = raiz.querySelector("#campo-periodo");
    const mensaje = raiz.querySelector("#carga-mensaje");
    const resultado = raiz.querySelector("#carga-resultado");
    const enviar = formulario.querySelector('button[type="submit"]');

    function tipoArchivo(archivo) {
      const extension = (archivo.name.split(".").pop() || "").toLowerCase();
      return EXTENSIONES[extension] || null;
    }

    function alElegir() {
      const archivo = entrada.files[0];
      mostrarMensaje(mensaje, "");
      if (!archivo) {
        detalle.textContent = "Ningún archivo seleccionado";
        periodo.hidden = true;
        return;
      }
      const tipo = tipoArchivo(archivo);
      detalle.textContent = `${archivo.name} · ${(archivo.size / 1024).toFixed(1)} KB${tipo ? ` · ${tipo}` : ""}`;
      periodo.hidden = tipo !== "XLSX";
      if (!tipo) mostrarMensaje(mensaje, "Formato no permitido. Solo se aceptan archivos .xlsx, .dat o .json.", "error");
      else if (archivo.size > TAMANO_MAXIMO) mostrarMensaje(mensaje, "El archivo supera el tamaño máximo de 25 MB.", "error");
    }

    entrada.addEventListener("change", alElegir);
    formulario.addEventListener("reset", () => {
      setTimeout(() => {
        alElegir();
        resultado.hidden = true;
      });
    });
    ["dragenter", "dragover"].forEach((tipo) =>
      zona.addEventListener(tipo, (evento) => {
        evento.preventDefault();
        zona.classList.add("sobre");
      })
    );
    ["dragleave", "drop"].forEach((tipo) =>
      zona.addEventListener(tipo, (evento) => {
        evento.preventDefault();
        zona.classList.remove("sobre");
      })
    );
    zona.addEventListener("drop", (evento) => {
      if (evento.dataTransfer.files.length) {
        entrada.files = evento.dataTransfer.files;
        alElegir();
      }
    });

    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      const archivo = entrada.files[0];
      if (!archivo) {
        mostrarMensaje(mensaje, "Seleccione un archivo para cargar.", "aviso");
        return;
      }
      const tipo = tipoArchivo(archivo);
      if (!tipo || archivo.size > TAMANO_MAXIMO) {
        alElegir();
        return;
      }
      const confirmado = await Confirmar({
        titulo: "Confirmar carga incremental",
        texto: `Se procesará "${archivo.name}" (${tipo}). Los registros existentes se actualizarán y los nuevos se insertarán sin duplicados.`,
        boton: "Cargar archivo",
      });
      if (!confirmado) return;
      const datos = new FormData();
      datos.append("archivo", archivo);
      datos.append("tipo", tipo);
      const mes = raiz.querySelector("#periodo-carga").value;
      if (tipo === "XLSX" && mes) datos.append("periodo_fecha", `${mes}-01`);
      enviar.disabled = true;
      enviar.innerHTML = '<span class="spinner" aria-hidden="true"></span> Procesando...';
      mostrarMensaje(mensaje, "Procesando el archivo. Las cargas grandes pueden tardar varios segundos.", "aviso");
      resultado.hidden = true;
      try {
        const r = await Api.subir(Api.RUTAS.cargaArchivo, datos);
        const errores = Api.listaDesde(r, "errores", "errores_carga");
        const procesados = Number(r.registros_procesados ?? 0);
        const insertados = Number(r.registros_insertados ?? r.registros_cargados ?? procesados - errores.length);
        const estado = r.estado || (errores.length ? (insertados ? "COMPLETADO_CON_ERRORES" : "FALLIDO") : "COMPLETADO");
        Indicadores("carga-indicadores", [
          { titulo: "Archivo", valor: r.nombre_archivo || archivo.name },
          { titulo: "Registros procesados", valor: Util.numero(procesados), tipo: "acento" },
          { titulo: "Insertados / actualizados", valor: Util.numero(insertados), tipo: "exito" },
          { titulo: "Filas con error", valor: Util.numero(errores.length), tipo: errores.length ? "error" : "exito" },
        ]);
        raiz.querySelector("#carga-estado").textContent = `ID de archivo ${r.id_archivo ?? "-"} · Estado ${estado}`;
        Tabla.render(
          "tabla-errores-carga",
          [
            { clave: "numero_fila", titulo: "Fila", tipo: "numero" },
            { clave: "motivo", titulo: "Motivo del error" },
          ],
          errores,
          { vacio: "El archivo se cargó sin errores.", ordenInicial: { clave: "numero_fila", direccion: "ASC" } }
        );
        resultado.hidden = false;
        mostrarMensaje(
          mensaje,
          errores.length ? `Carga terminada con ${errores.length} filas con error.` : "Carga terminada sin errores.",
          errores.length ? "aviso" : "exito"
        );
        ({ XLSX: ["nomina", "salud", "novedades", "personal"], DAT: ["entretenimiento"], JSON: ["entretenimiento"] })[tipo].forEach(
          (reporte) => Panel.recargar(reporte)
        );
        if (tipo === "XLSX") Reportes.invalidarEmpleados();
      } catch (error) {
        mostrarMensaje(mensaje, error.message, "error");
      } finally {
        enviar.disabled = false;
        enviar.textContent = "Cargar archivo";
      }
    });
  }

  function etiquetaResultado(valor) {
    const texto = String(valor || "").toUpperCase();
    if (["EXITOSO", "COMPLETADO"].includes(texto)) return "exito";
    if (["FALLIDO"].includes(texto)) return "error";
    if (texto.includes("ERROR") || texto === "PROCESANDO") return "aviso";
    return "";
  }

  function iniciarAuditoria(raiz) {
    const pestanas = raiz.querySelectorAll(".pestana");
    const paneles = raiz.querySelectorAll("[data-panel-auditoria]");
    const modal = raiz.querySelector("#modal-detalle-auditoria");
    const tituloModal = raiz.querySelector("#detalle-auditoria-titulo");
    const cuerpoModal = raiz.querySelector("#detalle-auditoria-cuerpo");
    const cargadas = new Set();

    function bloque(titulo, contenido) {
      const seccion = document.createElement("div");
      const encabezado = document.createElement("h4");
      encabezado.textContent = titulo;
      encabezado.style.margin = "12px 0 6px";
      const pre = document.createElement("pre");
      pre.className = "json-bloque";
      let texto = contenido;
      if (typeof contenido === "string") {
        const json = leerJson(contenido, null);
        texto = json !== null ? JSON.stringify(json, null, 2) : contenido;
      } else if (contenido !== null && contenido !== undefined) {
        texto = JSON.stringify(contenido, null, 2);
      }
      pre.textContent = texto || "Sin datos";
      seccion.append(encabezado, pre);
      return seccion;
    }

    function verRegistro(fila) {
      tituloModal.textContent = `Registro de auditoría #${fila.id_auditoria ?? ""}`;
      const resumen = document.createElement("div");
      resumen.className = "ficha";
      [
        ["Fecha", Util.fecha(fila.fecha)],
        ["Hora", fila.hora],
        ["Usuario", fila.username || fila.id_usuario || "Anónimo"],
        ["Acción", fila.accion],
        ["Tabla afectada", fila.tabla_afectada],
        ["Resultado", fila.resultado],
      ].forEach(([titulo, valor]) => {
        const caja = document.createElement("div");
        const etiqueta = document.createElement("span");
        etiqueta.textContent = titulo;
        const fuerte = document.createElement("strong");
        fuerte.textContent = Util.vacio(valor) ? "—" : valor;
        caja.append(etiqueta, fuerte);
        resumen.appendChild(caja);
      });
      const detalle = document.createElement("p");
      detalle.style.marginTop = "12px";
      detalle.textContent = fila.detalle || "";
      cuerpoModal.replaceChildren(resumen, detalle, bloque("Datos anteriores", fila.datos_anteriores), bloque("Datos nuevos", fila.datos_nuevos));
      modal.showModal();
    }

    async function verErrores(fila) {
      tituloModal.textContent = `Errores de carga: ${fila.nombre_archivo || "archivo " + fila.id_archivo}`;
      const contenedor = document.createElement("div");
      cuerpoModal.replaceChildren(contenedor);
      modal.showModal();
      Tabla.cargando(contenedor);
      try {
        const datos = await Api.get(Api.RUTAS.erroresArchivo(fila.id_archivo));
        Tabla.render(
          contenedor,
          [
            { clave: "numero_fila", titulo: "Fila", tipo: "numero" },
            { clave: "motivo", titulo: "Motivo" },
          ],
          Api.listaDesde(datos, "errores", "errores_carga"),
          { vacio: "Este archivo no registró errores.", ordenInicial: { clave: "numero_fila", direccion: "ASC" } }
        );
      } catch (error) {
        Tabla.mensaje(contenedor, error.message);
      }
    }

    async function cargarAuditoria() {
      const filtros = Util.datosFormulario(raiz.querySelector("#filtros-auditoria"));
      if (filtros.desde && filtros.hasta && filtros.desde > filtros.hasta) {
        Tabla.mensaje("tabla-auditoria", "La fecha inicial no puede ser posterior a la final.", "aviso");
        return;
      }
      Tabla.cargando("tabla-auditoria");
      try {
        const datos = await Api.get(Api.RUTAS.auditoria, filtros);
        const filas = Api.listaDesde(datos, "registros", "auditoria");
        const exitosos = filas.filter((f) => String(f.resultado).toUpperCase() === "EXITOSO").length;
        Indicadores("indicadores-auditoria", [
          { titulo: "Registros consultados", valor: Util.numero(datos.total ?? filas.length) },
          { titulo: "Exitosos", valor: Util.numero(exitosos), tipo: "exito" },
          { titulo: "Fallidos", valor: Util.numero(filas.length - exitosos), tipo: "error" },
          { titulo: "Usuarios distintos", valor: Util.numero(Util.contarDistintos(filas, "id_usuario")), tipo: "acento" },
        ]);
        Tabla.render(
          "tabla-auditoria",
          [
            { clave: "id_auditoria", titulo: "ID" },
            { clave: "fecha", titulo: "Fecha", tipo: "fecha" },
            { clave: "hora", titulo: "Hora" },
            { clave: "username", claves: ["username", "id_usuario"], titulo: "Usuario", formato: (v) => (Util.vacio(v) ? "Anónimo" : v) },
            { clave: "accion", titulo: "Acción" },
            { clave: "tabla_afectada", titulo: "Tabla" },
            { clave: "resultado", titulo: "Resultado", etiqueta: etiquetaResultado },
            { clave: "detalle", titulo: "Detalle" },
          ],
          filas,
          { alClic: verRegistro, totalServidor: datos.total ?? filas.length, vacio: "No hay registros de auditoría con esos filtros." }
        );
      } catch (error) {
        Tabla.mensaje("tabla-auditoria", error.message);
      }
    }

    async function cargarArchivos() {
      Tabla.cargando("tabla-archivos");
      try {
        const datos = await Api.get(Api.RUTAS.archivos, Util.datosFormulario(raiz.querySelector("#filtros-archivos")));
        const filas = Api.listaDesde(datos, "archivos");
        Tabla.render(
          "tabla-archivos",
          [
            { clave: "id_archivo", titulo: "ID" },
            { clave: "nombre_archivo", titulo: "Archivo" },
            { clave: "tipo", titulo: "Tipo" },
            { clave: "fecha", titulo: "Fecha", tipo: "fecha" },
            { clave: "hora", titulo: "Hora" },
            { clave: "username", claves: ["username", "id_usuario"], titulo: "Usuario", formato: (v) => (Util.vacio(v) ? "Sistema" : v) },
            { clave: "estado", titulo: "Estado", etiqueta: etiquetaResultado },
            { clave: "total_errores", titulo: "Errores", tipo: "numero" },
          ],
          filas,
          {
            alClic: verErrores,
            ordenInicial: { clave: "id_archivo", direccion: "DESC" },
            vacio: "Todavía no se han cargado archivos.",
          }
        );
      } catch (error) {
        Tabla.mensaje("tabla-archivos", error.message);
      }
    }

    const CARGADORES = { auditoria: cargarAuditoria, archivos: cargarArchivos };

    function mostrarPanel(nombre) {
      pestanas.forEach((p) => {
        const activa = p.dataset.panelAuditoria === nombre;
        p.classList.toggle("activa", activa);
        p.setAttribute("aria-selected", String(activa));
      });
      paneles.forEach((panel) => {
        if (panel.classList.contains("pestana")) return;
        panel.hidden = panel.dataset.panelAuditoria !== nombre;
      });
      if (!cargadas.has(nombre)) {
        cargadas.add(nombre);
        CARGADORES[nombre]();
      }
    }

    pestanas.forEach((p) => p.addEventListener("click", () => mostrarPanel(p.dataset.panelAuditoria)));
    raiz.querySelector("#filtros-auditoria").addEventListener("submit", (evento) => {
      evento.preventDefault();
      cargarAuditoria();
    });
    raiz.querySelector("#filtros-auditoria").addEventListener("reset", () => setTimeout(cargarAuditoria));
    raiz.querySelector("#filtros-archivos").addEventListener("submit", (evento) => {
      evento.preventDefault();
      cargarArchivos();
    });
    modal.querySelector("[data-cerrar]").addEventListener("click", () => modal.close());
    mostrarPanel("auditoria");
  }

  function iniciar(nombre, raiz) {
    if (raiz.querySelector("[data-recurso]")) iniciarCrud(nombre, raiz);
    else if (nombre === "carga") iniciarCarga(raiz);
    else if (nombre === "auditoria") iniciarAuditoria(raiz);
  }

  return { iniciar };
})();
