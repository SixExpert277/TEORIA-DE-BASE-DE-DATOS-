import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NOMBRE_EMPRESA = "EntreCOL+ / ColPlus-Solutions"
LEYENDA_CONFIDENCIAL = "Documento confidencial de uso interno. Su reproducción o divulgación sin autorización está prohibida."
COLOR_PRIMARIO = colors.HexColor("#1F3A5F")
COLOR_ACENTO = colors.HexColor("#E8A33D")
COLOR_FILA_ALTERNA = colors.HexColor("#EEF2F7")
MARGEN = 1.5 * cm
ALTO_ENCABEZADO = 2.6 * cm
ALTO_PIE = 1.4 * cm
TEXTO_SIN_RESULTADOS = "No se encontraron registros para los filtros aplicados."

ESTILOS = getSampleStyleSheet()
ESTILO_CELDA = ParagraphStyle("celda", parent=ESTILOS["BodyText"], fontSize=8, leading=10)
ESTILO_CABECERA = ParagraphStyle(
    "cabecera", parent=ESTILO_CELDA, textColor=colors.white, fontName="Helvetica-Bold"
)
ESTILO_SECCION = ParagraphStyle(
    "seccion", parent=ESTILOS["Heading3"], textColor=COLOR_PRIMARIO, spaceBefore=10, spaceAfter=4
)
ESTILO_RESUMEN = ParagraphStyle("resumen", parent=ESTILOS["BodyText"], fontSize=9, leading=12)
ESTILO_AVISO = ParagraphStyle(
    "aviso", parent=ESTILOS["BodyText"], fontSize=9, textColor=colors.HexColor("#7A4B00")
)


def formatear_fecha(valor):
    if valor is None:
        return ""
    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def formatear_valor(valor):
    if valor is None:
        return ""
    if hasattr(valor, "strftime"):
        return formatear_fecha(valor)
    if isinstance(valor, float) or valor.__class__.__name__ == "Decimal":
        return f"{valor:,.2f}"
    return str(valor)


class LienzoNumerado(canvas.Canvas):
    def __init__(self, *args, titulo="", filtros="", usuario="", generado="", **kwargs):
        super().__init__(*args, **kwargs)
        self.titulo_reporte = titulo
        self.filtros_reporte = filtros
        self.usuario_reporte = usuario
        self.generado_reporte = generado
        self.estados_paginas = []

    def showPage(self):
        self.estados_paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self.estados_paginas)
        for estado in self.estados_paginas:
            self.__dict__.update(estado)
            self.dibujar_encabezado()
            self.dibujar_pie(total)
            super().showPage()
        super().save()

    def dibujar_logo(self, x, y):
        self.setFillColor(COLOR_PRIMARIO)
        self.roundRect(x, y, 1.3 * cm, 1.3 * cm, 0.2 * cm, stroke=0, fill=1)
        self.setFillColor(COLOR_ACENTO)
        self.circle(x + 0.65 * cm, y + 0.65 * cm, 0.35 * cm, stroke=0, fill=1)
        self.setFillColor(colors.white)
        self.setFont("Helvetica-Bold", 11)
        self.drawCentredString(x + 0.65 * cm, y + 0.52 * cm, "E+")

    def dibujar_encabezado(self):
        ancho, alto = self._pagesize
        y_base = alto - ALTO_ENCABEZADO
        self.dibujar_logo(MARGEN, y_base + 0.6 * cm)
        self.setFillColor(COLOR_PRIMARIO)
        self.setFont("Helvetica-Bold", 13)
        self.drawString(MARGEN + 1.6 * cm, alto - 1.2 * cm, NOMBRE_EMPRESA)
        self.setFont("Helvetica-Bold", 11)
        self.drawString(MARGEN + 1.6 * cm, alto - 1.7 * cm, self.titulo_reporte)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#444444"))
        self.drawRightString(ancho - MARGEN, alto - 1.1 * cm, f"Generado: {self.generado_reporte}")
        self.drawRightString(ancho - MARGEN, alto - 1.5 * cm, f"Usuario auditor: {self.usuario_reporte}")
        self.drawString(MARGEN + 1.6 * cm, alto - 2.1 * cm, self.filtros_reporte[:180])
        self.setStrokeColor(COLOR_ACENTO)
        self.setLineWidth(1.5)
        self.line(MARGEN, y_base + 0.3 * cm, ancho - MARGEN, y_base + 0.3 * cm)

    def dibujar_pie(self, total):
        ancho, _ = self._pagesize
        self.setStrokeColor(COLOR_PRIMARIO)
        self.setLineWidth(0.5)
        self.line(MARGEN, ALTO_PIE, ancho - MARGEN, ALTO_PIE)
        self.setFillColor(colors.HexColor("#555555"))
        self.setFont("Helvetica-Oblique", 7)
        self.drawString(MARGEN, ALTO_PIE - 0.45 * cm, LEYENDA_CONFIDENCIAL)
        self.setFont("Helvetica", 8)
        self.drawRightString(ancho - MARGEN, ALTO_PIE - 0.45 * cm, f"Página {self._pageNumber} de {total}")


