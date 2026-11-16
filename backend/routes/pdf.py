import re
from datetime import date

from flask import Blueprint, Response, g, jsonify, request
from mysql.connector import Error

from database.connection import DatabaseConnectionError, get_db_connection
from routes.auth import token_required
from services import pdf_generator
from services.audit_logger import log_audit

pdf_bp = Blueprint("pdf", __name__, url_prefix="/api/pdf")

ORDENES_VALIDOS = ("ASC", "DESC")
ORDEN_POR_DEFECTO = "ASC"
MAXIMO_FILAS = 5000
MAXIMO_N = 1000
PATRON_MES_ANIO = re.compile(r"^(0[1-9]|1[0-2])/(\d{4})$")
PATRON_ANIO = re.compile(r"^\d{4}$")

MODALIDADES_NOMINA = ("general", "por_dependencia", "por_cargo_dependencia")
SUBTIPOS_ENTRETENIMIENTO = (
    "peliculas_genero_fechas",
    "peliculas_n_generos",
    "top_n_libros",
    "top_5_libros_anio",
)
TABLA_AUDITADA = {
    "nomina": "empleados",
    "informacion_personal": "empleados",
    "salud_pension": "afiliaciones_empleado",
    "novedades": "novedades",
    "entretenimiento": "peliculas",
}


class ParametroInvalido(Exception):
    pass


def leer_orden():
    orden = request.args.get("orden", ORDEN_POR_DEFECTO).strip().upper()
    if orden not in ORDENES_VALIDOS:
        raise ParametroInvalido("orden debe ser ASC o DESC")
    return orden


def leer_entero_positivo(nombre, maximo=MAXIMO_N):
    crudo = request.args.get(nombre, "").strip()
    if not crudo.isdigit() or not 1 <= int(crudo) <= maximo:
        raise ParametroInvalido(f"{nombre} debe ser un entero entre 1 y {maximo}")
    return int(crudo)


def mes_siguiente(anio, mes):
    return date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)


def leer_rango_fechas():
    f1 = request.args.get("f1", "").strip()
    f2 = request.args.get("f2", "").strip()
    inicio = interpretar_limite(f1, "f1", False)
    fin_exclusivo = interpretar_limite(f2, "f2", True)
    if inicio >= fin_exclusivo:
        raise ParametroInvalido("f1 no puede ser posterior a f2")
    return f1, f2, inicio, fin_exclusivo


def interpretar_limite(valor, nombre, es_fin):
    coincidencia = PATRON_MES_ANIO.match(valor)
    if coincidencia:
        mes, anio = int(coincidencia.group(1)), int(coincidencia.group(2))
        return mes_siguiente(anio, mes) if es_fin else date(anio, mes, 1)
    if PATRON_ANIO.match(valor):
        anio = int(valor)
        return date(anio + 1, 1, 1) if es_fin else date(anio, 1, 1)
    raise ParametroInvalido(f"{nombre} debe tener formato MM/AAAA")


def ejecutar(consulta, parametros=()):
    conexion = get_db_connection(autocommit=True)
    try:
        cursor = conexion.cursor()
        cursor.execute(consulta, parametros)
        filas = cursor.fetchall()
        cursor.close()
        return filas
    finally:
        conexion.close()


def limitar(filas):
    if len(filas) > MAXIMO_FILAS:
        return filas[:MAXIMO_FILAS], f"Se muestran las primeras {MAXIMO_FILAS} filas del resultado."
    return filas, None


BASE_EMPLEADOS = (
    "FROM empleados e "
    "JOIN personas p ON p.id_persona = e.id_persona "
    "JOIN cargos c ON c.id_cargo = e.id_cargo "
    "JOIN dependencias d ON d.id_dependencia = e.id_dependencia "
)
BASE_AFILIACIONES = (
    BASE_EMPLEADOS
    + "LEFT JOIN afiliaciones_empleado a ON a.id_empleado = e.id_empleado "
    "LEFT JOIN eps ep ON ep.id_eps = a.id_eps "
    "LEFT JOIN fondos_pension fp ON fp.id_fondo_pension = a.id_fondo_pension "
)
BASE_NOVEDADES = (
    BASE_EMPLEADOS
    + "JOIN afiliaciones_empleado a ON a.id_empleado = e.id_empleado "
    "JOIN detalle_nomina dn ON dn.id_afiliacion_empleado = a.id_afiliacion_empleado "
    "JOIN novedades n ON n.id_detalle_nomina = dn.id_detalle_nomina "
    "JOIN tipos_novedad tn ON tn.id_tipo_novedad = n.id_tipo_novedad "
)


