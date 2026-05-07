"""
LIBRA — Auth + Users + Subscriptions
- JWT auth (registro/login)
- Rol: creator (Brian) → gratuito, ilimitado
- Rol: contador → paga por créditos vía MercadoPago
- Supabase como DB (o SQLite local para dev)
"""

import os, json, hashlib, secrets, sqlite3
from datetime import datetime, timedelta, date
from typing import Optional
from dataclasses import dataclass, asdict

# ── JWT simple (sin librería extra) ──────────────────────────────
import hmac, base64

SECRET_KEY = os.getenv("LIBRA_SECRET", "B.reqw.23r4r4rt.4r4r4r5.hnjujtvvrddvv")
CREATOR_EMAIL = os.getenv("CREATOR_EMAIL", "brianveron2@gmail.com")

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _sign(payload: dict, exp_hours: int = 72) -> str:
    payload = {**payload, "exp": (datetime.utcnow() + timedelta(hours=exp_hours)).isoformat()}
    header  = _b64(json.dumps({"alg":"HS256","typ":"JWT"}).encode())
    body    = _b64(json.dumps(payload).encode())
    sig     = _b64(hmac.new(SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"

def _verify(token: str) -> Optional[dict]:
    try:
        header, body, sig = token.split(".")
        expected = _b64(hmac.new(SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
        if sig != expected:
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=="))
        if datetime.fromisoformat(payload["exp"]) < datetime.utcnow():
            return None
        return payload
    except:
        return None

def hash_password(pwd: str) -> str:
    salt = os.getenv("LIBRA_SALT", "libra-salt-2025")
    return hashlib.sha256(f"{salt}{pwd}".encode()).hexdigest()


# ── DB local SQLite (swappable por Supabase) ──────────────────────
DB_PATH = os.getenv("LIBRA_DB", "/app/libra.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        email       TEXT UNIQUE NOT NULL,
        nombre      TEXT NOT NULL,
        password    TEXT NOT NULL,
        rol         TEXT DEFAULT 'contador',   -- 'creator' | 'contador'
        plan        TEXT DEFAULT 'free',        -- 'free' | 'pro' | 'enterprise'
        creditos    INTEGER DEFAULT 0,
        activo      BOOLEAN DEFAULT 1,
        created_at  TEXT DEFAULT (datetime('now')),
        last_login  TEXT
    );
    CREATE TABLE IF NOT EXISTS estudios (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre      TEXT NOT NULL,
        slug        TEXT UNIQUE NOT NULL,
        owner_id    INTEGER REFERENCES usuarios(id),
        created_at  TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS estudio_miembros (
        estudio_id  INTEGER REFERENCES estudios(id),
        usuario_id  INTEGER REFERENCES usuarios(id),
        rol         TEXT DEFAULT 'member',  -- 'admin' | 'member' | 'viewer'
        PRIMARY KEY (estudio_id, usuario_id)
    );
    CREATE TABLE IF NOT EXISTS empresas (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        estudio_id          INTEGER REFERENCES estudios(id),
        razon_social        TEXT NOT NULL,
        cuit                TEXT NOT NULL,
        tipo                TEXT DEFAULT 'S.A.',
        actividad           TEXT,
        domicilio           TEXT,
        capital_suscripto   REAL DEFAULT 0,
        fecha_inscripcion   TEXT,
        fecha_estatuto      TEXT,
        consejo_profesional TEXT DEFAULT 'CPCE Buenos Aires',
        nro_inscripcion     TEXT,
        duracion_anos       INTEGER DEFAULT 99,
        activa              BOOLEAN DEFAULT 1,
        created_at          TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS ejercicios (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id      INTEGER REFERENCES empresas(id),
        numero          INTEGER NOT NULL,
        fecha_inicio    TEXT NOT NULL,
        fecha_cierre    TEXT NOT NULL,
        estado          TEXT DEFAULT 'borrador',  -- 'borrador' | 'emitido'
        created_at      TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS cuentas (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ejercicio_id INTEGER REFERENCES ejercicios(id),
        codigo      TEXT NOT NULL,
        descripcion TEXT,
        debe        REAL DEFAULT 0,
        haber       REAL DEFAULT 0,
        saldo       REAL DEFAULT 0,
        tipo        TEXT,
        rubro       TEXT,
        subrubro    TEXT
    );
    CREATE TABLE IF NOT EXISTS firmantes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        estudio_id  INTEGER REFERENCES estudios(id),
        nombre      TEXT NOT NULL,
        titulo      TEXT,
        matricula   TEXT,
        activo      BOOLEAN DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS transacciones (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id      INTEGER REFERENCES usuarios(id),
        tipo            TEXT,   -- 'compra_creditos' | 'consumo_balance'
        creditos        INTEGER,
        monto           REAL DEFAULT 0,
        mp_payment_id   TEXT,
        estado          TEXT DEFAULT 'pendiente',  -- 'pendiente' | 'aprobado' | 'rechazado'
        created_at      TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS balances_emitidos (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        ejercicio_id    INTEGER REFERENCES ejercicios(id),
        usuario_id      INTEGER REFERENCES usuarios(id),
        version         INTEGER DEFAULT 1,
        formato         TEXT DEFAULT 'pdf',
        tamano_kb       REAL,
        created_at      TEXT DEFAULT (datetime('now'))
    );
    """)

    # Insertar Brian como creator si no existe
    existing = db.execute("SELECT id FROM usuarios WHERE email=?", (CREATOR_EMAIL,)).fetchone()
    if not existing:
        db.execute("""
            INSERT INTO usuarios (email, nombre, password, rol, plan, creditos)
            VALUES (?, ?, ?, 'creator', 'enterprise', 999999)
        """, (CREATOR_EMAIL, "Brian Verón", hash_password("libra2025")))
        db.commit()
        # Crear estudio por defecto para Brian
        uid = db.execute("SELECT id FROM usuarios WHERE email=?", (CREATOR_EMAIL,)).fetchone()["id"]
        db.execute("INSERT INTO estudios (nombre, slug, owner_id) VALUES ('Ofi', 'ofi', ?)", (uid,))
        db.execute("INSERT INTO estudio_miembros VALUES ((SELECT id FROM estudios WHERE slug='ofi'), ?, 'admin')", (uid,))
        db.commit()

    db.close()


# ── Auth functions ────────────────────────────────────────────────

def registrar_usuario(email: str, nombre: str, password: str) -> dict:
    """Registra un nuevo usuario contador con 2 créditos gratis para probar."""
    db = get_db()
    existing = db.execute("SELECT id FROM usuarios WHERE email=?", (email.lower(),)).fetchone()
    if existing:
        db.close()
        return {"ok": False, "error": "Email ya registrado"}

    hashed = hash_password(password)
    slug = email.split("@")[0].lower().replace(".", "")[:20] + secrets.token_hex(3)

    db.execute("""
        INSERT INTO usuarios (email, nombre, password, rol, plan, creditos)
        VALUES (?, ?, ?, 'contador', 'free', 2)
    """, (email.lower(), nombre, hashed))
    db.commit()

    uid = db.execute("SELECT id FROM usuarios WHERE email=?", (email.lower(),)).fetchone()["id"]

    # Crear estudio por defecto
    nombre_estudio = nombre.split()[0] if nombre else "Mi estudio"
    db.execute("INSERT INTO estudios (nombre, slug, owner_id) VALUES (?, ?, ?)",
               (nombre_estudio, slug, uid))
    db.commit()
    estudio_id = db.execute("SELECT id FROM estudios WHERE slug=?", (slug,)).fetchone()["id"]
    db.execute("INSERT INTO estudio_miembros VALUES (?, ?, 'admin')", (estudio_id, uid))
    db.commit()
    db.close()

    token = _sign({"sub": email.lower(), "uid": uid, "rol": "contador"})
    return {"ok": True, "token": token, "uid": uid, "nombre": nombre, "creditos": 2, "rol": "contador"}


def login_usuario(email: str, password: str) -> dict:
    """Login. Devuelve JWT."""
    db = get_db()
    user = db.execute("SELECT * FROM usuarios WHERE email=? AND activo=1",
                      (email.lower(),)).fetchone()
    db.close()
    if not user:
        return {"ok": False, "error": "Usuario no encontrado"}
    if user["password"] != hash_password(password):
        return {"ok": False, "error": "Contraseña incorrecta"}

    db = get_db()
    db.execute("UPDATE usuarios SET last_login=datetime('now') WHERE id=?", (user["id"],))
    db.commit()
    db.close()

    token = _sign({
        "sub": user["email"], "uid": user["id"],
        "rol": user["rol"], "plan": user["plan"]
    })
    return {
        "ok": True, "token": token,
        "uid": user["id"], "nombre": user["nombre"],
        "email": user["email"], "rol": user["rol"],
        "plan": user["plan"], "creditos": user["creditos"]
    }


def get_user_from_token(token: str) -> Optional[dict]:
    payload = _verify(token)
    if not payload:
        return None
    db = get_db()
    user = db.execute("SELECT * FROM usuarios WHERE id=? AND activo=1",
                      (payload["uid"],)).fetchone()
    db.close()
    return dict(user) if user else None


def is_creator(user: dict) -> bool:
    return user.get("rol") == "creator" or user.get("email") == CREATOR_EMAIL


def consumir_credito(user_id: int, ejercicio_id: int, formato: str = "pdf") -> dict:
    """Descuenta 1 crédito. Creator no consume créditos."""
    db = get_db()
    user = db.execute("SELECT * FROM usuarios WHERE id=?", (user_id,)).fetchone()
    if not user:
        db.close()
        return {"ok": False, "error": "Usuario no encontrado"}

    if user["rol"] == "creator":
        db.close()
        return {"ok": True, "creditos_restantes": 999999, "gratis": True}

    if user["creditos"] < 1:
        db.close()
        return {"ok": False, "error": "Sin créditos disponibles. Comprá más en Configuración."}

    db.execute("UPDATE usuarios SET creditos=creditos-1 WHERE id=?", (user_id,))
    db.execute("""
        INSERT INTO transacciones (usuario_id, tipo, creditos, estado)
        VALUES (?, 'consumo_balance', -1, 'aprobado')
    """, (user_id,))
    restantes = user["creditos"] - 1

    # Registrar balance emitido
    db.execute("""
        INSERT INTO balances_emitidos (ejercicio_id, usuario_id, formato)
        VALUES (?, ?, ?)
    """, (ejercicio_id, user_id, formato))
    db.commit()
    db.close()
    return {"ok": True, "creditos_restantes": restantes}


def agregar_creditos(user_id: int, cantidad: int, monto: float, mp_id: str = None) -> dict:
    """Agrega créditos tras pago aprobado."""
    db = get_db()
    db.execute("UPDATE usuarios SET creditos=creditos+? WHERE id=?", (cantidad, user_id))
    db.execute("""
        INSERT INTO transacciones (usuario_id, tipo, creditos, monto, mp_payment_id, estado)
        VALUES (?, 'compra_creditos', ?, ?, ?, 'aprobado')
    """, (user_id, cantidad, monto, mp_id or "manual"))
    db.commit()
    user = db.execute("SELECT creditos FROM usuarios WHERE id=?", (user_id,)).fetchone()
    db.close()
    return {"ok": True, "creditos_nuevos": cantidad, "creditos_total": user["creditos"]}


# ── Empresas CRUD ────────────────────────────────────────────────

def crear_empresa(estudio_id: int, data: dict) -> dict:
    db = get_db()
    db.execute("""
        INSERT INTO empresas (estudio_id, razon_social, cuit, tipo, actividad, domicilio,
            capital_suscripto, fecha_inscripcion, fecha_estatuto, consejo_profesional,
            nro_inscripcion, duracion_anos)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (estudio_id, data["razon_social"], data["cuit"], data.get("tipo","S.A."),
          data.get("actividad",""), data.get("domicilio",""),
          data.get("capital_suscripto",0), data.get("fecha_inscripcion"),
          data.get("fecha_estatuto"), data.get("consejo_profesional","CPCE Buenos Aires"),
          data.get("nro_inscripcion",""), data.get("duracion_anos",99)))
    db.commit()
    eid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()
    return {"ok": True, "empresa_id": eid}


def listar_empresas(estudio_id: int) -> list:
    db = get_db()
    rows = db.execute("SELECT * FROM empresas WHERE estudio_id=? AND activa=1 ORDER BY razon_social",
                      (estudio_id,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def crear_ejercicio(empresa_id: int, numero: int, fecha_inicio: str, fecha_cierre: str) -> dict:
    db = get_db()
    db.execute("""
        INSERT INTO ejercicios (empresa_id, numero, fecha_inicio, fecha_cierre)
        VALUES (?,?,?,?)
    """, (empresa_id, numero, fecha_inicio, fecha_cierre))
    db.commit()
    eid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()
    return {"ok": True, "ejercicio_id": eid}


def guardar_cuentas(ejercicio_id: int, cuentas: list) -> dict:
    db = get_db()
    db.execute("DELETE FROM cuentas WHERE ejercicio_id=?", (ejercicio_id,))
    for c in cuentas:
        db.execute("""
            INSERT INTO cuentas (ejercicio_id, codigo, descripcion, debe, haber, saldo, tipo, rubro, subrubro)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (ejercicio_id, c.get("codigo",""), c.get("descripcion",""),
              c.get("debe",0), c.get("haber",0), c.get("saldo",0),
              c.get("tipo",""), c.get("rubro",""), c.get("subrubro","")))
    db.commit()
    db.close()
    return {"ok": True, "cuentas_guardadas": len(cuentas)}


def listar_cuentas(ejercicio_id: int) -> list:
    db = get_db()
    rows = db.execute("SELECT * FROM cuentas WHERE ejercicio_id=? ORDER BY codigo",
                      (ejercicio_id,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def marcar_ejercicio_emitido(ejercicio_id: int) -> dict:
    db = get_db()
    db.execute("UPDATE ejercicios SET estado='emitido' WHERE id=?", (ejercicio_id,))
    db.commit()
    db.close()
    return {"ok": True}


# ── MercadoPago (webhook + preferencia) ──────────────────────────

PACKS_CREDITOS = {
    "1":  {"creditos": 1,  "precio": 49999},
    "10": {"creditos": 10, "precio": 449990},
    "25": {"creditos": 25, "precio": 1124975},
    "50": {"creditos": 50, "precio": 1999950},
}

def crear_preferencia_mp(user_id: int, pack: str, email_mp: str) -> dict:
    """
    Genera el payload para crear una preferencia en MercadoPago.
    En producción: llamar a la API de MP con el SDK.
    Devuelve la URL de checkout.
    """
    p = PACKS_CREDITOS.get(pack)
    if not p:
        return {"ok": False, "error": "Pack inválido"}

    # En producción usar el SDK de MercadoPago:
    # import mercadopago
    # sdk = mercadopago.SDK(os.getenv("MP_ACCESS_TOKEN"))
    # preference_data = {"items": [...], "payer": {"email": email_mp}, ...}
    # sdk.preference().create(preference_data)

    return {
        "ok": True,
        "checkout_url": f"https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=DEMO_{user_id}_{pack}",
        "creditos": p["creditos"],
        "precio": p["precio"],
        "nota": "Integrá MP_ACCESS_TOKEN en producción para pagos reales"
    }


def procesar_webhook_mp(payload: dict) -> dict:
    """
    Procesa notificación de pago de MercadoPago.
    En producción llamar a MP para verificar el estado del pago.
    """
    payment_id = payload.get("data", {}).get("id")
    topic      = payload.get("type")

    if topic != "payment" or not payment_id:
        return {"ok": False, "msg": "No es un pago"}

    # Aquí irías a MP API a buscar el pago y verificar approved
    # Por ahora simulamos:
    # mp_payment = sdk.payment().get(payment_id)
    # if mp_payment["status"] == "approved":
    #     user_id = mp_payment["metadata"]["user_id"]
    #     pack    = mp_payment["metadata"]["pack"]
    #     agregar_creditos(user_id, PACKS_CREDITOS[pack]["creditos"], mp_payment["transaction_amount"], payment_id)

    return {"ok": True, "payment_id": payment_id, "msg": "Procesado (demo)"}


# ── Firmantes ────────────────────────────────────────────────────

def listar_firmantes(estudio_id: int) -> list:
    db = get_db()
    rows = db.execute("SELECT * FROM firmantes WHERE estudio_id=? AND activo=1", (estudio_id,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def agregar_firmante(estudio_id: int, nombre: str, titulo: str, matricula: str = "") -> dict:
    db = get_db()
    db.execute("INSERT INTO firmantes (estudio_id, nombre, titulo, matricula) VALUES (?,?,?,?)",
               (estudio_id, nombre, titulo, matricula))
    db.commit()
    db.close()
    return {"ok": True}


# ── Plan de cuentas predefinido ──────────────────────────────────

PLAN_CUENTAS_COMERCIAL = [
    ("1.1.1.1","Caja"),("1.1.1.2","Banco Cuenta Corriente"),("1.1.1.3","Banco Caja de Ahorros"),
    ("1.1.2.1","Inversiones Financieras C.P."),
    ("1.1.3.1","Créditos por Ventas"),("1.1.3.2","Documentos a Cobrar"),
    ("1.1.4.1","Bienes de Cambio"),
    ("1.1.5.1","IVA Crédito Fiscal"),("1.1.5.2","Anticipo Impuesto a las Ganancias"),
    ("1.1.7.1","Otros Créditos Corrientes"),
    ("1.2.1.1","Bienes de Uso"),("1.2.1.2","Amortiz. Acum. Bienes de Uso"),
    ("1.2.3.1","Activos Intangibles"),("1.2.3.2","Amortiz. Acum. Intangibles"),
    ("2.1.1.1","Proveedores"),("2.1.1.2","Documentos a Pagar"),
    ("2.1.3.1","IVA Débito Fiscal"),("2.1.3.2","IIBB a Pagar"),("2.1.3.3","IVA a Pagar"),
    ("2.1.4.1","Cargas Sociales a Pagar"),("2.1.4.2","Sueldos a Pagar"),
    ("2.1.5.1","Provisión Impuesto Ganancias"),
    ("2.1.7.1","Honorarios Directorio a Pagar"),
    ("2.2.1.1","Préstamos Bancarios L.P."),("2.2.2.1","Hipotecas"),
    ("3.1.1.1","Capital Suscripto"),("3.1.2.1","Ajuste del Capital"),
    ("3.1.3.1","Resultado del Ejercicio"),("3.1.4.1","Resultados No Asignados"),("3.1.5.1","Reserva Legal"),
    ("4.1.1.1","Ventas"),("4.1.1.2","Descuentos y Bonificaciones"),
    ("4.1.3.1","Intereses Ganados"),("4.1.3.2","Diferencia de Cambio Positiva"),
    ("4.2.1.1","Costo de Mercaderías Vendidas"),
    ("4.2.2.1","IIBB"),
    ("4.2.3.1","Amortiz. Activos Intangibles"),
    ("4.2.4.1","Depreciación Bienes de Uso"),
    ("4.2.5.1","Gastos Bancarios"),("4.2.5.2","Intereses Pagados"),
    ("4.2.6.1","Honorarios Directorio"),("4.2.7.1","Honorarios Profesionales"),
    ("4.2.7.2","Honorarios Contadores"),
    ("4.2.8.1","RECPAM"),("4.2.8.2","Diferencia de Cambio Negativa"),
    ("4.2.9.1","Impuesto a las Ganancias"),
]

PLAN_CUENTAS_AGROPECUARIO = [
    ("1.1.1.1","Caja"),("1.1.1.2","Banco CC"),
    ("1.1.4.1","Hacienda para Venta"),("1.1.4.2","Cereales y Oleaginosas"),("1.1.4.3","Semillas"),
    ("1.1.7.1","Anticipo a Proveedores"),
    ("1.2.1.1","Inmuebles Rurales"),("1.2.1.2","Maquinaria Agrícola"),
    ("1.2.1.3","Rodados"),("1.2.1.4","Amortiz. Acum. Bienes de Uso"),
    ("1.2.1.5","Hacienda de Cría"),("1.2.1.6","Plantaciones"),
    ("2.1.1.1","Proveedores"),("2.1.3.1","IIBB a Pagar"),("2.1.3.2","Impuesto a las Ganancias a Pagar"),
    ("2.2.1.1","Préstamos Bancarios"),
    ("3.1.1.1","Capital"),("3.1.2.1","Ajuste del Capital"),
    ("3.1.3.1","Resultado del Ejercicio"),("3.1.4.1","Resultados No Asignados"),
    ("4.1.1.1","Venta de Hacienda"),("4.1.1.2","Venta de Cereales"),("4.1.1.3","Venta de Granos"),
    ("4.2.1.1","Costo de Hacienda Vendida"),("4.2.1.2","Costo de Cereales Vendidos"),
    ("4.2.2.1","IIBB"),("4.2.4.1","Amortiz. Bienes de Uso"),
    ("4.2.5.1","Gastos Bancarios"),("4.2.7.1","Honorarios Profesionales"),
    ("4.2.8.1","RECPAM"),("4.2.9.1","Impuesto a las Ganancias"),
]

PLANES = {"comercial": PLAN_CUENTAS_COMERCIAL, "agropecuario": PLAN_CUENTAS_AGROPECUARIO}


# ── Estadísticas del estudio ─────────────────────────────────────

def stats_estudio(estudio_id: int) -> dict:
    db = get_db()
    empresas = db.execute("SELECT COUNT(*) FROM empresas WHERE estudio_id=? AND activa=1", (estudio_id,)).fetchone()[0]
    ejercicios = db.execute("""
        SELECT COUNT(*) FROM ejercicios e
        JOIN empresas emp ON e.empresa_id=emp.id
        WHERE emp.estudio_id=?
    """, (estudio_id,)).fetchone()[0]
    balances = db.execute("""
        SELECT COUNT(*) FROM balances_emitidos be
        JOIN ejercicios e ON be.ejercicio_id=e.id
        JOIN empresas emp ON e.empresa_id=emp.id
        WHERE emp.estudio_id=?
    """, (estudio_id,)).fetchone()[0]
    db.close()
    return {"empresas": empresas, "ejercicios": ejercicios, "balances_emitidos": balances}


# ── Init ──────────────────────────────────────────────────────────
init_db()

if __name__ == "__main__":
    print("=== LIBRA — Auth & DB Test ===")
    # Test registro
    r1 = registrar_usuario("contador@test.com", "María García", "test1234")
    print("Registro:", r1["ok"], "| Créditos iniciales:", r1.get("creditos"))
    # Test login
    r2 = login_usuario("contador@test.com", "test1234")
    print("Login OK:", r2["ok"], "| Rol:", r2.get("rol"))
    # Test token
    user = get_user_from_token(r2["token"])
    print("Token válido:", user["nombre"], "| Creator:", is_creator(user))
    # Test Brian
    r3 = login_usuario(CREATOR_EMAIL, "libra2025")
    print("Brian login:", r3["ok"], "| Creator:", r3.get("rol"))
    u3 = get_user_from_token(r3["token"])
    print("Brian is creator:", is_creator(u3))
    # Test consumo
    c1 = consumir_credito(user["id"], 1)
    c2 = consumir_credito(u3["id"], 1)
    print("Consumo contador:", c1)
    print("Consumo creator:", c2)
    # Stats
    db = get_db()
    est = db.execute("SELECT id FROM estudios WHERE owner_id=?", (u3["id"],)).fetchone()
    db.close()
    if est:
        print("Stats estudio Brian:", stats_estudio(est["id"]))
    print("\n✅ Auth & DB OK")
