def _cursor(connection):
    return connection.cursor(dictionary=True)

def all_rows(connection, sql, params=()):
    cursor = _cursor(connection)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()

def one_row(connection, sql, params=()):
    cursor = _cursor(connection)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone()
    finally:
        cursor.close()

def change(connection, sql, params=()):
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        connection.commit()
        return cursor.lastrowid, cursor.rowcount
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()

def employees(connection, order="ASC", dependency_id=None, job_id=None):
    order = "DESC" if str(order).upper() == "DESC" else "ASC"
    sql = """
    SELECT e.id_empleado, e.codigo_personal, e.salario, e.fecha_ingreso,
           p.nombres, p.apellidos, d.nombre_dependencia, c.nombre_cargo
    FROM empleados e
    JOIN personas p ON p.id_persona=e.id_persona
    LEFT JOIN dependencias d ON d.id_dependencia=e.id_dependencia
    LEFT JOIN cargos c ON c.id_cargo=e.id_cargo
    WHERE (%s IS NULL OR e.id_dependencia=%s)
      AND (%s IS NULL OR e.id_cargo=%s)
    ORDER BY p.apellidos """ + order + """, p.nombres """ + order
    return all_rows(connection, sql, (dependency_id, dependency_id, job_id, job_id))

def employee_count(connection, dependency_id=None, job_id=None):
    row = one_row(connection, """
    SELECT COUNT(*) AS total FROM empleados
    WHERE (%s IS NULL OR id_dependencia=%s)
      AND (%s IS NULL OR id_cargo=%s)
    """, (dependency_id, dependency_id, job_id, job_id))
    return row["total"]

def employee(connection, employee_id):
    return one_row(connection, "SELECT * FROM empleados WHERE id_empleado=%s", (employee_id,))

def insert_employee(connection, d):
    return change(connection, """
    INSERT INTO empleados
    (codigo_personal,id_persona,id_dependencia,id_cargo,salario,fecha_ingreso)
    VALUES (%s,%s,%s,%s,%s,%s)
    """, (d["codigo_personal"],d["id_persona"],d["id_dependencia"],d["id_cargo"],d["salario"],d["fecha_ingreso"]))

def update_employee(connection, employee_id, d):
    return change(connection, """
    UPDATE empleados SET codigo_personal=%s,id_persona=%s,id_dependencia=%s,
    id_cargo=%s,salario=%s,fecha_ingreso=%s WHERE id_empleado=%s
    """, (d["codigo_personal"],d["id_persona"],d["id_dependencia"],d["id_cargo"],d["salario"],d["fecha_ingreso"],employee_id))

def delete_employee(connection, employee_id):
    return change(connection, "DELETE FROM empleados WHERE id_empleado=%s", (employee_id,))

def novelties(connection, novelty_id=None, employee_id=None):
    return all_rows(connection, """
    SELECT n.*, t.nombre_tipo_novedad FROM novedades n
    LEFT JOIN tipos_novedad t ON t.id_tipo_novedad=n.id_tipo_novedad
    WHERE (%s IS NULL OR n.id_novedad=%s)
      AND (%s IS NULL OR n.id_empleado=%s)
    ORDER BY n.fecha_inicio DESC
    """, (novelty_id, novelty_id, employee_id, employee_id))

def novelty(connection, novelty_id):
    return one_row(connection, "SELECT * FROM novedades WHERE id_novedad=%s", (novelty_id,))

def insert_novelty(connection, d):
    return change(connection, """
    INSERT INTO novedades
    (id_empleado,id_tipo_novedad,fecha_inicio,fecha_fin,valor,descripcion)
    VALUES (%s,%s,%s,%s,%s,%s)
    """, (d["id_empleado"],d["id_tipo_novedad"],d["fecha_inicio"],d.get("fecha_fin"),d.get("valor",0),d.get("descripcion")))

def update_novelty(connection, novelty_id, d):
    return change(connection, """
    UPDATE novedades SET id_empleado=%s,id_tipo_novedad=%s,fecha_inicio=%s,
    fecha_fin=%s,valor=%s,descripcion=%s WHERE id_novedad=%s
    """, (d["id_empleado"],d["id_tipo_novedad"],d["fecha_inicio"],d.get("fecha_fin"),d.get("valor",0),d.get("descripcion"),novelty_id))

def delete_novelty(connection, novelty_id):
    return change(connection, "DELETE FROM novedades WHERE id_novedad=%s", (novelty_id,))

