import argparse
import os
import sys
from datetime import date, datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.common import (
    abrir_conexion,
    asegurar_catalogo,
    estado_final,
    finalizar_archivo,
    mapa_ids,
    registrar_archivo,
    registrar_errores,
    resumen,
    upsert_por_lotes,
)

PORCENTAJE_APORTE_PENSION = 0.04
PREFIJO_DOCUMENTO = "DOC-"
PERIODO_POR_DEFECTO = "2022-03-01"
MARCA_NOVEDAD = "X"

SQL_PERSONAS = (
    "INSERT INTO personas (numero_documento, nombre_completo) VALUES (%s, %s) "
    "ON DUPLICATE KEY UPDATE nombre_completo = VALUES(nombre_completo)"
)
SQL_EMPLEADOS = (
    "INSERT INTO empleados (codigo_personal, id_persona, id_cargo, id_dependencia, salario, fecha_ingreso) "
    "VALUES (%s, %s, %s, %s, %s, %s) "
    "ON DUPLICATE KEY UPDATE id_persona = VALUES(id_persona), id_cargo = VALUES(id_cargo), "
    "id_dependencia = VALUES(id_dependencia), salario = VALUES(salario), fecha_ingreso = VALUES(fecha_ingreso)"
)
SQL_AFILIACIONES = (
    "INSERT INTO afiliaciones_empleado (id_empleado, id_eps, id_arl, id_fondo_pension, fecha_inicio) "
    "VALUES (%s, %s, %s, %s, %s) "
    "ON DUPLICATE KEY UPDATE id_eps = VALUES(id_eps), id_arl = VALUES(id_arl), "
    "id_fondo_pension = VALUES(id_fondo_pension)"
)
SQL_NOMINAS = (
    "INSERT INTO nominas (periodo_fecha) VALUES (%s) "
    "ON DUPLICATE KEY UPDATE periodo_fecha = VALUES(periodo_fecha)"
)
SQL_DETALLE = (
    "INSERT INTO detalle_nomina (id_nomina, id_afiliacion_empleado, valor_aporte_pension, periodo_fecha) "
    "VALUES (%s, %s, %s, %s) "
    "ON DUPLICATE KEY UPDATE valor_aporte_pension = VALUES(valor_aporte_pension), "
    "periodo_fecha = VALUES(periodo_fecha)"
)
SQL_NOVEDADES = (
    "INSERT INTO novedades (id_detalle_nomina, id_tipo_novedad, detalle, dias_reportados) "
    "VALUES (%s, %s, %s, %s) "
    "ON DUPLICATE KEY UPDATE detalle = VALUES(detalle), dias_reportados = VALUES(dias_reportados)"
)


def es_vacio(valor):
    return valor is None or (not isinstance(valor, str) and pd.isna(valor)) or str(valor).strip() == ""


def texto_obligatorio(valor, nombre_campo):
    if es_vacio(valor):
        raise ValueError(f"{nombre_campo} vacio")
    return " ".join(str(valor).split())


def fecha_compacta(valor):
    if es_vacio(valor):
        raise ValueError("fecha de ingreso vacia")
    return datetime.strptime(str(int(valor)), "%Y%m%d").date()


def fecha_opcional(valor):
    if es_vacio(valor):
        return None
    return pd.Timestamp(valor).date()


def entero_no_negativo(valor, nombre_campo):
    if es_vacio(valor):
        return 0
    numero = int(float(valor))
    if numero < 0:
        raise ValueError(f"{nombre_campo} negativo")
    return numero


def validar_empleado(fila, prefijo_documento=PREFIJO_DOCUMENTO):
    codigo = int(float(fila["CÓDIGO"])) if not es_vacio(fila["CÓDIGO"]) else None
    if codigo is None:
        raise ValueError("codigo vacio")
    salario = fila["SUELDO"]
    if es_vacio(salario) or float(salario) <= 0:
        raise ValueError("sueldo invalido")
    return {
        "codigo_personal": str(codigo),
        "numero_documento": f"{prefijo_documento}{codigo}",
        "nombre_completo": texto_obligatorio(fila["NOMBRE DEL EMPLEADO"], "nombre"),
        "dependencia": texto_obligatorio(fila["DEPENDENCIA"], "dependencia"),
        "cargo": texto_obligatorio(fila["CARGO"], "cargo"),
        "fecha_ingreso": fecha_compacta(fila["FECHA INGRESO"]),
        "eps": texto_obligatorio(fila["EPS"], "eps"),
        "arl": texto_obligatorio(fila["ARL"], "arl"),
        "fondo_pension": texto_obligatorio(fila["PENSIÓN"], "pension"),
        "salario": round(float(salario), 2),
    }


def normalizar_periodo(valor):
    if isinstance(valor, date):
        return valor.replace(day=1)
    return datetime.strptime(str(valor)[:7] + "-01", "%Y-%m-%d").date()


def valor_monetario(valor):
    if es_vacio(valor):
        return 0
    return int(round(float(valor)))


