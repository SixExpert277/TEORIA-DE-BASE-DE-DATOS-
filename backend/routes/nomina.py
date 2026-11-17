from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from backend.database.connection import get_connection
from backend.database import queries
from backend.routes.auth import get_current_user
from backend.services.audit_logger import log_action

router = APIRouter(prefix="/api/nomina", tags=["Nómina y novedades"])

class EmpleadoInput(BaseModel):
    codigo_personal: str = Field(min_length=1, max_length=40)
    id_persona: int
    id_dependencia: int
    id_cargo: int
    salario: float = Field(ge=0)
    fecha_ingreso: date

class NovedadInput(BaseModel):
    id_empleado: int
    id_tipo_novedad: int
    fecha_inicio: date
    fecha_fin: date | None = None
    valor: float = 0
    descripcion: str | None = None

def db_connection():
    connection = get_connection()
    try:
        yield connection
    finally:
        connection.close()

def register_audit(user, action, entity, record_id, details=None):
    log_action(usuario=user, accion=action, entidad=entity, entidad_id=record_id, detalles=details or {})

@router.get("/empleados")
def list_employees(orden: str = Query("ASC", pattern="^(ASC|DESC)$"), dependencia_id: int | None = None, cargo_id: int | None = None, db=Depends(db_connection), user=Depends(get_current_user)):
    rows = queries.employees(db, orden, dependencia_id, cargo_id)
    return {"total": queries.employee_count(db, dependencia_id, cargo_id), "empleados": rows}

@router.get("/empleados/{employee_id}")
def get_employee(employee_id: int, db=Depends(db_connection), user=Depends(get_current_user)):
    row = queries.employee(db, employee_id)
    if not row:
        raise HTTPException(404, "Empleado no encontrado")
    return row

@router.post("/empleados", status_code=201)
def create_employee(data: EmpleadoInput, db=Depends(db_connection), user=Depends(get_current_user)):
    try:
        record_id, _ = queries.insert_employee(db, data.model_dump())
        register_audit(user, "CREATE", "empleados", record_id, data.model_dump(mode="json"))
        return {"mensaje": "Empleado creado", "id_empleado": record_id}
    except Exception as exc:
        raise HTTPException(400, "No fue posible crear el empleado") from exc

@router.put("/empleados/{employee_id}")
def edit_employee(employee_id: int, data: EmpleadoInput, db=Depends(db_connection), user=Depends(get_current_user)):
    if not queries.employee(db, employee_id):
        raise HTTPException(404, "Empleado no encontrado")
    try:
        _, affected = queries.update_employee(db, employee_id, data.model_dump())
        register_audit(user, "UPDATE", "empleados", employee_id, data.model_dump(mode="json"))
        return {"mensaje": "Empleado actualizado", "filas_afectadas": affected}
    except Exception as exc:
        raise HTTPException(400, "No fue posible actualizar el empleado") from exc

@router.delete("/empleados/{employee_id}")
def remove_employee(employee_id: int, db=Depends(db_connection), user=Depends(get_current_user)):
    if not queries.employee(db, employee_id):
        raise HTTPException(404, "Empleado no encontrado")
    try:
        _, affected = queries.delete_employee(db, employee_id)
        register_audit(user, "DELETE", "empleados", employee_id)
        return {"mensaje": "Empleado eliminado", "filas_afectadas": affected}
    except Exception as exc:
        raise HTTPException(409, "No fue posible eliminarlo; puede tener registros relacionados") from exc

@router.get("/novedades")
def list_novelties(empleado_id: int | None = None, db=Depends(db_connection), user=Depends(get_current_user)):
    rows = queries.novelties(db, employee_id=empleado_id)
    return {"total": len(rows), "novedades": rows}

@router.get("/novedades/{novelty_id}")
def get_novelty(novelty_id: int, db=Depends(db_connection), user=Depends(get_current_user)):
    row = queries.novelty(db, novelty_id)
    if not row:
        raise HTTPException(404, "Novedad no encontrada")
    return row

@router.post("/novedades", status_code=201)
def create_novelty(data: NovedadInput, db=Depends(db_connection), user=Depends(get_current_user)):
    if not queries.employee(db, data.id_empleado):
        raise HTTPException(404, "Empleado no encontrado")
    try:
        record_id, _ = queries.insert_novelty(db, data.model_dump())
        register_audit(user, "CREATE", "novedades", record_id, data.model_dump(mode="json"))
        return {"mensaje": "Novedad creada", "id_novedad": record_id}
    except Exception as exc:
        raise HTTPException(400, "No fue posible crear la novedad") from exc