def reporte_nomina(usuario):
    modalidad = request.args.get("modalidad", "general").strip().lower()
    if modalidad not in MODALIDADES_NOMINA:
        raise ParametroInvalido("modalidad debe ser general, por_dependencia o por_cargo_dependencia")
    orden = leer_orden()
    ordenamientos = {
        "general": f"p.nombre_completo {orden}",
        "por_dependencia": f"d.nombre ASC, p.nombre_completo {orden}",
        "por_cargo_dependencia": f"d.nombre ASC, c.nombre ASC, p.nombre_completo {orden}",
    }
    filas = ejecutar(
        "SELECT e.codigo_personal, p.nombre_completo, d.nombre, c.nombre, e.salario "
        + BASE_EMPLEADOS
        + "ORDER BY "
        + ordenamientos[modalidad]
    )
    conteos = None
    if modalidad == "por_dependencia":
        conteos = {
            "columnas": ["Dependencia", "Cantidad de empleados"],
            "filas": ejecutar(
                "SELECT d.nombre, COUNT(*) " + BASE_EMPLEADOS + "GROUP BY d.nombre ORDER BY d.nombre ASC"
            ),
        }
    if modalidad == "por_cargo_dependencia":
        conteos = {
            "columnas": ["Dependencia", "Cargo", "Cantidad de empleados"],
            "filas": ejecutar(
                "SELECT d.nombre, c.nombre, COUNT(*) "
                + BASE_EMPLEADOS
                + "GROUP BY d.nombre, c.nombre ORDER BY d.nombre ASC, c.nombre ASC"
            ),
        }
    filas, aviso = limitar(filas)
    filtros = {"modalidad": modalidad, "orden": orden}
    texto = f"Modalidad: {modalidad} | Orden de nombres: {orden}"
    return filtros, pdf_generator.pdf_nomina(modalidad, conteos, filas, texto, usuario, aviso)


def reporte_informacion_personal(usuario):
    codigo = request.args.get("codigo_personal", "").strip()
    id_empleado = request.args.get("id_empleado", "").strip()
    if codigo:
        condicion, valor, filtros = "e.codigo_personal = %s", codigo, {"codigo_personal": codigo}
    elif id_empleado.isdigit():
        condicion, valor, filtros = "e.id_empleado = %s", int(id_empleado), {"id_empleado": int(id_empleado)}
    else:
        raise ParametroInvalido("Debe indicar codigo_personal o id_empleado")
    resultado = ejecutar(
        "SELECT e.id_empleado, e.codigo_personal, p.nombre_completo, d.nombre, c.nombre, e.fecha_ingreso, "
        "ep.nombre, "
        "(SELECT dn.valor_aporte_pension FROM detalle_nomina dn "
        "WHERE dn.id_afiliacion_empleado = a.id_afiliacion_empleado "
        "ORDER BY dn.periodo_fecha DESC LIMIT 1), "
        "e.salario "
        + BASE_AFILIACIONES
        + f"WHERE {condicion} LIMIT 1",
        (valor,),
    )
    if not resultado:
        raise LookupError("Empleado no encontrado")
    fila = resultado[0]
    empleado = {
        "codigo_personal": fila[1],
        "nombre_completo": fila[2],
        "dependencia": fila[3],
        "cargo": fila[4],
        "fecha_ingreso": fila[5],
        "eps": fila[6],
        "aporte_pension": fila[7],
        "salario": fila[8],
    }
    novedades = ejecutar(
        "SELECT dn.periodo_fecha, tn.nombre, n.detalle, n.dias_reportados "
        "FROM afiliaciones_empleado a "
        "JOIN detalle_nomina dn ON dn.id_afiliacion_empleado = a.id_afiliacion_empleado "
        "JOIN novedades n ON n.id_detalle_nomina = dn.id_detalle_nomina "
        "JOIN tipos_novedad tn ON tn.id_tipo_novedad = n.id_tipo_novedad "
        "WHERE a.id_empleado = %s ORDER BY dn.periodo_fecha ASC, tn.nombre ASC",
        (fila[0],),
    )
    texto = f"Empleado: {fila[1]}"
    return filtros, pdf_generator.pdf_informacion_personal(empleado, novedades, texto, usuario)


