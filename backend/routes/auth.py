import base64
import io
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from flask import Blueprint, g, jsonify, request
from PIL import Image, ImageDraw, ImageFont
from mysql.connector import Error

from config import (
    CAPTCHA_EXPIRATION_SECONDS,
    JWT_ALGORITHM,
    JWT_EXPIRATION_HOURS,
    JWT_SECRET_KEY,
)
from database.connection import DatabaseConnectionError, get_db_connection
from services.audit_logger import log_audit

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

ROLES_VALIDOS = ("admin", "auditor", "usuario")
ROL_POR_DEFECTO = "usuario"
LONGITUD_CAPTCHA = 5
ALFABETO_CAPTCHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LONGITUD_MINIMA_CLAVE = 8

_captchas = {}
_captchas_lock = threading.Lock()


def _error(mensaje, codigo):
    return jsonify({"error": mensaje}), codigo


def _purgar_captchas_vencidos():
    ahora = time.time()
    vencidos = [clave for clave, datos in _captchas.items() if datos["expira"] <= ahora]
    for clave in vencidos:
        del _captchas[clave]


def _generar_imagen_captcha(texto):
    ancho, alto = 180, 64
    imagen = Image.new("RGB", (ancho, alto), (245, 245, 245))
    lienzo = ImageDraw.Draw(imagen)
    try:
        fuente = ImageFont.load_default(size=34)
    except TypeError:
        fuente = ImageFont.load_default()
    for _ in range(6):
        inicio = (secrets.randbelow(ancho), secrets.randbelow(alto))
        fin = (secrets.randbelow(ancho), secrets.randbelow(alto))
        lienzo.line([inicio, fin], fill=(150, 150, 150), width=2)
    for indice, caracter in enumerate(texto):
        posicion = (14 + indice * 30, 10 + secrets.randbelow(14))
        lienzo.text(posicion, caracter, fill=(30, 30, 120), font=fuente)
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _crear_captcha():
    texto = "".join(secrets.choice(ALFABETO_CAPTCHA) for _ in range(LONGITUD_CAPTCHA))
    captcha_id = secrets.token_urlsafe(16)
    with _captchas_lock:
        _purgar_captchas_vencidos()
        _captchas[captcha_id] = {
            "respuesta": texto,
            "expira": time.time() + CAPTCHA_EXPIRATION_SECONDS,
        }
    return captcha_id, texto


def _consumir_captcha(captcha_id, respuesta):
    with _captchas_lock:
        _purgar_captchas_vencidos()
        datos = _captchas.pop(captcha_id, None)
    if datos is None:
        return False
    return secrets.compare_digest(
        datos["respuesta"].upper(), str(respuesta).strip().upper()
    )