def construir_novedades(fila):
    novedades = []
    bonificacion = valor_monetario(fila.get("BONIFICACIÓN"))
    if bonificacion > 0:
        novedades.append(("BONIFICACION", f"Valor bonificacion: {bonificacion}", 0))
    transporte = valor_monetario(fila.get("TRANSPORTE"))
    if transporte > 0:
        novedades.append(("TRANSPORTE", f"Valor auxilio de transporte: {transporte}", 0))
    if str(fila.get("NOVEDAD INCAPACIDAD", "")).strip().upper() == MARCA_NOVEDAD:
        inicio = fecha_opcional(fila.get("FECHA INICIO INCAPACIDAD"))
        fin = fecha_opcional(fila.get("FECHA TERMINACIÓN INCAPACIDAD"))
        dias = entero_no_negativo(fila.get("NUMERO DIAS INCAPACIDADES EN EL MES"), "dias incapacidad")
        novedades.append(("INCAPACIDAD", f"Incapacidad del {inicio} al {fin}", dias))
    if str(fila.get("NOVEDAD VACACIONES", "")).strip().upper() == MARCA_NOVEDAD:
        inicio = fecha_opcional(fila.get("FECHA DE INICIO DE VACACIONES"))
        fin = fecha_opcional(fila.get("FECHA TERMINACION DE VACACIONES"))
        dias = entero_no_negativo(fila.get("NUMERO DE DIAS VACACIONES"), "dias vacaciones")
        novedades.append(("VACACIONES", f"Vacaciones del {inicio} al {fin}", dias))
    return novedades


def cargar_maestro(conexion, dataframe, prefijo_documento):
    validos, errores = [], []
    for indice, fila in dataframe.iterrows():
        numero_fila = indice + 2
        try:
            validos.append((numero_fila, validar_empleado(fila, prefijo_documento)))
        except Exception as error:
            errores.append((numero_fila, f"[maestro] {error}"))
    if not validos:
        return {}, errores

    cache = {
        "cargos": asegurar_catalogo(conexion, "cargos", "id_cargo", [v["cargo"] for _, v in validos]),
        "dependencias": asegurar_catalogo(conexion, "dependencias", "id_dependencia", [v["dependencia"] for _, v in validos]),
        "eps": asegurar_catalogo(conexion, "eps", "id_eps", [v["eps"] for _, v in validos]),
        "arl": asegurar_catalogo(conexion, "arl", "id_arl", [v["arl"] for _, v in validos]),
        "fondos": asegurar_catalogo(conexion, "fondos_pension", "id_fondo_pension", [v["fondo_pension"] for _, v in validos]),
    }

    errores += [
        (numero, f"[maestro] {error}")
        for numero, error in upsert_por_lotes(
            conexion,
            SQL_PERSONAS,
            [(v["numero_documento"], v["nombre_completo"]) for _, v in validos],
            [numero for numero, _ in validos],
        )
    ]
    ids_personas = mapa_ids(conexion, "personas", "numero_documento", "id_persona", [v["numero_documento"] for _, v in validos])

    con_persona = [(n, v) for n, v in validos if v["numero_documento"] in ids_personas]
    errores += [(n, "[maestro] persona no registrada") for n, v in validos if v["numero_documento"] not in ids_personas]
    errores += [
        (numero, f"[maestro] {error}")
        for numero, error in upsert_por_lotes(
            conexion,
            SQL_EMPLEADOS,
            [
                (
                    v["codigo_personal"],
                    ids_personas[v["numero_documento"]],
                    cache["cargos"][v["cargo"]],
                    cache["dependencias"][v["dependencia"]],
                    v["salario"],
                    v["fecha_ingreso"],
                )
                for _, v in con_persona
            ],
            [numero for numero, _ in con_persona],
        )
    ]
    ids_empleados = mapa_ids(conexion, "empleados", "codigo_personal", "id_empleado", [v["codigo_personal"] for _, v in con_persona])

    con_empleado = [(n, v) for n, v in con_persona if v["codigo_personal"] in ids_empleados]
    errores += [(n, "[maestro] empleado no registrado") for n, v in con_persona if v["codigo_personal"] not in ids_empleados]
    errores += [
        (numero, f"[maestro] {error}")
        for numero, error in upsert_por_lotes(
            conexion,
            SQL_AFILIACIONES,
            [
                (
                    ids_empleados[v["codigo_personal"]],
                    cache["eps"][v["eps"]],
                    cache["arl"][v["arl"]],
                    cache["fondos"][v["fondo_pension"]],
                    v["fecha_ingreso"],
                )
                for _, v in con_empleado
            ],
            [numero for numero, _ in con_empleado],
        )
    ]
    ids_afiliaciones = mapa_ids(
        conexion,
        "afiliaciones_empleado",
        "id_empleado",
        "id_afiliacion_empleado",
        ids_empleados.values(),
        orden="fecha_inicio ASC",
    )
    afiliacion_por_codigo = {
        codigo: ids_afiliaciones[id_empleado]
        for codigo, id_empleado in ids_empleados.items()
        if id_empleado in ids_afiliaciones
    }
    salarios = {v["codigo_personal"]: v["salario"] for _, v in con_empleado}
    return {"afiliaciones": afiliacion_por_codigo, "salarios": salarios}, errores