def reporte_salud_pension(usuario):
    orden = leer_orden()
    bloques = [
        {
            "titulo": "Frecuencia general por EPS",
            "columnas": ["EPS", "Cantidad de empleados"],
            "filas": ejecutar(
                "SELECT COALESCE(ep.nombre, 'Sin EPS'), COUNT(*) " + BASE_AFILIACIONES
                + "GROUP BY ep.nombre ORDER BY ep.nombre ASC"
            ),
        },
        {
            "titulo": "Frecuencia general por Fondo de Pensión",
            "columnas": ["Fondo de pensión", "Cantidad de empleados"],
            "filas": ejecutar(
                "SELECT COALESCE(fp.nombre, 'Sin fondo'), COUNT(*) " + BASE_AFILIACIONES
                + "GROUP BY fp.nombre ORDER BY fp.nombre ASC"
            ),
        },
        {
            "titulo": "Frecuencia de EPS por dependencia",
            "columnas": ["Dependencia", "EPS", "Cantidad de empleados"],
            "filas": ejecutar(
                "SELECT d.nombre, COALESCE(ep.nombre, 'Sin EPS'), COUNT(*) " + BASE_AFILIACIONES
                + "GROUP BY d.nombre, ep.nombre ORDER BY d.nombre ASC, ep.nombre ASC"
            ),
        },
        {
            "titulo": "Frecuencia de Fondo de Pensión por dependencia",
            "columnas": ["Dependencia", "Fondo de pensión", "Cantidad de empleados"],
            "filas": ejecutar(
                "SELECT d.nombre, COALESCE(fp.nombre, 'Sin fondo'), COUNT(*) " + BASE_AFILIACIONES
                + "GROUP BY d.nombre, fp.nombre ORDER BY d.nombre ASC, fp.nombre ASC"
            ),
        },
    ]
    listado_eps, aviso_eps = limitar(
        ejecutar(
            "SELECT c.nombre, COALESCE(ep.nombre, 'Sin EPS'), p.nombre_completo "
            + BASE_AFILIACIONES
            + f"ORDER BY c.nombre ASC, ep.nombre ASC, p.nombre_completo {orden}"
        )
    )
    listado_pension, aviso_pension = limitar(
        ejecutar(
            "SELECT c.nombre, COALESCE(fp.nombre, 'Sin fondo'), p.nombre_completo "
            + BASE_AFILIACIONES
            + f"ORDER BY c.nombre ASC, fp.nombre ASC, p.nombre_completo {orden}"
        )
    )
    bloques.append(
        {
            "titulo": "Listado por cargo y EPS",
            "columnas": ["Cargo", "EPS", "Empleado"],
            "filas": listado_eps,
            "aviso": aviso_eps,
        }
    )
    bloques.append(
        {
            "titulo": "Listado por cargo y Fondo de Pensión",
            "columnas": ["Cargo", "Fondo de pensión", "Empleado"],
            "filas": listado_pension,
            "aviso": aviso_pension,
        }
    )
    texto = f"Orden de nombres: {orden}"
    return {"orden": orden}, pdf_generator.pdf_salud_pension(bloques, texto, usuario)