@router.put("/novedades/{novelty_id}")
def edit_novelty(novelty_id: int, data: NovedadInput, db=Depends(db_connection), user=Depends(get_current_user)):
    if not queries.novelty(db, novelty_id):
        raise HTTPException(404, "Novedad no encontrada")
    try:
        _, affected = queries.update_novelty(db, novelty_id, data.model_dump())
        register_audit(user, "UPDATE", "novedades", novelty_id, data.model_dump(mode="json"))
        return {"mensaje": "Novedad actualizada", "filas_afectadas": affected}
    except Exception as exc:
        raise HTTPException(400, "No fue posible actualizar la novedad") from exc

@router.delete("/novedades/{novelty_id}")
def remove_novelty(novelty_id: int, db=Depends(db_connection), user=Depends(get_current_user)):
    if not queries.novelty(db, novelty_id):
        raise HTTPException(404, "Novedad no encontrada")
    try:
        _, affected = queries.delete_novelty(db, novelty_id)
        register_audit(user, "DELETE", "novedades", novelty_id)
        return {"mensaje": "Novedad eliminada", "filas_afectadas": affected}
    except Exception as exc:
        raise HTTPException(409, "No fue posible eliminar la novedad") from exc

@router.get("/reporte/empleados")
def report_employees(orden: str = Query("ASC", pattern="^(ASC|DESC)$"), dependencia_id: int | None = None, cargo_id: int | None = None, db=Depends(db_connection), user=Depends(get_current_user)):
    rows = queries.employees(db, orden, dependencia_id, cargo_id)
    return {"total": queries.employee_count(db, dependencia_id, cargo_id), "empleados": rows}

@router.get("/reporte/dependencias")
def report_dependencies(db=Depends(db_connection), user=Depends(get_current_user)):
    rows = queries.employees_by_dependency(db)
    return {"total_empleados": sum(x["total"] for x in rows), "grafico_torta": rows}

@router.get("/reporte/dependencias-cargos")
def report_dependency_jobs(db=Depends(db_connection), user=Depends(get_current_user)):
    rows = queries.employees_by_dependency_job(db)
    return {"total_grupos": len(rows), "grafico_barras": rows}

@router.get("/reporte/empleado/{employee_id}")
def report_employee_profile(employee_id: int, db=Depends(db_connection), user=Depends(get_current_user)):
    row = queries.employee_profile(db, employee_id)
    if not row:
        raise HTTPException(404, "Empleado no encontrado")
    return row

@router.get("/reporte/salud-pension")
def report_health_pension(db=Depends(db_connection), user=Depends(get_current_user)):
    return {
        "frecuencias_eps": queries.health_frequency(db),
        "frecuencias_pension": queries.health_frequency(db, True),
        "eps_por_dependencia": queries.health_by_dependency(db),
        "pension_por_dependencia": queries.health_by_dependency(db, True)
    }

@router.get("/reporte/cargo-eps")
def report_job_eps(orden: str = Query("ASC", pattern="^(ASC|DESC)$"), db=Depends(db_connection), user=Depends(get_current_user)):
    rows = queries.employees_by_job_health(db, False, orden)
    return {"total": len(rows), "empleados": rows}

@router.get("/reporte/cargo-pension")
def report_job_pension(orden: str = Query("ASC", pattern="^(ASC|DESC)$"), db=Depends(db_connection), user=Depends(get_current_user)):
    rows = queries.employees_by_job_health(db, True, orden)
    return {"total": len(rows), "empleados": rows}

@router.get("/reporte/novedades")
def report_novelties(f1: str = Query(..., pattern=r"^(0[1-9]|1[0-2])/[0-9]{4}$"), f2: str = Query(..., pattern=r"^(0[1-9]|1[0-2])/[0-9]{4}$"), db=Depends(db_connection), user=Depends(get_current_user)):
    a = tuple(map(int, f1.split("/")[::-1]))
    b = tuple(map(int, f2.split("/")[::-1]))
    if a > b:
        raise HTTPException(400, "f1 no puede ser posterior a f2")
    return {
        "empleados_con_novedades": queries.novelty_report(db, f1, f2),
        "conteo_dependencia_cargo": queries.novelty_report_counts(db, f1, f2)
    }
