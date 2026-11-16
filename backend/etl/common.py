import os
import sys
from datetime import datetime

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database.connection import batch_size, get_connection


def abrir_conexion():
    return get_connection()


def registrar_archivo(conexion, id_usuario, filepath, tipo):
    ahora = datetime.now()
    cursor = conexion.cursor()
    cursor.execute(
        "INSERT INTO archivos (id_usuario, nombre_archivo, fecha, hora, tipo, estado) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (id_usuario, os.path.basename(filepath), ahora.date(), ahora.time().replace(microsecond=0), tipo, "PROCESANDO"),
    )
    id_archivo = cursor.lastrowid
    conexion.commit()
    cursor.close()
    return id_archivo


def registrar_errores(conexion, id_archivo, errores):
    if not errores:
        return
    cursor = conexion.cursor()
    cursor.executemany(
        "INSERT INTO errores_carga (id_archivo, numero_fila, motivo) VALUES (%s, %s, %s)",
        [(id_archivo, numero_fila, str(motivo)[:500]) for numero_fila, motivo in errores],
    )
    conexion.commit()
    cursor.close()


def finalizar_archivo(conexion, id_archivo, estado):
    cursor = conexion.cursor()
    cursor.execute("UPDATE archivos SET estado = %s WHERE id_archivo = %s", (estado, id_archivo))
    conexion.commit()
    cursor.close()


def estado_final(total_errores, total_procesados):
    if total_errores == 0:
        return "COMPLETADO"
    if total_errores >= total_procesados:
        return "FALLIDO"
    return "COMPLETADO_CON_ERRORES"


def resumen(id_archivo, procesados, errores):
    return {
        "registros_procesados": procesados,
        "registros_insertados": procesados - len(errores),
        "errores": [{"numero_fila": fila, "motivo": str(motivo)} for fila, motivo in errores],
        "id_archivo": id_archivo,
    }


def lotes(elementos, tamano=None):
    tamano = tamano or batch_size()
    for inicio in range(0, len(elementos), tamano):
        yield elementos[inicio:inicio + tamano]


def asegurar_catalogo(conexion, tabla, columna_id, nombres):
    nombres_unicos = sorted({nombre for nombre in nombres if nombre})
    cursor = conexion.cursor()
    for lote in lotes(nombres_unicos):
        cursor.executemany(
            f"INSERT INTO {tabla} (nombre) VALUES (%s) ON DUPLICATE KEY UPDATE nombre = nombre",
            [(nombre,) for nombre in lote],
        )
    conexion.commit()
    cursor.execute(f"SELECT {columna_id}, nombre FROM {tabla}")
    cache = {nombre: identificador for identificador, nombre in cursor.fetchall()}
    cursor.close()
    return cache


def upsert_por_lotes(conexion, sql, filas, numeros_fila):
    errores = []
    cursor = conexion.cursor()
    posicion = 0
    for lote in lotes(filas):
        lote_numeros = numeros_fila[posicion:posicion + len(lote)]
        posicion += len(lote)
        try:
            cursor.executemany(sql, lote)
            conexion.commit()
        except Exception:
            conexion.rollback()
            for fila, numero in zip(lote, lote_numeros):
                try:
                    cursor.execute(sql, fila)
                    conexion.commit()
                except Exception as error:
                    conexion.rollback()
                    errores.append((numero, error))
    cursor.close()
    return errores


def mapa_ids(conexion, tabla, columna_clave, columna_id, claves, condicion_extra="", parametros_extra=(), orden=""):
    claves = list(claves)
    resultado = {}
    cursor = conexion.cursor()
    for lote in lotes(claves):
        marcadores = ", ".join(["%s"] * len(lote))
        consulta = f"SELECT {columna_clave}, {columna_id} FROM {tabla} WHERE {columna_clave} IN ({marcadores})"
        if condicion_extra:
            consulta += f" AND {condicion_extra}"
        if orden:
            consulta += f" ORDER BY {orden}"
        cursor.execute(consulta, tuple(lote) + tuple(parametros_extra))
        resultado.update({clave: identificador for clave, identificador in cursor.fetchall()})
    cursor.close()
    return resultado
