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