def reporte_novedades(usuario):
    f1, f2, inicio, fin_exclusivo = leer_rango_fechas()
    orden = leer_orden()
    parametros = (inicio, fin_exclusivo)
    conteos = ejecutar(
        "SELECT d.nombre, c.nombre, COUNT(*) "
        + BASE_NOVEDADES
        + "WHERE dn.periodo_fecha >= %s AND dn.periodo_fecha < %s "
        "GROUP BY d.nombre, c.nombre ORDER BY d.nombre ASC, c.nombre ASC",
        parametros,
    )
    detalle, aviso = limitar(
        ejecutar(
            "SELECT e.codigo_personal, p.nombre_completo, d.nombre, c.nombre, dn.periodo_fecha, "
            "tn.nombre, n.detalle, n.dias_reportados "
            + BASE_NOVEDADES
            + "WHERE dn.periodo_fecha >= %s AND dn.periodo_fecha < %s "
            f"ORDER BY d.nombre ASC, c.nombre ASC, p.nombre_completo {orden}, dn.periodo_fecha ASC",
            parametros,
        )
    )
    texto = f"Rango: {f1} a {f2} | Orden de nombres: {orden}"
    documento = pdf_generator.pdf_novedades(detalle, conteos, texto, usuario, aviso)
    return {"f1": f1, "f2": f2, "orden": orden}, documento


def reporte_entretenimiento(usuario):
    subtipo = request.args.get("subtipo", "").strip().lower()
    if subtipo not in SUBTIPOS_ENTRETENIMIENTO:
        raise ParametroInvalido("subtipo debe ser uno de: " + ", ".join(SUBTIPOS_ENTRETENIMIENTO))
    orden = leer_orden()
    if subtipo == "peliculas_genero_fechas":
        f1, f2, inicio, fin_exclusivo = leer_rango_fechas()
        filas, aviso = limitar(
            ejecutar(
                "SELECT g.nombre, pe.titulo, pe.fecha_estreno "
                "FROM peliculas pe "
                "JOIN pelicula_generos pg ON pg.id_pelicula = pe.id_pelicula "
                "JOIN generos g ON g.id_genero = pg.id_genero "
                "WHERE pe.fecha_estreno >= %s AND pe.fecha_estreno < %s "
                f"ORDER BY g.nombre ASC, pe.titulo {orden}",
                (inicio, fin_exclusivo),
            )
        )
        bloques = [
            {
                "titulo": "Películas por género en el rango de fechas",
                "columnas": ["Género", "Película", "Fecha de estreno"],
                "filas": filas,
                "resumen": [f"Total de registros: {len(filas)}"],
                "aviso": aviso,
            }
        ]
        filtros = {"subtipo": subtipo, "f1": f1, "f2": f2, "orden": orden}
        texto = f"Rango: {f1} a {f2} | Orden de títulos: {orden}"
    elif subtipo == "peliculas_n_generos":
        n = leer_entero_positivo("n")
        filas, aviso = limitar(
            ejecutar(
                "SELECT pe.titulo, pe.fecha_estreno, COUNT(pg.id_genero) "
                "FROM peliculas pe "
                "JOIN pelicula_generos pg ON pg.id_pelicula = pe.id_pelicula "
                "GROUP BY pe.id_pelicula, pe.titulo, pe.fecha_estreno "
                "HAVING COUNT(pg.id_genero) = %s "
                f"ORDER BY pe.titulo {orden}",
                (n,),
            )
        )
        total = ejecutar(
            "SELECT COUNT(*) FROM (SELECT pg.id_pelicula FROM pelicula_generos pg "
            "GROUP BY pg.id_pelicula HAVING COUNT(pg.id_genero) = %s) conteo",
            (n,),
        )[0][0]
        bloques = [
            {
                "titulo": f"Películas con exactamente {n} géneros",
                "columnas": ["Película", "Fecha de estreno", "Cantidad de géneros"],
                "filas": filas,
                "resumen": [f"Total de películas: {total}"],
                "aviso": aviso,
            }
        ]
        filtros = {"subtipo": subtipo, "n": n, "orden": orden}
        texto = f"N géneros: {n} | Orden de títulos: {orden}"
    elif subtipo == "top_n_libros":
        n = leer_entero_positivo("n")
        filas = ejecutar(
            "SELECT t.titulo, a.nombre, t.rating, t.numero_resenas, t.anio_publicacion FROM ("
            "SELECT titulo, id_autor, rating, numero_resenas, anio_publicacion FROM libros "
            "WHERE rating IS NOT NULL ORDER BY rating DESC, numero_resenas DESC LIMIT %s) t "
            "JOIN autores a ON a.id_autor = t.id_autor "
            f"ORDER BY t.titulo {orden}",
            (n,),
        )
        bloques = [
            {
                "titulo": f"Top {n} libros con mejor rating",
                "columnas": ["Título", "Autor", "Rating", "Reseñas", "Año de publicación"],
                "filas": filas,
            }
        ]
        filtros = {"subtipo": subtipo, "n": n, "orden": orden}
        texto = f"Top N: {n} | Orden de títulos: {orden}"
    else:
        bloques = []
        for etiqueta, direccion_rating in (("mejor", "DESC"), ("peor", "ASC")):
            filas, aviso = limitar(
                ejecutar(
                    "SELECT r.anio_publicacion, r.titulo, a.nombre, r.rating FROM ("
                    "SELECT l.titulo, l.id_autor, l.rating, l.anio_publicacion, "
                    f"ROW_NUMBER() OVER (PARTITION BY l.anio_publicacion ORDER BY l.rating {direccion_rating}, "
                    "l.numero_resenas DESC) AS posicion "
                    "FROM libros l WHERE l.rating IS NOT NULL AND l.anio_publicacion IS NOT NULL) r "
                    "JOIN autores a ON a.id_autor = r.id_autor "
                    "WHERE r.posicion <= 5 "
                    f"ORDER BY r.anio_publicacion ASC, r.titulo {orden}"
                )
            )
            bloques.append(
                {
                    "titulo": f"Top 5 libros con {etiqueta} rating por año",
                    "columnas": ["Año", "Título", "Autor", "Rating"],
                    "filas": filas,
                    "aviso": aviso,
                }
            )
        filtros = {"subtipo": subtipo, "orden": orden}
        texto = f"Top 5 mejor y peor rating por año | Orden de títulos: {orden}"
    documento = pdf_generator.pdf_entretenimiento(subtipo, bloques, texto, usuario)
    return filtros, documento


