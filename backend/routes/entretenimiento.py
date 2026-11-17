from flask import Blueprint, jsonify, request
from backend.database.queries import (
    TABLES,
    list_records,
    get_record,
    create_record,
    update_record,
    delete_record,
    peliculas_por_genero_y_fecha,
    peliculas_con_exactamente_n_generos,
    top_libros,
    top_y_peores_libros_por_anio,
    frecuencia_peliculas_por_genero,
    frecuencia_libros_por_anio,
    list_audit_table
)
from backend.routes.auth import token_required
from backend.services.audit_logger import log_action

entretenimiento_bp = Blueprint("entretenimiento", __name__, url_prefix="/api/entretenimiento")


def registrar_accion(accion, entidad, detalles):
    log_action(accion, entidad, detalles)


def respuesta_error(error, status=400):
    return jsonify({"ok": False, "mensaje": str(error)}), status


def validar_entidad(entidad):
    if entidad not in TABLES:
        raise ValueError("La entidad debe ser peliculas o libros")


def crear_rutas_crud(entidad):
    def listar():
        try:
            return jsonify({"ok": True, "datos": list_records(entidad, request.args.to_dict())})
        except Exception as error:
            return respuesta_error(error)

    def consultar(record_id):
        try:
            registro = get_record(entidad, record_id)
            if not registro:
                return respuesta_error("Registro no encontrado", 404)
            return jsonify({"ok": True, "datos": registro})
        except Exception as error:
            return respuesta_error(error)

    def insertar():
        try:
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return respuesta_error("El cuerpo debe ser un objeto JSON")
            resultado = create_record(entidad, payload)
            registrar_accion("CREATE", entidad, {"id": resultado["lastrowid"]})
            return jsonify({"ok": True, "mensaje": "Registro creado", "id": resultado["lastrowid"]}), 201
        except ValueError as error:
            return respuesta_error(error)
        except Exception as error:
            return respuesta_error(error, 500)

    def actualizar(record_id):
        try:
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return respuesta_error("El cuerpo debe ser un objeto JSON")
            actual = get_record(entidad, record_id)
            if not actual:
                return respuesta_error("Registro no encontrado", 404)
            resultado = update_record(entidad, record_id, payload)
            registrar_accion("UPDATE", entidad, {"id": record_id})
            return jsonify({"ok": True, "mensaje": "Registro actualizado", "filas_afectadas": resultado["rowcount"]})
        except ValueError as error:
            return respuesta_error(error)
        except Exception as error:
            return respuesta_error(error, 500)

    def eliminar(record_id):
        try:
            actual = get_record(entidad, record_id)
            if not actual:
                return respuesta_error("Registro no encontrado", 404)
            resultado = delete_record(entidad, record_id)
            registrar_accion("DELETE", entidad, {"id": record_id})
            return jsonify({"ok": True, "mensaje": "Registro eliminado", "filas_afectadas": resultado["rowcount"]})
        except Exception as error:
            return respuesta_error(error, 500)

    endpoint = entidad
    entretenimiento_bp.add_url_rule(f"/{entidad}", endpoint=f"{endpoint}_listar", view_func=token_required(listar), methods=["GET"])
    entretenimiento_bp.add_url_rule(f"/{entidad}/<int:record_id>", endpoint=f"{endpoint}_consultar", view_func=token_required(consultar), methods=["GET"])
    entretenimiento_bp.add_url_rule(f"/{entidad}", endpoint=f"{endpoint}_insertar", view_func=token_required(insertar), methods=["POST"])
    entretenimiento_bp.add_url_rule(f"/{entidad}/<int:record_id>", endpoint=f"{endpoint}_actualizar", view_func=token_required(actualizar), methods=["PUT"])
    entretenimiento_bp.add_url_rule(f"/{entidad}/<int:record_id>", endpoint=f"{endpoint}_eliminar", view_func=token_required(eliminar), methods=["DELETE"])


crear_rutas_crud("peliculas")
crear_rutas_crud("libros")


@entretenimiento_bp.get("/reportes/peliculas-por-genero")
@token_required
def reporte_peliculas_genero():
    try:
        f1 = request.args.get("f1")
        f2 = request.args.get("f2")
        orden = request.args.get("orden", "ASC")
        if not f1 or not f2:
            return respuesta_error("Debes enviar f1 y f2 en formato AAAA-MM-DD")
        return jsonify({"ok": True, "datos": peliculas_por_genero_y_fecha(f1, f2, orden)})
    except Exception as error:
        return respuesta_error(error)


@entretenimiento_bp.get("/reportes/peliculas-exactamente-n-generos")
@token_required
def reporte_peliculas_n_generos():
    try:
        n = int(request.args.get("n", ""))
        if n < 0:
            return respuesta_error("n debe ser mayor o igual a cero")
        orden = request.args.get("orden", "ASC")
        datos = peliculas_con_exactamente_n_generos(n, orden)
        return jsonify({"ok": True, "cantidad": len(datos), "datos": datos})
    except ValueError as error:
        return respuesta_error(error)
    except Exception as error:
        return respuesta_error(error)


@entretenimiento_bp.get("/reportes/top-libros")
@token_required
def reporte_top_libros():
    try:
        n = int(request.args.get("n", "10"))
        if n < 1 or n > 500:
            return respuesta_error("n debe estar entre 1 y 500")
        orden = request.args.get("orden", "DESC")
        return jsonify({"ok": True, "datos": top_libros(n, orden)})
    except ValueError as error:
        return respuesta_error(error)
    except Exception as error:
        return respuesta_error(error)


@entretenimiento_bp.get("/reportes/libros-rating-por-anio")
@token_required
def reporte_libros_por_anio():
    try:
        orden = request.args.get("orden", "ASC")
        return jsonify({"ok": True, "datos": top_y_peores_libros_por_anio(orden)})
    except Exception as error:
        return respuesta_error(error)


@entretenimiento_bp.get("/reportes/frecuencia-peliculas-genero")
@token_required
def reporte_frecuencia_peliculas():
    try:
        f1 = request.args.get("f1")
        f2 = request.args.get("f2")
        if not f1 or not f2:
            return respuesta_error("Debes enviar f1 y f2 en formato AAAA-MM-DD")
        return jsonify({"ok": True, "datos": frecuencia_peliculas_por_genero(f1, f2)})
    except Exception as error:
        return respuesta_error(error)


@entretenimiento_bp.get("/reportes/frecuencia-libros-anio")
@token_required
def reporte_frecuencia_libros():
    try:
        f1 = int(request.args.get("f1", ""))
        f2 = int(request.args.get("f2", ""))
        if f1 > f2:
            return respuesta_error("f1 no puede ser mayor que f2")
        return jsonify({"ok": True, "datos": frecuencia_libros_por_anio(f1, f2)})
    except ValueError as error:
        return respuesta_error(error)
    except Exception as error:
        return respuesta_error(error)


@entretenimiento_bp.get("/auditoria/<string:tabla>")
@token_required
def consultar_auditoria(tabla):
    try:
        if tabla not in {"auditoria", "archivos"}:
            return respuesta_error("La tabla debe ser auditoria o archivos")
        limite = max(1, min(int(request.args.get("limite", "50")), 200))
        desde = max(0, int(request.args.get("desde", "0")))
        return jsonify({"ok": True, "datos": list_audit_table(tabla, limite, desde)})
    except ValueError as error:
        return respuesta_error(error)
    except Exception as error:
        return respuesta_error(error, 500)
