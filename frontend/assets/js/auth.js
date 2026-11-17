const Auth = (() => {
  let captchaActual = null;
  let temporizadorCaptcha = null;
  let temporizadorSesion = null;

  function decodificarToken(token) {
    try {
      const partes = String(token).split(".");
      if (partes.length !== 3) return null;
      const base64 = partes[1].replace(/-/g, "+").replace(/_/g, "/");
      const relleno = base64 + "===".slice((base64.length + 3) % 4);
      const texto = decodeURIComponent(
        atob(relleno)
          .split("")
          .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
          .join("")
      );
      return JSON.parse(texto);
    } catch (error) {
      return null;
    }
  }

  function tokenVigente(token) {
    const carga = decodificarToken(token);
    if (!carga || typeof carga.exp !== "number") return false;
    return carga.exp * 1000 > Date.now();
  }

  function sesionActiva() {
    const token = Api.obtenerToken();
    return Boolean(token) && tokenVigente(token);
  }

  function irA(pagina, parametros) {
    const destino = new URL(pagina, window.location.href);
    Object.entries(parametros || {}).forEach(([clave, valor]) => destino.searchParams.set(clave, valor));
    window.location.replace(destino.toString());
  }

  function cerrarSesion(motivo) {
    Api.limpiarSesion();
    if (temporizadorSesion) clearTimeout(temporizadorSesion);
    irA("index.html", motivo ? { motivo } : {});
  }

  function requerirSesion() {
    if (!sesionActiva()) {
      Api.limpiarSesion();
      irA("index.html", { motivo: "requerida" });
      return null;
    }
    const carga = decodificarToken(Api.obtenerToken());
    const restante = carga.exp * 1000 - Date.now();
    temporizadorSesion = setTimeout(() => cerrarSesion("expirada"), Math.max(restante, 0));
    const guardado = Api.obtenerUsuario() || {};
    return {
      id_usuario: guardado.id_usuario ?? carga.id_usuario,
      username: guardado.username ?? carga.username,
      rol: guardado.rol ?? carga.rol,
      expira: new Date(carga.exp * 1000),
    };
  }

  function mostrarMensaje(elemento, texto, tipo) {
    if (!elemento) return;
    elemento.textContent = texto || "";
    elemento.className = `mensaje mensaje-${tipo || "error"}`;
    elemento.hidden = !texto;
  }

  async function cargarCaptcha() {
    const contenedor = document.getElementById("captcha-imagen");
    const tiempo = document.getElementById("captcha-tiempo");
    const respuesta = document.getElementById("captcha-respuesta");
    const boton = document.getElementById("btn-captcha");
    if (temporizadorCaptcha) clearInterval(temporizadorCaptcha);
    captchaActual = null;
    respuesta.value = "";
    boton.disabled = true;
    contenedor.textContent = "Generando desafío...";
    tiempo.textContent = "";
    tiempo.classList.remove("vencido");
    try {
      const datos = await Api.publico(Api.RUTAS.captcha);
      const imagen = document.createElement("img");
      imagen.alt = "Desafío CAPTCHA: escriba los caracteres que ve";
      imagen.src = `data:${datos.tipo_contenido || "image/png"};base64,${datos.imagen_base64}`;
      contenedor.replaceChildren(imagen);
      const vence = Date.now() + Number(datos.expira_en_segundos || 240) * 1000;
      captchaActual = { id: datos.captcha_id, vence };
      const actualizar = () => {
        const segundos = Math.max(0, Math.round((vence - Date.now()) / 1000));
        if (segundos === 0) {
          tiempo.textContent = "El desafío expiró. Genere uno nuevo.";
          tiempo.classList.add("vencido");
          clearInterval(temporizadorCaptcha);
          return;
        }
        const minutos = Math.floor(segundos / 60);
        tiempo.textContent = `Vence en ${minutos}:${String(segundos % 60).padStart(2, "0")}`;
      };
      actualizar();
      temporizadorCaptcha = setInterval(actualizar, 1000);
    } catch (error) {
      contenedor.textContent = "No fue posible cargar el CAPTCHA";
      mostrarMensaje(document.getElementById("login-mensaje"), error.message, "error");
    } finally {
      boton.disabled = false;
    }
  }

  async function enviarLogin(evento) {
    evento.preventDefault();
    const formulario = evento.currentTarget;
    const mensaje = document.getElementById("login-mensaje");
    const boton = formulario.querySelector('button[type="submit"]');
    mostrarMensaje(mensaje, "");
    if (!formulario.reportValidity()) return;
    if (!captchaActual || captchaActual.vence <= Date.now()) {
      mostrarMensaje(mensaje, "El CAPTCHA expiró. Se generó un nuevo desafío.", "aviso");
      cargarCaptcha();
      return;
    }
    const datos = new FormData(formulario);
    const cuerpo = {
      username: String(datos.get("username")).trim(),
      password: String(datos.get("password")),
      captcha_id: captchaActual.id,
      captcha_respuesta: String(datos.get("captcha_respuesta")).trim().toUpperCase(),
    };
    boton.disabled = true;
    boton.innerHTML = '<span class="spinner" aria-hidden="true"></span> Validando...';
    try {
      const respuesta = await Api.publico(Api.RUTAS.login, { metodo: "POST", cuerpo });
      if (!respuesta || !respuesta.token || !tokenVigente(respuesta.token)) {
        throw new Error("El servidor devolvió un token inválido.");
      }
      Api.guardarSesion(respuesta.token, respuesta.usuario);
      mostrarMensaje(mensaje, "Acceso concedido. Redirigiendo al panel...", "exito");
      irA("dashboard.html");
    } catch (error) {
      mostrarMensaje(mensaje, error.message, "error");
      formulario.querySelector('[name="password"]').value = "";
      cargarCaptcha();
    } finally {
      boton.disabled = false;
      boton.textContent = "Ingresar";
    }
  }

  function iniciarLogin() {
    if (sesionActiva()) {
      irA("dashboard.html");
      return;
    }
    const motivos = {
      expirada: ["Su sesión expiró. Inicie sesión nuevamente.", "aviso"],
      requerida: ["Debe iniciar sesión para acceder al panel.", "aviso"],
      salida: ["Sesión cerrada correctamente.", "exito"],
    };
    const motivo = new URLSearchParams(window.location.search).get("motivo");
    if (motivos[motivo]) mostrarMensaje(document.getElementById("login-mensaje"), ...motivos[motivo]);
    document.getElementById("form-login").addEventListener("submit", enviarLogin);
    document.getElementById("btn-captcha").addEventListener("click", cargarCaptcha);
    document.getElementById("captcha-respuesta").addEventListener("input", (evento) => {
      evento.target.value = evento.target.value.toUpperCase();
    });
    const verClave = document.getElementById("btn-ver-clave");
    verClave.addEventListener("click", () => {
      const campo = document.getElementById("password");
      const visible = campo.type === "text";
      campo.type = visible ? "password" : "text";
      verClave.textContent = visible ? "Mostrar" : "Ocultar";
      verClave.setAttribute("aria-pressed", String(!visible));
    });
    cargarCaptcha();
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("form-login")) iniciarLogin();
  });

  return { requerirSesion, cerrarSesion, decodificarToken, sesionActiva };
})();
