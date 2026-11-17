const Api = (() => {
  const CLAVE_TOKEN = "entrcol_token";
  const CLAVE_USUARIO = "entrcol_usuario";

  const metaBase = document.querySelector('meta[name="api-base"]');
  const BASE = (metaBase ? metaBase.content : "").replace(/\/+$/, "");

  const RUTAS = {
    captcha: "/api/auth/captcha",
    login: "/api/auth/login",
    salud: "/api/health",
    pdf: (tipo) => `/api/pdf/reporte/${encodeURIComponent(tipo)}`,
    catalogos: "/api/nomina/catalogos",
    empleados: "/api/nomina/empleados",
    empleado: (id) => `/api/nomina/empleados/${encodeURIComponent(id)}`,
    novedades: "/api/nomina/novedades",
    novedad: (id) => `/api/nomina/novedades/${encodeURIComponent(id)}`,
    reporteDependencias: "/api/nomina/reporte/dependencias",
    reporteDependenciasCargos: "/api/nomina/reporte/dependencias-cargos",
    reporteEmpleado: (id) => `/api/nomina/reporte/empleado/${encodeURIComponent(id)}`,
    reporteSaludPension: "/api/nomina/reporte/salud-pension",
    reporteCargoEps: "/api/nomina/reporte/cargo-eps",
    reporteCargoPension: "/api/nomina/reporte/cargo-pension",
    reporteNovedades: "/api/nomina/reporte/novedades",
    generos: "/api/entretenimiento/generos",
    peliculas: "/api/entretenimiento/peliculas",
    pelicula: (id) => `/api/entretenimiento/peliculas/${encodeURIComponent(id)}`,
    libros: "/api/entretenimiento/libros",
    libro: (id) => `/api/entretenimiento/libros/${encodeURIComponent(id)}`,
    peliculasGeneroFechas: "/api/entretenimiento/reporte/peliculas-genero",
    peliculasNGeneros: "/api/entretenimiento/reporte/peliculas-n-generos",
    topLibros: "/api/entretenimiento/reporte/top-libros",
    top5LibrosAnio: "/api/entretenimiento/reporte/top5-libros-anio",
    graficoPeliculasGenero: "/api/entretenimiento/grafico/peliculas-genero",
    graficoLibrosAnio: "/api/entretenimiento/grafico/libros-anio",
    cargaArchivo: "/api/etl/upload",
    archivos: "/api/etl/archivos",
    erroresArchivo: (id) => `/api/etl/archivos/${encodeURIComponent(id)}/errores`,
    auditoria: "/api/auditoria",
  };

  const ALIAS = {
    nombre_dependencia: "dependencia",
    nombre_cargo: "cargo",
    nombre_eps: "eps",
    nombre_fondo_pension: "fondo_pension",
    nombre_tipo_novedad: "tipo_novedad",
    nombre_genero: "genero",
    nombre_autor: "autor",
    nombre_editorial: "editorial",
    nombre_idioma: "idioma",
  };

  class ErrorApi extends Error {
    constructor(mensaje, estado, datos) {
      super(mensaje);
      this.name = "ErrorApi";
      this.estado = estado;
      this.datos = datos;
    }
  }

  function obtenerToken() {
    return sessionStorage.getItem(CLAVE_TOKEN);
  }

  function obtenerUsuario() {
    try {
      return JSON.parse(sessionStorage.getItem(CLAVE_USUARIO) || "null");
    } catch (error) {
      return null;
    }
  }

  function guardarSesion(token, usuario) {
    sessionStorage.setItem(CLAVE_TOKEN, token);
    sessionStorage.setItem(CLAVE_USUARIO, JSON.stringify(usuario || {}));
  }

  function limpiarSesion() {
    sessionStorage.removeItem(CLAVE_TOKEN);
    sessionStorage.removeItem(CLAVE_USUARIO);
  }

  function construirUrl(ruta, parametros) {
    const url = new URL(BASE + ruta, window.location.href);
    Object.entries(parametros || {}).forEach(([clave, valor]) => {
      if (valor !== undefined && valor !== null && String(valor).trim() !== "") {
        url.searchParams.set(clave, valor);
      }
    });
    return url.toString();
  }

  function mensajeDesde(datos, estado) {
    if (datos && typeof datos === "object") {
      if (typeof datos.error === "string") return datos.error;
      if (typeof datos.mensaje === "string") return datos.mensaje;
      if (typeof datos.detail === "string") return datos.detail;
      if (Array.isArray(datos.detail) && datos.detail.length) {
        return datos.detail.map((d) => d.msg || JSON.stringify(d)).join(" | ");
      }
    }
    const textos = {
      400: "La solicitud tiene datos inválidos.",
      401: "La sesión no es válida o expiró.",
      403: "No tiene permisos para esta operación.",
      404: "El recurso solicitado no existe en el servidor.",
      409: "La operación entra en conflicto con datos existentes.",
      413: "El archivo supera el tamaño permitido.",
      500: "Error interno del servidor.",
      503: "La base de datos no está disponible.",
    };
    return textos[estado] || `Error inesperado (${estado}).`;
  }

  function alExpirarSesion() {
    limpiarSesion();
    const destino = new URL("index.html", window.location.href);
    destino.searchParams.set("motivo", "expirada");
    window.location.replace(destino.toString());
  }

  async function solicitar(ruta, opciones = {}) {
    const { metodo = "GET", parametros, cuerpo, formulario, respuesta = "json", publica = false } = opciones;
    const cabeceras = { Accept: respuesta === "blob" ? "application/pdf" : "application/json" };
    const token = obtenerToken();
    if (token && !publica) cabeceras.Authorization = `Bearer ${token}`;
    let carga;
    if (formulario) {
      carga = formulario;
    } else if (cuerpo !== undefined) {
      cabeceras["Content-Type"] = "application/json";
      carga = JSON.stringify(cuerpo);
    }
    let resultado;
    try {
      resultado = await fetch(construirUrl(ruta, parametros), { method: metodo, headers: cabeceras, body: carga });
    } catch (error) {
      throw new ErrorApi(`No se pudo conectar con el backend en ${BASE || window.location.origin}.`, 0, null);
    }
    if (resultado.status === 401 && !publica) {
      alExpirarSesion();
      throw new ErrorApi("La sesión expiró. Inicie sesión nuevamente.", 401, null);
    }
    const tipo = resultado.headers.get("Content-Type") || "";
    if (!resultado.ok) {
      let datos = null;
      if (tipo.includes("application/json")) {
        datos = await resultado.json().catch(() => null);
      }
      throw new ErrorApi(mensajeDesde(datos, resultado.status), resultado.status, datos);
    }
    if (respuesta === "blob") return resultado.blob();
    if (resultado.status === 204) return null;
    if (tipo.includes("application/json")) return normalizar(await resultado.json());
    return resultado.text();
  }

  function normalizarFila(fila) {
    if (!fila || typeof fila !== "object" || Array.isArray(fila)) return fila;
    const copia = { ...fila };
    Object.entries(ALIAS).forEach(([original, canonico]) => {
      if (copia[original] !== undefined && copia[canonico] === undefined) copia[canonico] = copia[original];
    });
    if (copia.nombre_completo === undefined && (copia.nombres !== undefined || copia.apellidos !== undefined)) {
      copia.nombre_completo = [copia.nombres, copia.apellidos].filter(Boolean).join(" ");
    }
    if (copia.nombre_completo === undefined && copia.codigo_personal !== undefined && copia.nombre !== undefined) {
      copia.nombre_completo = copia.nombre;
    }
    Object.keys(copia).forEach((clave) => {
      const valor = copia[clave];
      if (Array.isArray(valor)) copia[clave] = valor.map(normalizarFila);
      else if (valor && typeof valor === "object") copia[clave] = normalizarFila(valor);
    });
    return copia;
  }

  function normalizar(datos) {
    if (Array.isArray(datos)) return datos.map(normalizarFila);
    return normalizarFila(datos);
  }

  function listaDesde(datos, ...claves) {
    if (Array.isArray(datos)) return datos;
    if (!datos || typeof datos !== "object") return [];
    for (const clave of claves) {
      if (Array.isArray(datos[clave])) return datos[clave];
    }
    const primera = Object.values(datos).find(Array.isArray);
    return primera || [];
  }

  return {
    RUTAS,
    ErrorApi,
    base: BASE,
    obtenerToken,
    obtenerUsuario,
    guardarSesion,
    limpiarSesion,
    listaDesde,
    get: (ruta, parametros) => solicitar(ruta, { parametros }),
    post: (ruta, cuerpo) => solicitar(ruta, { metodo: "POST", cuerpo }),
    put: (ruta, cuerpo) => solicitar(ruta, { metodo: "PUT", cuerpo }),
    eliminar: (ruta) => solicitar(ruta, { metodo: "DELETE" }),
    publico: (ruta, opciones) => solicitar(ruta, { ...opciones, publica: true }),
    subir: (ruta, formulario) => solicitar(ruta, { metodo: "POST", formulario }),
    pdf: (tipo, parametros) => solicitar(RUTAS.pdf(tipo), { parametros, respuesta: "blob" }),
  };
})();