def construir_tabla(columnas, filas, ancho_disponible):
    datos = [[Paragraph(escape(str(columna)), ESTILO_CABECERA) for columna in columnas]]
    for fila in filas:
        datos.append([Paragraph(escape(formatear_valor(valor)), ESTILO_CELDA) for valor in fila])
    proporcion = ancho_disponible / len(columnas)
    tabla = Table(datos, colWidths=[proporcion] * len(columnas), repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARIO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B8C2CF")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for indice in range(2, len(datos), 2):
        estilo.append(("BACKGROUND", (0, indice), (-1, indice), COLOR_FILA_ALTERNA))
    tabla.setStyle(TableStyle(estilo))
    return tabla


def construir_seccion(seccion, ancho_disponible):
    elementos = []
    if seccion.get("titulo"):
        elementos.append(Paragraph(escape(seccion["titulo"]), ESTILO_SECCION))
    for linea in seccion.get("resumen", []):
        elementos.append(Paragraph(escape(linea), ESTILO_RESUMEN))
    if seccion.get("resumen"):
        elementos.append(Spacer(1, 4))
    filas = seccion.get("filas", [])
    if filas:
        elementos.append(construir_tabla(seccion["columnas"], filas, ancho_disponible))
    else:
        elementos.append(Paragraph(TEXTO_SIN_RESULTADOS, ESTILO_AVISO))
    if seccion.get("aviso"):
        elementos.append(Spacer(1, 3))
        elementos.append(Paragraph(escape(seccion["aviso"]), ESTILO_AVISO))
    return elementos


def generar_pdf(titulo, filtros, usuario, secciones):
    buffer = io.BytesIO()
    generado = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    pagina = landscape(A4)
    ancho_disponible = pagina[0] - 2 * MARGEN

    def fabrica_lienzo(*args, **kwargs):
        return LienzoNumerado(
            *args, titulo=titulo, filtros=filtros, usuario=usuario, generado=generado, **kwargs
        )

    documento = SimpleDocTemplate(
        buffer,
        pagesize=pagina,
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=ALTO_ENCABEZADO + 0.3 * cm,
        bottomMargin=ALTO_PIE + 0.5 * cm,
        title=f"{NOMBRE_EMPRESA} - {titulo}",
        author=usuario,
    )
    elementos = []
    for seccion in secciones:
        elementos.extend(construir_seccion(seccion, ancho_disponible))
    if not elementos:
        elementos.append(Paragraph(TEXTO_SIN_RESULTADOS, ESTILO_AVISO))
    documento.build(elementos, canvasmaker=fabrica_lienzo)
    buffer.seek(0)
    return buffer


def seccion_tabla(titulo, columnas, filas, resumen=None, aviso=None):
    return {"titulo": titulo, "columnas": columnas, "filas": filas, "resumen": resumen or [], "aviso": aviso}


def pdf_nomina(modalidad, conteos, filas, filtros, usuario, aviso=None):
    columnas = ["Código", "Nombre", "Dependencia", "Cargo", "Salario"]
    titulos = {
        "general": "Nómina general",
        "por_dependencia": "Nómina por dependencia",
        "por_cargo_dependencia": "Nómina por dependencia y cargo",
    }
    secciones = []
    if conteos:
        etiqueta = "Conteo por dependencia" if modalidad == "por_dependencia" else "Conteo por dependencia y cargo"
        secciones.append(seccion_tabla(etiqueta, conteos["columnas"], conteos["filas"]))
    secciones.append(
        seccion_tabla(titulos[modalidad], columnas, filas, [f"Total de empleados: {len(filas)}"], aviso)
    )
    return generar_pdf("Reporte de Nómina", filtros, usuario, secciones)


def pdf_informacion_personal(empleado, novedades, filtros, usuario):
    secciones = []
    if empleado:
        ficha = [
            ("Código Personal", empleado["codigo_personal"]),
            ("Nombre completo", empleado["nombre_completo"]),
            ("Dependencia", empleado["dependencia"]),
            ("Cargo", empleado["cargo"]),
            ("Fecha de ingreso", formatear_fecha(empleado["fecha_ingreso"])),
            ("EPS", empleado["eps"]),
            ("Aporte Pensión", empleado["aporte_pension"]),
            ("Salario", empleado["salario"]),
        ]
        secciones.append(seccion_tabla("Ficha del empleado", ["Campo", "Valor"], ficha))
        secciones.append(
            seccion_tabla(
                "Novedades del empleado",
                ["Período", "Tipo de novedad", "Detalle", "Días reportados"],
                novedades,
                [f"Total de novedades: {len(novedades)}"],
            )
        )
    else:
        secciones.append(seccion_tabla("Ficha del empleado", ["Campo", "Valor"], []))
    return generar_pdf("Reporte de Información Personal", filtros, usuario, secciones)


def pdf_salud_pension(bloques, filtros, usuario):
    secciones = [
        seccion_tabla(bloque["titulo"], bloque["columnas"], bloque["filas"], bloque.get("resumen"), bloque.get("aviso"))
        for bloque in bloques
    ]
    return generar_pdf("Reporte de Salud y Pensión", filtros, usuario, secciones)


def pdf_novedades(detalle, conteos, filtros, usuario, aviso=None):
    secciones = [
        seccion_tabla(
            "Conteo de novedades por dependencia y cargo",
            ["Dependencia", "Cargo", "Cantidad de novedades"],
            conteos,
            [f"Total de novedades: {sum(int(fila[2]) for fila in conteos)}"],
        ),
        seccion_tabla(
            "Detalle de novedades",
            ["Código", "Empleado", "Dependencia", "Cargo", "Período", "Tipo", "Detalle", "Días"],
            detalle,
            aviso=aviso,
        ),
    ]
    return generar_pdf("Reporte de Novedades", filtros, usuario, secciones)


def pdf_entretenimiento(subtitulo, bloques, filtros, usuario):
    secciones = [
        seccion_tabla(bloque["titulo"], bloque["columnas"], bloque["filas"], bloque.get("resumen"), bloque.get("aviso"))
        for bloque in bloques
    ]
    return generar_pdf(f"Reporte de Base-Entretenimiento - {subtitulo}", filtros, usuario, secciones)
