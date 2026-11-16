import argparse
import os
import re
import sys
from datetime import date

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

SEPARADOR_CAMPOS = "::"
SEPARADOR_LISTAS = "|"
SIN_GENEROS = "(no genres listed)"
PATRON_TITULO = re.compile(r"^(?P<titulo>.*?)\s*\((?P<anio>\d{4})\)\s*$")
CODIFICACIONES = ("utf-8", "latin-1")

SQL_PELICULAS = (
    "INSERT INTO peliculas (id_pelicula, titulo, fecha_estreno) VALUES (%s, %s, %s) "
    "ON DUPLICATE KEY UPDATE titulo = VALUES(titulo), fecha_estreno = VALUES(fecha_estreno)"
)
SQL_PELICULA_GENEROS = (
    "INSERT INTO pelicula_generos (id_pelicula, id_genero) VALUES (%s, %s) "
    "ON DUPLICATE KEY UPDATE id_genero = VALUES(id_genero)"
)
SQL_PARTICIPANTES = (
    "INSERT INTO pelicula_participantes (id_pelicula, id_artista, tipo_rol) VALUES (%s, %s, %s) "
    "ON DUPLICATE KEY UPDATE tipo_rol = VALUES(tipo_rol)"
)


def leer_lineas(filepath):
    for codificacion in CODIFICACIONES:
        try:
            with open(filepath, encoding=codificacion) as archivo:
                return archivo.read().splitlines()
        except UnicodeDecodeError:
            continue
    raise ValueError("codificacion no soportada")


def lista_separada(valor):
    return [elemento.strip() for elemento in valor.split(SEPARADOR_LISTAS) if elemento.strip()]


def parsear_linea(linea):
    campos = linea.split(SEPARADOR_CAMPOS)
    if len(campos) < 3:
        raise ValueError("linea con menos de 3 campos")
    identificador = int(campos[0].strip())
    coincidencia = PATRON_TITULO.match(campos[1].strip())
    if coincidencia:
        titulo, anio = coincidencia.group("titulo"), int(coincidencia.group("anio"))
        fecha_estreno = date(anio, 1, 1)
    else:
        titulo, fecha_estreno = campos[1].strip(), None
    if not titulo:
        raise ValueError("titulo vacio")
    generos = [genero for genero in lista_separada(campos[2]) if genero != SIN_GENEROS]
    directores = lista_separada(campos[3]) if len(campos) > 3 else []
    actores = lista_separada(campos[4]) if len(campos) > 4 else []
    return {
        "id_pelicula": identificador,
        "titulo": titulo[:255],
        "fecha_estreno": fecha_estreno,
        "generos": generos,
        "directores": directores,
        "actores": actores,
    }


def run_etl_peliculas(filepath, id_usuario):
    lineas = [linea for linea in leer_lineas(filepath) if linea.strip()]
    conexion = abrir_conexion()
    id_archivo = registrar_archivo(conexion, id_usuario, filepath, "DAT")
    errores = []
    try:
        validas = []
        for numero, linea in enumerate(lineas, start=1):
            try:
                validas.append((numero, parsear_linea(linea)))
            except Exception as error:
                errores.append((numero, error))

        generos = asegurar_catalogo(conexion, "generos", "id_genero", [g for _, p in validas for g in p["generos"]])
        artistas = asegurar_catalogo(
            conexion, "artistas", "id_artista", [a for _, p in validas for a in p["directores"] + p["actores"]]
        )

        errores += upsert_por_lotes(
            conexion,
            SQL_PELICULAS,
            [(p["id_pelicula"], p["titulo"], p["fecha_estreno"]) for _, p in validas],
            [numero for numero, _ in validas],
        )
        existentes = mapa_ids(conexion, "peliculas", "id_pelicula", "id_pelicula", [p["id_pelicula"] for _, p in validas])
        persistidas = [(n, p) for n, p in validas if p["id_pelicula"] in existentes]

        filas_generos, numeros_generos = [], []
        filas_participantes, numeros_participantes = [], []
        for numero, pelicula in persistidas:
            for genero in pelicula["generos"]:
                filas_generos.append((pelicula["id_pelicula"], generos[genero]))
                numeros_generos.append(numero)
            for director in pelicula["directores"]:
                filas_participantes.append((pelicula["id_pelicula"], artistas[director], "DIRECTOR"))
                numeros_participantes.append(numero)
            for actor in pelicula["actores"]:
                filas_participantes.append((pelicula["id_pelicula"], artistas[actor], "ACTOR"))
                numeros_participantes.append(numero)

        errores += upsert_por_lotes(conexion, SQL_PELICULA_GENEROS, filas_generos, numeros_generos)
        errores += upsert_por_lotes(conexion, SQL_PARTICIPANTES, filas_participantes, numeros_participantes)

        errores.sort(key=lambda item: item[0])
        registrar_errores(conexion, id_archivo, errores)
        finalizar_archivo(conexion, id_archivo, estado_final(len(errores), len(lineas)))
    except Exception as error:
        conexion.rollback()
        registrar_errores(conexion, id_archivo, errores + [(0, f"fallo critico: {error}")])
        finalizar_archivo(conexion, id_archivo, "FALLIDO")
        raise
    finally:
        conexion.close()
    return resumen(id_archivo, len(lineas), errores)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archivo", default=os.path.join("data_sources", "movies.dat"))
    parser.add_argument("--id-usuario", type=int, default=None)
    argumentos = parser.parse_args()
    print(run_etl_peliculas(argumentos.archivo, argumentos.id_usuario))


if __name__ == "__main__":
    main()
