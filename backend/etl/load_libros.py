import argparse
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.common import (
    abrir_conexion,
    asegurar_catalogo,
    estado_final,
    finalizar_archivo,
    registrar_archivo,
    registrar_errores,
    resumen,
    upsert_por_lotes,
)

PATRON_RATING = re.compile(r"^\d(\.\d+)?$")
PATRON_FECHA = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")

SQL_LIBROS = (
    "INSERT INTO libros (titulo, isbn, isbn13, id_autor, id_editorial, id_idioma, numero_paginas, "
    "rating, numero_resenas, anio_publicacion, fecha_publicacion) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
    "ON DUPLICATE KEY UPDATE titulo = VALUES(titulo), isbn13 = VALUES(isbn13), id_autor = VALUES(id_autor), "
    "id_editorial = VALUES(id_editorial), id_idioma = VALUES(id_idioma), numero_paginas = VALUES(numero_paginas), "
    "rating = VALUES(rating), numero_resenas = VALUES(numero_resenas), "
    "anio_publicacion = VALUES(anio_publicacion), fecha_publicacion = VALUES(fecha_publicacion)"
)


def texto(valor):
    if valor is None:
        return None
    limpio = " ".join(str(valor).split())
    return limpio or None


def validar_alineacion(libro):
    rating = str(libro.get("average_rating", "")).strip()
    if not PATRON_RATING.match(rating):
        raise ValueError(f"fila desalineada: average_rating no numerico ({rating!r}), isbn={libro.get('isbn')!r}")
    if libro.get("FIELD13"):
        raise ValueError(f"fila desalineada: FIELD13 con contenido ({libro.get('FIELD13')!r})")


def entero_o_none(valor):
    limpio = texto(valor)
    if limpio is None or not re.fullmatch(r"\d+", limpio):
        return None
    numero = int(limpio)
    return numero if numero > 0 else None


def rating_o_none(valor):
    limpio = texto(valor)
    if limpio is None or not PATRON_RATING.match(limpio):
        return None
    numero = float(limpio)
    return numero if 0.0 <= numero <= 5.0 else None


def fecha_o_none(valor):
    limpio = texto(valor)
    if limpio is None or not PATRON_FECHA.match(limpio):
        return None
    try:
        return datetime.strptime(limpio, "%m/%d/%Y").date()
    except ValueError:
        return None


def normalizar_isbn(valor):
    limpio = texto(valor)
    if limpio is None:
        return None
    limpio = limpio.replace("-", "").upper()
    if re.fullmatch(r"\d{9}", limpio) or re.fullmatch(r"\d{12}", limpio):
        limpio = limpio.zfill(len(limpio) + 1)
    return limpio if re.fullmatch(r"\d{9}[\dX]|\d{13}", limpio) else None


def parsear_libro(libro):
    validar_alineacion(libro)
    isbn = normalizar_isbn(libro.get("isbn"))
    if isbn is None:
        raise ValueError("isbn invalido o vacio")
    titulo = texto(libro.get("title"))
    if titulo is None:
        raise ValueError("titulo vacio")
    autores = [texto(autor) for autor in str(libro.get("authors") or "").split("/")]
    autores = [autor for autor in autores if autor]
    fecha = fecha_o_none(libro.get("publication_date"))
    return {
        "titulo": titulo[:500],
        "isbn": isbn,
        "isbn13": normalizar_isbn(libro.get("isbn13")),
        "autor": autores[0] if autores else None,
        "editorial": texto(libro.get("publisher")),
        "idioma": texto(libro.get("language_code")),
        "numero_paginas": entero_o_none(libro.get("num_pages")),
        "rating": rating_o_none(libro.get("average_rating")),
        "numero_resenas": entero_o_none(libro.get("text_reviews_count")) or 0,
        "anio_publicacion": fecha.year if fecha else None,
        "fecha_publicacion": fecha,
    }


def leer_libros(filepath):
    with open(filepath, encoding="utf-8") as archivo:
        contenido = json.load(archivo)
    if not isinstance(contenido, list):
        raise ValueError("el archivo JSON debe contener una lista de libros")
    return contenido


def run_etl_libros(filepath, id_usuario):
    libros = leer_libros(filepath)
    conexion = abrir_conexion()
    id_archivo = registrar_archivo(conexion, id_usuario, filepath, "JSON")
    errores = []
    try:
        validos = []
        for numero, libro in enumerate(libros, start=1):
            try:
                validos.append((numero, parsear_libro(libro)))
            except Exception as error:
                errores.append((numero, error))

        autores = asegurar_catalogo(conexion, "autores", "id_autor", [l["autor"] for _, l in validos])
        editoriales = asegurar_catalogo(conexion, "editoriales", "id_editorial", [l["editorial"] for _, l in validos])
        idiomas = asegurar_catalogo(conexion, "idiomas", "id_idioma", [l["idioma"] for _, l in validos])

        filas = [
            (
                l["titulo"],
                l["isbn"],
                l["isbn13"],
                autores.get(l["autor"]),
                editoriales.get(l["editorial"]),
                idiomas.get(l["idioma"]),
                l["numero_paginas"],
                l["rating"],
                l["numero_resenas"],
                l["anio_publicacion"],
                l["fecha_publicacion"],
            )
            for _, l in validos
        ]
        errores += upsert_por_lotes(conexion, SQL_LIBROS, filas, [numero for numero, _ in validos])

        errores.sort(key=lambda item: item[0])
        registrar_errores(conexion, id_archivo, errores)
        finalizar_archivo(conexion, id_archivo, estado_final(len(errores), len(libros)))
    except Exception as error:
        conexion.rollback()
        registrar_errores(conexion, id_archivo, errores + [(0, f"fallo critico: {error}")])
        finalizar_archivo(conexion, id_archivo, "FALLIDO")
        raise
    finally:
        conexion.close()
    return resumen(id_archivo, len(libros), errores)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archivo", default=os.path.join("data_sources", "Books.json"))
    parser.add_argument("--id-usuario", type=int, default=None)
    argumentos = parser.parse_args()
    print(run_etl_libros(argumentos.archivo, argumentos.id_usuario))


if __name__ == "__main__":
    main()