def _generar_token(usuario):
    ahora = datetime.now(timezone.utc)
    carga = {
        "sub": str(usuario["id_usuario"]),
        "id_usuario": usuario["id_usuario"],
        "username": usuario["username"],
        "rol": usuario["rol"],
        "iat": ahora,
        "exp": ahora + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(carga, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def token_required(funcion):
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        cabecera = request.headers.get("Authorization", "")
        partes = cabecera.split()
        if len(partes) != 2 or partes[0].lower() != "bearer":
            return _error("Token de autenticación ausente o con formato inválido", 401)
        try:
            carga = jwt.decode(partes[1], JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            return _error("El token ha expirado", 401)
        except jwt.InvalidTokenError:
            return _error("Token inválido", 401)
        g.current_user = {
            "id_usuario": carga["id_usuario"],
            "username": carga["username"],
            "rol": carga["rol"],
        }
        return funcion(*args, **kwargs)

    return envoltura


def _buscar_usuario(cursor, username):
    cursor.execute(
        "SELECT id_usuario, username, contrasena, rol FROM usuarios WHERE username = %s",
        (username,),
    )
    return cursor.fetchone()


def _resolver_id_persona(cursor, id_persona, codigo_personal):
    if id_persona is not None:
        cursor.execute("SELECT id_persona FROM personas WHERE id_persona = %s", (id_persona,))
        fila = cursor.fetchone()
        return fila["id_persona"] if fila else False
    if codigo_personal:
        cursor.execute(
            "SELECT id_persona FROM empleados WHERE codigo_personal = %s",
            (codigo_personal,),
        )
        fila = cursor.fetchone()
        return fila["id_persona"] if fila else False
    return None


@auth_bp.route("/register", methods=["POST"])
def register():
    datos = request.get_json(silent=True) or {}
    username = str(datos.get("username", "")).strip()
    password = str(datos.get("password", ""))
    rol = str(datos.get("rol", ROL_POR_DEFECTO)).strip().lower()
    id_persona = datos.get("id_persona")
    codigo_personal = datos.get("codigo_personal")

    if not username or not password:
        return _error("username y password son obligatorios", 400)
    if len(password) < LONGITUD_MINIMA_CLAVE:
        return _error(f"La contraseña debe tener al menos {LONGITUD_MINIMA_CLAVE} caracteres", 400)
    if rol not in ROLES_VALIDOS:
        return _error(f"rol inválido. Valores permitidos: {', '.join(ROLES_VALIDOS)}", 400)

    conexion = None
    try:
        conexion = get_db_connection()
        cursor = conexion.cursor(dictionary=True)
        if _buscar_usuario(cursor, username):
            cursor.close()
            log_audit("REGISTRO", f"Registro rechazado: el usuario '{username}' ya existe", "FALLIDO")
            return _error("El usuario ya existe", 409)
        persona_resuelta = _resolver_id_persona(cursor, id_persona, codigo_personal)
        if persona_resuelta is False:
            cursor.close()
            log_audit("REGISTRO", f"Registro rechazado: persona no encontrada para '{username}'", "FALLIDO")
            return _error("La persona o el código personal indicado no existe", 404)
        hash_clave = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute(
            "INSERT INTO usuarios (id_persona, username, contrasena, rol) VALUES (%s, %s, %s, %s)",
            (persona_resuelta, username, hash_clave, rol),
        )
        nuevo_id = cursor.lastrowid
        conexion.commit()
        cursor.close()
    except DatabaseConnectionError:
        return _error("Servicio de base de datos no disponible", 503)
    except Error:
        if conexion is not None:
            conexion.rollback()
        log_audit("REGISTRO", f"Error de base de datos registrando '{username}'", "FALLIDO")
        return _error("No se pudo registrar el usuario", 500)
    finally:
        if conexion is not None:
            conexion.close()

    log_audit(
        "REGISTRO",
        f"Usuario '{username}' registrado con rol '{rol}'",
        "EXITOSO",
        id_usuario=nuevo_id,
        datos_nuevos={"id_usuario": nuevo_id, "username": username, "rol": rol, "id_persona": persona_resuelta},
    )
    return jsonify({"id_usuario": nuevo_id, "username": username, "rol": rol}), 201


@auth_bp.route("/captcha", methods=["GET"])
def captcha():
    captcha_id, texto = _crear_captcha()
    return jsonify(
        {
            "captcha_id": captcha_id,
            "imagen_base64": _generar_imagen_captcha(texto),
            "tipo_contenido": "image/png",
            "expira_en_segundos": CAPTCHA_EXPIRATION_SECONDS,
        }
    )


@auth_bp.route("/login", methods=["POST"])
def login():
    datos = request.get_json(silent=True) or {}
    username = str(datos.get("username", "")).strip()
    password = str(datos.get("password", ""))
    captcha_id = str(datos.get("captcha_id", "")).strip()
    captcha_respuesta = str(datos.get("captcha_respuesta", "")).strip()

    if not username or not password or not captcha_id or not captcha_respuesta:
        return _error("username, password, captcha_id y captcha_respuesta son obligatorios", 400)

    if not _consumir_captcha(captcha_id, captcha_respuesta):
        log_audit("LOGIN", f"Intento de login con CAPTCHA inválido o expirado para '{username}'", "FALLIDO")
        return _error("CAPTCHA inválido o expirado", 400)

    conexion = None
    try:
        conexion = get_db_connection()
        cursor = conexion.cursor(dictionary=True)
        usuario = _buscar_usuario(cursor, username)
        cursor.close()
    except DatabaseConnectionError:
        return _error("Servicio de base de datos no disponible", 503)
    except Error:
        log_audit("LOGIN", f"Error de base de datos en login de '{username}'", "FALLIDO")
        return _error("No se pudo procesar el inicio de sesión", 500)
    finally:
        if conexion is not None:
            conexion.close()

    if usuario is None:
        log_audit("LOGIN", f"Login fallido: el usuario '{username}' no existe", "FALLIDO", id_usuario=None)
        return _error("Credenciales inválidas", 401)

    clave_valida = bcrypt.checkpw(password.encode("utf-8"), usuario["contrasena"].encode("utf-8"))
    if not clave_valida:
        log_audit(
            "LOGIN",
            f"Login fallido: contraseña incorrecta para '{username}'",
            "FALLIDO",
            id_usuario=usuario["id_usuario"],
        )
        return _error("Credenciales inválidas", 401)

    token = _generar_token(usuario)
    log_audit(
        "LOGIN",
        f"Login exitoso de '{username}'",
        "EXITOSO",
        id_usuario=usuario["id_usuario"],
    )
    return jsonify(
        {
            "token": token,
            "token_type": "Bearer",
            "expira_en_horas": JWT_EXPIRATION_HOURS,
            "usuario": {
                "id_usuario": usuario["id_usuario"],
                "username": usuario["username"],
                "rol": usuario["rol"],
            },
        }
    )
