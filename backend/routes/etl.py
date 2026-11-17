import csv
import io
import json
from datetime import date, datetime
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename
from backend.database.queries import issue8_insert_incremental, issue8_insert_metadata_record
from backend.routes.auth import token_required
from backend.services.audit_logger import log_action

etl_bp = Blueprint("etl", __name__, url_prefix="/api/etl")
EXTENSIONES_PERMITIDAS = {"xlsx", "dat", "json"}
TIPOS_PERMITIDOS = {"peliculas", "libros"}
TAMANO_MAXIMO = 10 * 1024 * 1024


def normalizar_valor(value):
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def leer_json(contenido):
    data = json.loads(contenido.decode("utf-8-sig"))
    if isinstance(data, dict):
        data = data.get("datos", data.get("data", [data]))
    if not isinstance(data, list):
        raise ValueError("El JSON debe contener una lista de registros")
    return data


def leer_xlsx(contenido):
    try:
        import pandas as pd
    except ImportError as error:
        raise ValueError("Para leer XLSX debes instalar pandas y openpyxl") from error
    frame = pd.read_excel(io.BytesIO(contenido))
    frame = frame.where(frame.notna(), None)
    return frame.to_dict(orient="records")


def leer_dat(contenido):
    texto = contenido.decode("utf-8-sig")
    try:
        dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t|")
    except csv.Error:
        dialecto = csv.excel
    return list(csv.DictReader(io.StringIO(texto), dialect=dialecto))


def leer_archivo(nombre, contenido):
    extension = nombre.rsplit(".", 1)[-1].lower()
    if extension == "json":
        return leer_json(contenido)
    if extension == "xlsx":
        return leer_xlsx(contenido)
    if extension == "dat":
        return leer_dat(contenido)
    raise ValueError("Extensión no permitida")


def guardar_error(nombre_archivo, numero_fila, mensaje):
    issue8_insert_metadata_record("errores_carga", {
        "nombre_archivo": nombre_archivo,
        "archivo": nombre_archivo,
        "fila": numero_fila,
        "numero_fila": numero_fila,
        "mensaje_error": mensaje,
        "descripcion": mensaje,
        "error": mensaje,
        "fecha_error": datetime.now(),
        "fecha": datetime.now()
    })


def guardar_archivo(nombre_archivo, extension, procesados, errores, estado):
    issue8_insert_metadata_record("archivos", {
        "nombre_archivo": nombre_archivo,
        "archivo": nombre_archivo,
        "tipo_archivo": extension,
        "extension": extension,
        "registros_procesados": procesados,
        "filas_procesadas": procesados,
        "total_registros": procesados,
        "registros_error": errores,
        "cantidad_errores": errores,
        "estado": estado,
        "fecha_carga": datetime.now(),
        "created_at": datetime.now()
    })


@etl_bp.post("/upload")
@token_required
def cargar_archivo():
    archivo = request.files.get("archivo")
    tipo = request.form.get("tipo", "").strip().lower()
    if not archivo or not archivo.filename:
        return jsonify({"ok": False, "mensaje": "Debes adjuntar un archivo en el campo archivo"}), 400
    if tipo not in TIPOS_PERMITIDOS:
        return jsonify({"ok": False, "mensaje": "El campo tipo debe ser peliculas o libros"}), 400
    nombre = secure_filename(archivo.filename)
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if extension not in EXTENSIONES_PERMITIDAS:
        return jsonify({"ok": False, "mensaje": "Solo se permiten archivos XLSX, DAT o JSON"}), 400
    contenido = archivo.read()
    if len(contenido) > TAMANO_MAXIMO:
        return jsonify({"ok": False, "mensaje": "El archivo supera el límite de 10 MB"}), 413
    try:
        registros = leer_archivo(nombre, contenido)
        registros_validos = []
        errores = []
        for indice, registro in enumerate(registros, start=2):
            if not isinstance(registro, dict):
                errores.append({"fila": indice, "error": "Cada registro debe ser un objeto"})
                continue
            normalizado = {str(key).strip(): normalizar_valor(value) for key, value in registro.items()}
            normalizado = {key: value for key, value in normalizado.items() if value is not None}
            if not normalizado.get("titulo"):
                errores.append({"fila": indice, "error": "El campo titulo es obligatorio"})
                continue
            registros_validos.append(normalizado)
        procesados = issue8_insert_incremental(tipo, registros_validos)
        for error in errores:
            try:
                guardar_error(nombre, error["fila"], error["error"])
            except Exception:
                pass
        estado = "COMPLETADO" if not errores else "COMPLETADO_CON_ERRORES"
        guardar_archivo(nombre, extension, procesados, len(errores), estado)
        log_action("ETL_UPLOAD", tipo, {"archivo": nombre, "procesados": procesados, "errores": len(errores)})
        return jsonify({
            "ok": True,
            "archivo": nombre,
            "tipo": tipo,
            "registros_recibidos": len(registros),
            "registros_insertados": procesados,
            "registros_con_error": len(errores),
            "errores": errores,
            "estado": estado
        }), 200
    except ValueError as error:
        return jsonify({"ok": False, "mensaje": str(error)}), 400
    except Exception as error:
        try:
            guardar_archivo(nombre, extension, 0, 1, "FALLIDO")
        except Exception:
            pass
        return jsonify({"ok": False, "mensaje": "No fue posible procesar el archivo", "detalle": str(error)}), 500