def employees_by_dependency(connection):
    return all_rows(connection, """
    SELECT d.nombre_dependencia,COUNT(e.id_empleado) AS total
    FROM dependencias d LEFT JOIN empleados e ON e.id_dependencia=d.id_dependencia
    GROUP BY d.id_dependencia,d.nombre_dependencia ORDER BY d.nombre_dependencia ASC
    """)

def employees_by_dependency_job(connection):
    return all_rows(connection, """
    SELECT d.nombre_dependencia,c.nombre_cargo,COUNT(e.id_empleado) AS total
    FROM empleados e LEFT JOIN dependencias d ON d.id_dependencia=e.id_dependencia
    LEFT JOIN cargos c ON c.id_cargo=e.id_cargo
    GROUP BY d.nombre_dependencia,c.nombre_cargo
    ORDER BY d.nombre_dependencia ASC,c.nombre_cargo ASC
    """)

def employee_profile(connection, employee_id):
    row = one_row(connection, """
    SELECT e.codigo_personal,CONCAT_WS(' ',p.nombres,p.apellidos) AS nombre_completo,
    d.nombre_dependencia,c.nombre_cargo,DATE_FORMAT(e.fecha_ingreso,'%d/%m/%Y') AS fecha_ingreso,
    eps.nombre_eps,fp.nombre_fondo_pension,e.salario,
    COALESCE((SELECT dn.valor_aporte_pension FROM detalle_nomina dn
    WHERE dn.id_empleado=e.id_empleado ORDER BY dn.periodo_fecha DESC LIMIT 1),0) AS aporte_pension
    FROM empleados e JOIN personas p ON p.id_persona=e.id_persona
    LEFT JOIN dependencias d ON d.id_dependencia=e.id_dependencia
    LEFT JOIN cargos c ON c.id_cargo=e.id_cargo
    LEFT JOIN afiliaciones_empleado ae ON ae.id_empleado=e.id_empleado
    LEFT JOIN eps ON eps.id_eps=ae.id_eps
    LEFT JOIN fondos_pension fp ON fp.id_fondo_pension=ae.id_fondo_pension
    WHERE e.id_empleado=%s
    """, (employee_id,))
    if row:
        row["novedades"] = novelties(connection, employee_id=employee_id)
    return row

def health_frequency(connection, pension=False):
    table, key, label = ("fondos_pension","id_fondo_pension","nombre_fondo_pension") if pension else ("eps","id_eps","nombre_eps")
    sql = f"""
    SELECT x.{label} AS entidad,COUNT(e.id_empleado) AS total
    FROM afiliaciones_empleado a JOIN empleados e ON e.id_empleado=a.id_empleado
    JOIN {table} x ON x.{key}=a.{key}
    GROUP BY x.{key},x.{label} ORDER BY x.{label} ASC
    """
    return all_rows(connection, sql)

def health_by_dependency(connection, pension=False):
    table, key, label = ("fondos_pension","id_fondo_pension","nombre_fondo_pension") if pension else ("eps","id_eps","nombre_eps")
    sql = f"""
    SELECT d.nombre_dependencia,x.{label} AS entidad,COUNT(e.id_empleado) AS total
    FROM empleados e JOIN dependencias d ON d.id_dependencia=e.id_dependencia
    JOIN afiliaciones_empleado a ON a.id_empleado=e.id_empleado
    JOIN {table} x ON x.{key}=a.{key}
    GROUP BY d.nombre_dependencia,x.{label}
    ORDER BY d.nombre_dependencia ASC,x.{label} ASC
    """
    return all_rows(connection, sql)

def employees_by_job_health(connection, pension=False, order="ASC"):
    order = "DESC" if str(order).upper()=="DESC" else "ASC"
    table, key, label = ("fondos_pension","id_fondo_pension","nombre_fondo_pension") if pension else ("eps","id_eps","nombre_eps")
    sql = f"""
    SELECT c.nombre_cargo,x.{label} AS entidad,CONCAT_WS(' ',p.nombres,p.apellidos) AS nombre,
    e.codigo_personal
    FROM empleados e JOIN personas p ON p.id_persona=e.id_persona
    LEFT JOIN cargos c ON c.id_cargo=e.id_cargo
    JOIN afiliaciones_empleado a ON a.id_empleado=e.id_empleado
    JOIN {table} x ON x.{key}=a.{key}
    ORDER BY c.nombre_cargo ASC,x.{label} ASC,nombre {order}
    """
    return all_rows(connection, sql)