def cargar_hoja_mensual(conexion, hoja, dataframe, periodo, contexto):
    errores = []
    cursor = conexion.cursor()
    cursor.execute(SQL_NOMINAS, (periodo,))
    conexion.commit()
    cursor.execute("SELECT id_nomina FROM nominas WHERE periodo_fecha = %s", (periodo,))
    id_nomina = cursor.fetchone()[0]
    cursor.close()

    validas = []
    for indice, fila in dataframe.iterrows():
        numero_fila = indice + 2
        try:
            codigo = str(int(float(fila["CÓDIGO"])))
            id_afiliacion = contexto["afiliaciones"].get(codigo)
            if id_afiliacion is None:
                raise ValueError(f"codigo {codigo} sin afiliacion en el maestro")
            aporte = round(contexto["salarios"][codigo] * PORCENTAJE_APORTE_PENSION, 2)
            validas.append((numero_fila, id_afiliacion, aporte, construir_novedades(fila)))
        except Exception as error:
            errores.append((numero_fila, f"[{hoja}] {error}"))

    errores += [
        (numero, f"[{hoja}] {error}")
        for numero, error in upsert_por_lotes(
            conexion,
            SQL_DETALLE,
            [(id_nomina, id_afiliacion, aporte, periodo) for _, id_afiliacion, aporte, _ in validas],
            [numero for numero, _, _, _ in validas],
        )
    ]
    ids_detalle = mapa_ids(
        conexion,
        "detalle_nomina",
        "id_afiliacion_empleado",
        "id_detalle_nomina",
        [id_afiliacion for _, id_afiliacion, _, _ in validas],
        condicion_extra="id_nomina = %s",
        parametros_extra=(id_nomina,),
    )

    nombres_tipos = [tipo for _, _, _, novedades in validas for tipo, _, _ in novedades]
    tipos = asegurar_catalogo(conexion, "tipos_novedad", "id_tipo_novedad", nombres_tipos)
    filas_novedades, numeros_novedades = [], []
    for numero, id_afiliacion, _, novedades in validas:
        if id_afiliacion not in ids_detalle:
            errores.append((numero, f"[{hoja}] detalle de nomina no registrado"))
            continue
        for tipo, detalle, dias in novedades:
            filas_novedades.append((ids_detalle[id_afiliacion], tipos[tipo], detalle, dias))
            numeros_novedades.append(numero)
    errores += [
        (numero, f"[{hoja}] {error}")
        for numero, error in upsert_por_lotes(conexion, SQL_NOVEDADES, filas_novedades, numeros_novedades)
    ]
    return errores


def run_etl_nomina(filepath, id_usuario, periodo_fecha=PERIODO_POR_DEFECTO, prefijo_documento=PREFIJO_DOCUMENTO):
    hojas = pd.read_excel(filepath, sheet_name=None)
    nombres_hojas = list(hojas.keys())
    maestro, mensuales = hojas[nombres_hojas[0]], nombres_hojas[1:]
    procesados = len(maestro) + sum(len(hojas[nombre]) for nombre in mensuales)

    conexion = abrir_conexion()
    id_archivo = registrar_archivo(conexion, id_usuario, filepath, "XLSX")
    errores = []
    try:
        contexto, errores_maestro = cargar_maestro(conexion, maestro, prefijo_documento)
        errores += errores_maestro
        for nombre in mensuales:
            if not contexto:
                errores += [(indice + 2, f"[{nombre}] maestro sin empleados validos") for indice in hojas[nombre].index]
                continue
            periodo = normalizar_periodo(periodo_fecha)
            errores += cargar_hoja_mensual(conexion, nombre, hojas[nombre], periodo, contexto)
        registrar_errores(conexion, id_archivo, errores)
        finalizar_archivo(conexion, id_archivo, estado_final(len(errores), procesados))
    except Exception as error:
        conexion.rollback()
        registrar_errores(conexion, id_archivo, errores + [(0, f"fallo critico: {error}")])
        finalizar_archivo(conexion, id_archivo, "FALLIDO")
        raise
    finally:
        conexion.close()
    return resumen(id_archivo, procesados, errores)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archivo", default=os.path.join("data_sources", "Nomina.xlsx"))
    parser.add_argument("--id-usuario", type=int, default=None)
    parser.add_argument("--periodo-fecha", default=PERIODO_POR_DEFECTO)
    parser.add_argument("--prefijo-documento", default=PREFIJO_DOCUMENTO)
    argumentos = parser.parse_args()
    print(run_etl_nomina(argumentos.archivo, argumentos.id_usuario, argumentos.periodo_fecha, argumentos.prefijo_documento))


if __name__ == "__main__":
    main()