GENERADORES = {
    "nomina": reporte_nomina,
    "informacion_personal": reporte_informacion_personal,
    "salud_pension": reporte_salud_pension,
    "novedades": reporte_novedades,
    "entretenimiento": reporte_entretenimiento,
}


def respuesta_error(mensaje, codigo):
    return jsonify({"error": mensaje}), codigo


@pdf_bp.route("/reporte/<tipo_reporte>", methods=["GET"])
@token_required
def reporte(tipo_reporte):
    generador = GENERADORES.get(tipo_reporte)
    if generador is None:
        return respuesta_error("Tipo de reporte no válido. Valores: " + ", ".join(GENERADORES), 404)
    usuario = g.current_user
    argumentos = dict(request.args)
    accion = "EXPORTAR_PDF"
    tabla = TABLA_AUDITADA[tipo_reporte]
    try:
        filtros, documento = generador(usuario["username"])
    except ParametroInvalido as error:
        log_audit(accion, f"Reporte '{tipo_reporte}' rechazado: {error}", "FALLIDO",
                  id_usuario=usuario["id_usuario"], tabla_afectada=tabla, datos_nuevos=argumentos)
        return respuesta_error(str(error), 400)
    except LookupError as error:
        log_audit(accion, f"Reporte '{tipo_reporte}' sin resultados: {error}", "FALLIDO",
                  id_usuario=usuario["id_usuario"], tabla_afectada=tabla, datos_nuevos=argumentos)
        return respuesta_error(str(error), 404)
    except DatabaseConnectionError:
        return respuesta_error("Servicio de base de datos no disponible", 503)
    except Error:
        log_audit(accion, f"Error de base de datos generando '{tipo_reporte}'", "FALLIDO",
                  id_usuario=usuario["id_usuario"], tabla_afectada=tabla, datos_nuevos=argumentos)
        return respuesta_error("No se pudo generar el reporte", 500)
    log_audit(accion, f"Reporte '{tipo_reporte}' generado", "EXITOSO",
              id_usuario=usuario["id_usuario"], tabla_afectada=tabla,
              datos_nuevos={"tipo_reporte": tipo_reporte, "filtros": filtros})
    return Response(
        documento.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="reporte_{tipo_reporte}.pdf"'},
    )