def novelty_report(connection, f1, f2):
    return all_rows(connection, """
    SELECT e.codigo_personal,CONCAT_WS(' ',p.nombres,p.apellidos) AS nombre,
    d.nombre_dependencia,c.nombre_cargo,n.id_novedad,t.nombre_tipo_novedad,
    n.fecha_inicio,n.fecha_fin,n.valor,n.descripcion
    FROM novedades n JOIN empleados e ON e.id_empleado=n.id_empleado
    JOIN personas p ON p.id_persona=e.id_persona
    LEFT JOIN dependencias d ON d.id_dependencia=e.id_dependencia
    LEFT JOIN cargos c ON c.id_cargo=e.id_cargo
    LEFT JOIN tipos_novedad t ON t.id_tipo_novedad=n.id_tipo_novedad
    WHERE n.fecha_inicio>=STR_TO_DATE(CONCAT('01/',%s),'%d/%m/%Y')
    AND n.fecha_inicio<DATE_ADD(STR_TO_DATE(CONCAT('01/',%s),'%d/%m/%Y'),INTERVAL 1 MONTH)
    ORDER BY d.nombre_dependencia ASC,c.nombre_cargo ASC,nombre ASC
    """, (f1,f2))

def novelty_report_counts(connection, f1, f2):
    return all_rows(connection, """
    SELECT d.nombre_dependencia,c.nombre_cargo,COUNT(n.id_novedad) AS total
    FROM novedades n JOIN empleados e ON e.id_empleado=n.id_empleado
    LEFT JOIN dependencias d ON d.id_dependencia=e.id_dependencia
    LEFT JOIN cargos c ON c.id_cargo=e.id_cargo
    WHERE n.fecha_inicio>=STR_TO_DATE(CONCAT('01/',%s),'%d/%m/%Y')
    AND n.fecha_inicio<DATE_ADD(STR_TO_DATE(CONCAT('01/',%s),'%d/%m/%Y'),INTERVAL 1 MONTH)
    GROUP BY d.nombre_dependencia,c.nombre_cargo
    ORDER BY d.nombre_dependencia ASC,c.nombre_cargo ASC
    """, (f1,f2))
from backend.database.connection import get_connection as _issue8_get_connection

ISSUE8_TABLES = {
    "peliculas": {
        "pk": "id_pelicula",
        "columns": ["titulo", "fecha_lanzamiento", "duracion_minutos", "sinopsis", "idioma_id"],
        "search": ["titulo", "sinopsis"],
        "order": ["id_pelicula", "titulo", "fecha_lanzamiento", "duracion_minutos"]
    },
    "libros": {
        "pk": "id_libro",
        "columns": ["titulo", "anio_publicacion", "rating", "editorial_id", "idioma_id", "isbn"],
        "search": ["titulo", "isbn"],
        "order": ["id_libro", "titulo", "anio_publicacion", "rating"]
    }
}


def _issue8_select(sql, params=None):
    connection = _issue8_get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params or ())
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def _issue8_select_one(sql, params=None):
    connection = _issue8_get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params or ())
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def _issue8_write(sql, params=None):
    connection = _issue8_get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params or ())
        connection.commit()
        return {"lastrowid": cursor.lastrowid, "rowcount": cursor.rowcount}
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def _issue8_many(sql, values):
    connection = _issue8_get_connection()
    cursor = connection.cursor()
    try:
        cursor.executemany(sql, values)
        connection.commit()
        return cursor.rowcount
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def _issue8_build_filters(entity, params):
    config = ISSUE8_TABLES[entity]
    alias = "p" if entity == "peliculas" else "l"
    conditions = []
    values = []

    for field in config["columns"]:
        value = params.get(field)
        if value not in (None, ""):
            conditions.append(f"{alias}.`{field}` = %s")
            values.append(value)

    search_value = params.get("buscar")
    if search_value:
        search_conditions = [f"{alias}.`{field}` LIKE %s" for field in config["search"]]
        conditions.append("(" + " OR ".join(search_conditions) + ")")
        values.extend([f"%{search_value}%"] * len(search_conditions))

    if entity == "peliculas":
        genero_id = params.get("genero_id")
        if genero_id not in (None, ""):
            conditions.append("EXISTS (SELECT 1 FROM pelicula_generos pg WHERE pg.id_pelicula = p.id_pelicula AND pg.id_genero = %s)")
            values.append(genero_id)
        if params.get("f1"):
            conditions.append("p.fecha_lanzamiento >= %s")
            values.append(params["f1"])
        if params.get("f2"):
            conditions.append("p.fecha_lanzamiento <= %s")
            values.append(params["f2"])

    if entity == "libros":
        for parameter, operator, column in (
            ("anio_desde", ">=", "anio_publicacion"),
            ("anio_hasta", "<=", "anio_publicacion"),
            ("rating_min", ">=", "rating"),
            ("rating_max", "<=", "rating")
        ):
            value = params.get(parameter)
            if value not in (None, ""):
                conditions.append(f"l.{column} {operator} %s")
                values.append(value)

    where_sql = " WHERE " + " AND ".join(conditions) if conditions else ""
    return where_sql, values


