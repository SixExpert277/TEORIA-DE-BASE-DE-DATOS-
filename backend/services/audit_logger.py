import json
from datetime import date, datetime, time
from decimal import Decimal

from mysql.connector import Error

from database.connection import get_db_connection


def _serializar(valor):
    if valor is None:
        return None
    if isinstance(valor, str):
        return valor
    return json.dumps(valor, ensure_ascii=False, default=_convertir)


def _convertir(objeto):
    if isinstance(objeto, (datetime, date, time)):
        return objeto.isoformat()
    if isinstance(objeto, Decimal):
        return float(objeto)
    return str(objeto)


def log_audit(
    accion,
    detalle,
    resultado="EXITOSO",
    id_usuario=None,
    tabla_afectada="usuarios",
    datos_anteriores=None,
    datos_nuevos=None,
):
    consulta = (
        "INSERT INTO auditoria "
        "(id_usuario, accion, detalle, resultado, tabla_afectada, "
        "datos_anteriores, datos_nuevos, fecha, hora) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, CURDATE(), CURTIME())"
    )
    parametros = (
        id_usuario,
        accion,
        detalle,
        resultado,
        tabla_afectada,
        _serializar(datos_anteriores),
        _serializar(datos_nuevos),
    )
    conexion = None
    try:
        conexion = get_db_connection(autocommit=False)
        cursor = conexion.cursor()
        cursor.execute(consulta, parametros)
        conexion.commit()
        cursor.close()
        return True
    except Exception:
        if conexion is not None:
            try:
                conexion.rollback()
            except Error:
                pass
        return False
    finally:
        if conexion is not None:
            try:
                conexion.close()
            except Error:
                pass