def issue8_list_records(entity, params):
    if entity not in ISSUE8_TABLES:
        raise ValueError("Entidad no permitida")
    config = ISSUE8_TABLES[entity]
    alias = "p" if entity == "peliculas" else "l"
    where_sql, values = _issue8_build_filters(entity, params)
    order_by = params.get("ordenar_por", config["pk"])
    if order_by not in config["order"]:
        order_by = config["pk"]
    direction = str(params.get("orden", "ASC")).upper()
    if direction not in {"ASC", "DESC"}:
        raise ValueError("orden debe ser ASC o DESC")
    try:
        limit = max(1, min(int(params.get("limite", 50)), 200))
        offset = max(0, int(params.get("desde", 0)))
    except (TypeError, ValueError):
        raise ValueError("limite y desde deben ser números enteros")
    sql = f"SELECT {alias}.* FROM `{entity}` {alias}{where_sql} ORDER BY {alias}.`{order_by}` {direction} LIMIT %s OFFSET %s"
    return _issue8_select(sql, tuple(values + [limit, offset]))


def issue8_get_record(entity, record_id):
    if entity not in ISSUE8_TABLES:
        raise ValueError("Entidad no permitida")
    pk = ISSUE8_TABLES[entity]["pk"]
    return _issue8_select_one(f"SELECT * FROM `{entity}` WHERE `{pk}` = %s", (record_id,))


def issue8_create_record(entity, payload):
    if entity not in ISSUE8_TABLES:
        raise ValueError("Entidad no permitida")
    allowed = ISSUE8_TABLES[entity]["columns"]
    data = {key: value for key, value in payload.items() if key in allowed}
    if not data or not data.get("titulo"):
        raise ValueError("El campo titulo es obligatorio")
    columns = list(data)
    column_sql = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    return _issue8_write(f"INSERT INTO `{entity}` ({column_sql}) VALUES ({placeholders})", tuple(data[column] for column in columns))


def issue8_update_record(entity, record_id, payload):
    if entity not in ISSUE8_TABLES:
        raise ValueError("Entidad no permitida")
    config = ISSUE8_TABLES[entity]
    data = {key: value for key, value in payload.items() if key in config["columns"]}
    if not data:
        raise ValueError("No se enviaron campos válidos para actualizar")
    assignments = ", ".join(f"`{column}` = %s" for column in data)
    return _issue8_write(
        f"UPDATE `{entity}` SET {assignments} WHERE `{config['pk']}` = %s",
        tuple(data.values()) + (record_id,)
    )


def issue8_delete_record(entity, record_id):
    if entity not in ISSUE8_TABLES:
        raise ValueError("Entidad no permitida")
    pk = ISSUE8_TABLES[entity]["pk"]
    return _issue8_write(f"DELETE FROM `{entity}` WHERE `{pk}` = %s", (record_id,))


def issue8_peliculas_por_genero_y_fecha(f1, f2, orden):
    direction = str(orden).upper()
    if direction not in {"ASC", "DESC"}:
        raise ValueError("orden debe ser ASC o DESC")
    sql = f"""
        SELECT p.id_pelicula, p.titulo, p.fecha_lanzamiento, g.id_genero, g.nombre AS genero
        FROM peliculas p
        INNER JOIN pelicula_generos pg ON pg.id_pelicula = p.id_pelicula
        INNER JOIN generos g ON g.id_genero = pg.id_genero
        WHERE p.fecha_lanzamiento BETWEEN %s AND %s
        ORDER BY p.fecha_lanzamiento {direction}, p.titulo {direction}
    """
    return _issue8_select(sql, (f1, f2))


def issue8_peliculas_con_exactamente_n_generos(n, orden):
    direction = str(orden).upper()
    if direction not in {"ASC", "DESC"}:
        raise ValueError("orden debe ser ASC o DESC")
    sql = f"""
        SELECT p.id_pelicula, p.titulo, COUNT(pg.id_genero) AS total_generos
        FROM peliculas p
        LEFT JOIN pelicula_generos pg ON pg.id_pelicula = p.id_pelicula
        GROUP BY p.id_pelicula, p.titulo
        HAVING COUNT(pg.id_genero) = %s
        ORDER BY p.titulo {direction}
    """
    return _issue8_select(sql, (n,))


def issue8_top_libros(n, orden):
    direction = str(orden).upper()
    if direction not in {"ASC", "DESC"}:
        raise ValueError("orden debe ser ASC o DESC")
    return _issue8_select(f"SELECT * FROM libros ORDER BY rating {direction}, titulo ASC LIMIT %s", (n,))


def issue8_top_y_peores_libros_por_anio(orden):
    direction = str(orden).upper()
    if direction not in {"ASC", "DESC"}:
        raise ValueError("orden debe ser ASC o DESC")
    sql = f"""
        WITH clasificacion AS (
            SELECT l.*,
                   ROW_NUMBER() OVER (PARTITION BY anio_publicacion ORDER BY rating DESC, id_libro ASC) AS posicion_mejor,
                   ROW_NUMBER() OVER (PARTITION BY anio_publicacion ORDER BY rating ASC, id_libro ASC) AS posicion_peor
            FROM libros l
            WHERE rating IS NOT NULL AND anio_publicacion IS NOT NULL
        )
        SELECT * FROM clasificacion
        WHERE posicion_mejor <= 5 OR posicion_peor <= 5
        ORDER BY anio_publicacion {direction}, rating DESC
    """
    return _issue8_select(sql)


def issue8_frecuencia_peliculas_por_genero(f1, f2):
    sql = """
        SELECT g.id_genero, g.nombre AS genero, COUNT(DISTINCT p.id_pelicula) AS frecuencia
        FROM generos g
        LEFT JOIN pelicula_generos pg ON pg.id_genero = g.id_genero
        LEFT JOIN peliculas p ON p.id_pelicula = pg.id_pelicula AND p.fecha_lanzamiento BETWEEN %s AND %s
        GROUP BY g.id_genero, g.nombre
        ORDER BY frecuencia DESC, genero ASC
    """
    return _issue8_select(sql, (f1, f2))


def issue8_frecuencia_libros_por_anio(f1, f2):
    sql = """
        SELECT anio_publicacion, COUNT(*) AS frecuencia
        FROM libros
        WHERE anio_publicacion BETWEEN %s AND %s
        GROUP BY anio_publicacion
        ORDER BY anio_publicacion ASC
    """
    return _issue8_select(sql, (f1, f2))


def issue8_list_audit_table(table, limit, offset):
    if table not in {"auditoria", "archivos"}:
        raise ValueError("Tabla de auditoría no permitida")
    return _issue8_select(f"SELECT * FROM `{table}` LIMIT %s OFFSET %s", (limit, offset))


def issue8_insert_metadata_record(table, values):
    allowed_tables = {"auditoria", "archivos", "errores_carga"}
    if table not in allowed_tables:
        raise ValueError("Tabla de metadatos no permitida")
    columns = _issue8_select(
        "SELECT COLUMN_NAME AS column_name FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        (table,)
    )
    available = {row["column_name"] for row in columns}
    data = {key: value for key, value in values.items() if key in available}
    if not data:
        return None
    column_names = list(data)
    column_sql = ", ".join(f"`{column}`" for column in column_names)
    placeholders = ", ".join(["%s"] * len(column_names))
    return _issue8_write(
        f"INSERT INTO `{table}` ({column_sql}) VALUES ({placeholders})",
        tuple(data[column] for column in column_names)
    )


def issue8_insert_incremental(entity, rows):
    if entity not in ISSUE8_TABLES:
        raise ValueError("Entidad no permitida")
    allowed = ISSUE8_TABLES[entity]["columns"]
    normalized = []
    fields = [field for field in allowed if any(row.get(field) is not None for row in rows)]
    if not fields:
        return 0
    for row in rows:
        data = {field: row.get(field) for field in fields}
        if not data.get("titulo"):
            continue
        normalized.append(tuple(data[field] for field in fields))
    if not normalized:
        return 0
    column_sql = ", ".join(f"`{column}`" for column in fields)
    placeholders = ", ".join(["%s"] * len(fields))
    return _issue8_many(f"INSERT IGNORE INTO `{entity}` ({column_sql}) VALUES ({placeholders})", normalized)
