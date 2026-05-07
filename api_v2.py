"""
LIBRA — API v2 completa con Auth
Todos los endpoints protegidos con JWT.
Creator (Brian) es gratis e ilimitado.
"""
import os, sys, io, tempfile
from datetime import date, datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

sys.path.insert(0, os.path.dirname(__file__))
from motor_contable import (
    Cuenta, Ejercicio, Empresa, MotorContable, ResultadoBalance,
    importar_excel, exportar_excel, generar_pdf_balance,
    variacion_ipc_ejercicio, get_ipc, IPC_FACPCE
)
from auth import (
    registrar_usuario, login_usuario, get_user_from_token, is_creator,
    consumir_credito, agregar_creditos, crear_empresa, listar_empresas,
    crear_ejercicio, guardar_cuentas, listar_cuentas, marcar_ejercicio_emitido,
    crear_preferencia_mp, procesar_webhook_mp, listar_firmantes, agregar_firmante,
    stats_estudio, PACKS_CREDITOS, PLANES, get_db, hash_password
)

app = FastAPI(title="LIBRA API v2", version="2.0.0", description="Motor contable RT54 argentino")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# ── Auth dependency ───────────────────────────────────────────────

def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = authorization.replace("Bearer ", "")
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return user

def require_credits(user: dict):
    if is_creator(user):
        return
    if user["creditos"] < 1:
        raise HTTPException(status_code=402,
            detail="Sin créditos. Comprá más en Configuración → Créditos.")

# ── Schemas ───────────────────────────────────────────────────────

class RegisterIn(BaseModel):
    email: str
    nombre: str
    password: str

class LoginIn(BaseModel):
    email: str
    password: str

class CuentaIn(BaseModel):
    codigo: str; descripcion: str = ""
    debe: float = 0; haber: float = 0; saldo: Optional[float] = None

class EjercicioCalcIn(BaseModel):
    numero: int = 1
    fecha_inicio: str = "01/01/2025"
    fecha_cierre: str = "31/12/2025"
    cuentas: list[CuentaIn]

class EmpresaIn(BaseModel):
    razon_social: str; cuit: str; tipo: str = "S.A."
    actividad: str = ""; domicilio: str = ""
    capital_suscripto: float = 0
    fecha_inscripcion: Optional[str] = None
    fecha_estatuto: Optional[str] = None
    consejo_profesional: str = "CPCE Buenos Aires"
    nro_inscripcion: str = ""; duracion_anos: int = 99

class EjercicioIn(BaseModel):
    empresa_id: int; numero: int
    fecha_inicio: str; fecha_cierre: str

class CuentasIn(BaseModel):
    ejercicio_id: int; cuentas: list[CuentaIn]

class EmitirIn(BaseModel):
    empresa_id: int; ejercicio_id: int
    firmantes: list[dict] = []
    incluir_notas: bool = True
    formato: str = "pdf"
    es_agropecuaria: bool = False

class FirmanteIn(BaseModel):
    nombre: str; titulo: str = "Contador Público"
    matricula: str = ""

class ComprarIn(BaseModel):
    pack: str; email_mp: str

class CambiarPasswordIn(BaseModel):
    password_actual: str; password_nuevo: str

# ── Helpers ───────────────────────────────────────────────────────

def parse_fecha(s: str) -> date:
    for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
        try:
            return datetime.strptime(s, fmt).date()
        except: pass
    raise ValueError(f"Fecha inválida: {s}")

def build_ejercicio_obj(data: EjercicioCalcIn) -> Ejercicio:
    cuentas = []
    for c in data.cuentas:
        saldo = c.saldo if c.saldo is not None else c.debe - c.haber
        cuentas.append(Cuenta(c.codigo, c.descripcion, c.debe, c.haber, saldo))
    return Ejercicio(data.numero, parse_fecha(data.fecha_inicio),
                     parse_fecha(data.fecha_cierre), cuentas)

def resultado_dict(r: ResultadoBalance) -> dict:
    return {
        "activo_corriente": r.activo_corriente, "activo_no_corriente": r.activo_no_corriente,
        "total_activo": r.total_activo, "pasivo_corriente": r.pasivo_corriente,
        "pasivo_no_corriente": r.pasivo_no_corriente, "total_pasivo": r.total_pasivo,
        "patrimonio_neto": r.patrimonio_neto, "resultado_ejercicio": r.resultado_ejercicio,
        "total_pn_con_resultado": r.total_pn_con_resultado,
        "total_ingresos": r.total_ingresos, "total_gastos": r.total_gastos,
        "variacion_ipc": round(r.variacion_ipc, 2), "recpam": round(r.recpam, 2),
        "cuadra": r.cuadra, "diferencia": round(r.diferencia, 2),
        "clasificacion_rt54": r.clasificacion_rt54,
        "margen_neto": round(r.margen_neto, 2), "roa": round(r.roa, 2),
        "liquidez_corriente": round(r.liquidez_corriente, 2),
        "solvencia": round(r.solvencia, 2), "endeudamiento": round(r.endeudamiento, 2),
    }

def cuenta_dict(c: Cuenta) -> dict:
    return {"codigo": c.codigo, "descripcion": c.descripcion,
            "debe": c.debe, "haber": c.haber, "saldo": c.saldo,
            "tipo": c.tipo, "rubro": c.rubro, "subrubro": c.subrubro,
            "saldo_reexpresado": c.saldo_reexpresado, "coef_aplicado": round(c.coef_aplicado, 6)}

def get_estudio_id(user_id: int) -> int:
    db = get_db()
    row = db.execute("""
        SELECT estudio_id FROM estudio_miembros
        WHERE usuario_id=? ORDER BY estudio_id LIMIT 1
    """, (user_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="No tenés un estudio asignado")
    return row["estudio_id"]

# ══════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {"app": "LIBRA", "version": "2.0.0", "status": "ok",
            "docs": "/docs", "motor": "RT54 + AxI + RECPAM"}

@app.get("/health")
def health():
    return {"status": "ok", "ipc_periodos": len(IPC_FACPCE),
            "motor": "RT54", "db": "SQLite (dev) → Supabase (prod)"}

@app.post("/auth/register", tags=["Auth"])
def register(data: RegisterIn):
    """Registro público. 2 créditos gratis para probar."""
    if len(data.password) < 6:
        raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres")
    result = registrar_usuario(data.email.strip(), data.nombre.strip(), data.password)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result

@app.post("/auth/login", tags=["Auth"])
def login(data: LoginIn):
    """Login. Devuelve JWT Bearer token."""
    result = login_usuario(data.email.strip(), data.password)
    if not result["ok"]:
        raise HTTPException(401, result["error"])
    return result

@app.get("/auth/me", tags=["Auth"])
def me(user: dict = Depends(get_current_user)):
    """Info del usuario autenticado."""
    return {
        "id": user["id"], "email": user["email"], "nombre": user["nombre"],
        "rol": user["rol"], "plan": user["plan"],
        "creditos": 999999 if is_creator(user) else user["creditos"],
        "es_creator": is_creator(user),
    }

@app.put("/auth/password", tags=["Auth"])
def cambiar_password(data: CambiarPasswordIn, user: dict = Depends(get_current_user)):
    db = get_db()
    if user["password"] != hash_password(data.password_actual):
        db.close()
        raise HTTPException(400, "Contraseña actual incorrecta")
    db.execute("UPDATE usuarios SET password=? WHERE id=?",
               (hash_password(data.password_nuevo), user["id"]))
    db.commit()
    db.close()
    return {"ok": True, "msg": "Contraseña actualizada"}

# ══════════════════════════════════════════════════════════════════
# ESTUDIO
# ══════════════════════════════════════════════════════════════════

@app.get("/estudio", tags=["Estudio"])
def get_estudio(user: dict = Depends(get_current_user)):
    estudio_id = get_estudio_id(user["id"])
    db = get_db()
    est = db.execute("SELECT * FROM estudios WHERE id=?", (estudio_id,)).fetchone()
    miembros = db.execute("""
        SELECT u.id, u.nombre, u.email, u.rol, em.rol as rol_estudio
        FROM estudio_miembros em JOIN usuarios u ON em.usuario_id=u.id
        WHERE em.estudio_id=?
    """, (estudio_id,)).fetchall()
    db.close()
    stats = stats_estudio(estudio_id)
    return {
        **dict(est), "stats": stats,
        "miembros": [dict(m) for m in miembros],
        "creditos_usuario": 999999 if is_creator(user) else user["creditos"],
        "es_creator": is_creator(user),
    }

@app.put("/estudio", tags=["Estudio"])
def update_estudio(data: dict, user: dict = Depends(get_current_user)):
    estudio_id = get_estudio_id(user["id"])
    db = get_db()
    if "nombre" in data:
        db.execute("UPDATE estudios SET nombre=? WHERE id=?", (data["nombre"], estudio_id))
    db.commit()
    db.close()
    return {"ok": True}

@app.get("/estudio/firmantes", tags=["Estudio"])
def get_firmantes(user: dict = Depends(get_current_user)):
    estudio_id = get_estudio_id(user["id"])
    return {"firmantes": listar_firmantes(estudio_id)}

@app.post("/estudio/firmantes", tags=["Estudio"])
def add_firmante(data: FirmanteIn, user: dict = Depends(get_current_user)):
    estudio_id = get_estudio_id(user["id"])
    result = agregar_firmante(estudio_id, data.nombre, data.titulo, data.matricula)
    return result

@app.delete("/estudio/firmantes/{fid}", tags=["Estudio"])
def del_firmante(fid: int, user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute("UPDATE firmantes SET activo=0 WHERE id=?", (fid,))
    db.commit()
    db.close()
    return {"ok": True}

# ══════════════════════════════════════════════════════════════════
# EMPRESAS
# ══════════════════════════════════════════════════════════════════

@app.get("/empresas", tags=["Empresas"])
def get_empresas(user: dict = Depends(get_current_user)):
    estudio_id = get_estudio_id(user["id"])
    empresas = listar_empresas(estudio_id)
    # Para cada empresa, traer sus ejercicios
    db = get_db()
    for e in empresas:
        e["ejercicios"] = [dict(r) for r in db.execute(
            "SELECT * FROM ejercicios WHERE empresa_id=? ORDER BY numero DESC",
            (e["id"],)).fetchall()]
    db.close()
    return {"empresas": empresas}

@app.post("/empresas", tags=["Empresas"])
def post_empresa(data: EmpresaIn, user: dict = Depends(get_current_user)):
    estudio_id = get_estudio_id(user["id"])
    result = crear_empresa(estudio_id, data.dict())
    return result

@app.get("/empresas/{empresa_id}", tags=["Empresas"])
def get_empresa(empresa_id: int, user: dict = Depends(get_current_user)):
    estudio_id = get_estudio_id(user["id"])
    db = get_db()
    emp = db.execute(
        "SELECT * FROM empresas WHERE id=? AND estudio_id=?",
        (empresa_id, estudio_id)).fetchone()
    if not emp:
        db.close()
        raise HTTPException(404, "Empresa no encontrada")
    ejercicios = db.execute(
        "SELECT * FROM ejercicios WHERE empresa_id=? ORDER BY numero DESC",
        (empresa_id,)).fetchall()
    db.close()
    return {**dict(emp), "ejercicios": [dict(e) for e in ejercicios]}

@app.put("/empresas/{empresa_id}", tags=["Empresas"])
def put_empresa(empresa_id: int, data: EmpresaIn, user: dict = Depends(get_current_user)):
    estudio_id = get_estudio_id(user["id"])
    db = get_db()
    db.execute("""
        UPDATE empresas SET razon_social=?, cuit=?, tipo=?, actividad=?, domicilio=?,
        capital_suscripto=?, fecha_inscripcion=?, fecha_estatuto=?,
        consejo_profesional=?, nro_inscripcion=?, duracion_anos=?
        WHERE id=? AND estudio_id=?
    """, (data.razon_social, data.cuit, data.tipo, data.actividad, data.domicilio,
          data.capital_suscripto, data.fecha_inscripcion, data.fecha_estatuto,
          data.consejo_profesional, data.nro_inscripcion, data.duracion_anos,
          empresa_id, estudio_id))
    db.commit()
    db.close()
    return {"ok": True}

@app.delete("/empresas/{empresa_id}", tags=["Empresas"])
def del_empresa(empresa_id: int, user: dict = Depends(get_current_user)):
    estudio_id = get_estudio_id(user["id"])
    db = get_db()
    db.execute("UPDATE empresas SET activa=0 WHERE id=? AND estudio_id=?",
               (empresa_id, estudio_id))
    db.commit()
    db.close()
    return {"ok": True}

# ══════════════════════════════════════════════════════════════════
# EJERCICIOS & CUENTAS
# ══════════════════════════════════════════════════════════════════

@app.post("/ejercicios", tags=["Ejercicios"])
def post_ejercicio(data: EjercicioIn, user: dict = Depends(get_current_user)):
    result = crear_ejercicio(data.empresa_id, data.numero, data.fecha_inicio, data.fecha_cierre)
    return result

@app.get("/ejercicios/{ejercicio_id}/cuentas", tags=["Ejercicios"])
def get_cuentas(ejercicio_id: int, user: dict = Depends(get_current_user)):
    cuentas = listar_cuentas(ejercicio_id)
    return {"cuentas": cuentas, "total": len(cuentas)}

@app.post("/ejercicios/{ejercicio_id}/cuentas", tags=["Ejercicios"])
def post_cuentas(ejercicio_id: int, data: CuentasIn, user: dict = Depends(get_current_user)):
    result = guardar_cuentas(ejercicio_id, [c.dict() for c in data.cuentas])
    return result

# ══════════════════════════════════════════════════════════════════
# MOTOR CONTABLE (sin auth para herramientas)
# ══════════════════════════════════════════════════════════════════

@app.post("/calcular", tags=["Motor"])
def calcular(data: EjercicioCalcIn, user: dict = Depends(get_current_user)):
    try:
        ej = build_ejercicio_obj(data)
        motor = MotorContable(ej)
        r = motor.calcular()
        motor.calcular_axi()
        return {"resultado": resultado_dict(r), "cuentas": [cuenta_dict(c) for c in motor.cuentas]}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/validar", tags=["Motor"])
def validar(data: EjercicioCalcIn, user: dict = Depends(get_current_user)):
    try:
        ej = build_ejercicio_obj(data)
        motor = MotorContable(ej)
        errores = motor.validar_saldos()
        r = motor.calcular()
        return {
            "cuadra": r.cuadra, "diferencia": r.diferencia, "errores": errores,
            "total_errores": sum(1 for e in errores if e["tipo"] == "error"),
            "total_advertencias": sum(1 for e in errores if e["tipo"] == "advertencia"),
        }
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/axi", tags=["Motor"])
def axi(data: EjercicioCalcIn, user: dict = Depends(get_current_user)):
    try:
        ej = build_ejercicio_obj(data)
        motor = MotorContable(ej)
        motor.calcular_axi()
        variacion = variacion_ipc_ejercicio(ej.fecha_inicio, ej.fecha_cierre)
        return {"variacion_ipc": round(variacion, 2), "cuentas": [cuenta_dict(c) for c in motor.cuentas]}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/comparativo", tags=["Motor"])
def comparativo(data: dict, user: dict = Depends(get_current_user)):
    try:
        from pydantic import parse_obj_as
        ej1 = build_ejercicio_obj(EjercicioCalcIn(**data["ejercicio_actual"]))
        ej2 = build_ejercicio_obj(EjercicioCalcIn(**data["ejercicio_anterior"]))
        m1 = MotorContable(ej1); m2 = MotorContable(ej2)
        return m1.comparar_con(m2)
    except Exception as e:
        raise HTTPException(400, str(e))

@app.get("/ipc/{anio}/{mes}", tags=["Motor"])
def ipc(anio: int, mes: int):
    return {"anio": anio, "mes": mes, "indice": get_ipc(anio, mes)}

@app.get("/ipc", tags=["Motor"])
def ipc_all():
    return {"indices": [{"anio": k[0], "mes": k[1], "indice": v} for k, v in sorted(IPC_FACPCE.items())]}

@app.post("/clasificar-rt54", tags=["Motor"])
def clasificar(data: dict):
    ingresos = float(data.get("ingresos_anuales", 0))
    agro     = bool(data.get("es_agropecuaria", False))
    motor    = MotorContable(Ejercicio(1, date.today(), date.today(), []))
    clasif   = motor.clasificar_rt54(ingresos, agro)
    labels   = {"EP":"Entidad Pequeña","EM":"Entidad Mediana","RE":"Restante Entidad"}
    return {"clasificacion": clasif, "label": labels[clasif],
            "umbral_ep": 3_500_000_000, "umbral_em": 12_000_000_000}

# ══════════════════════════════════════════════════════════════════
# IMPORTAR / EXPORTAR
# ══════════════════════════════════════════════════════════════════

@app.post("/importar-excel", tags=["Archivos"])
async def importar(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if not file.filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(400, "Formato no soportado. Usá .xlsx, .xls o .csv")
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(await file.read()); tmp_path = tmp.name
        cuentas = importar_excel(tmp_path)
        os.unlink(tmp_path)
        return {"total": len(cuentas), "cuentas": [cuenta_dict(c) for c in cuentas]}
    except Exception as e:
        raise HTTPException(400, f"Error al procesar: {str(e)}")

@app.post("/exportar-excel", tags=["Archivos"])
def exportar_xls(data: EjercicioCalcIn, user: dict = Depends(get_current_user)):
    try:
        ej = build_ejercicio_obj(data)
        motor = MotorContable(ej)
        r = motor.calcular(); motor.calcular_axi()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name
        exportar_excel(motor.cuentas, r, tmp_path)
        with open(tmp_path, "rb") as f: content = f.read()
        os.unlink(tmp_path)
        return Response(content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=libra-saldos-ej{data.numero}.xlsx"})
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/plantilla-excel", tags=["Archivos"])
def plantilla(tipo: str = "comercial"):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    plan = PLANES.get(tipo, PLANES["comercial"])
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Sumas y Saldos"
    headers = ["Código", "Descripción", "Debe", "Haber", "Saldo"]
    ws.append(headers)
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1A2840")
        c.alignment = Alignment(horizontal="center")
    for codigo, desc in plan:
        ws.append([codigo, desc, 0, 0, 0])
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 42
    for col in ["C","D","E"]: ws.column_dimensions[col].width = 18
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return Response(content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=plantilla-libra-{tipo}.xlsx"})

# ══════════════════════════════════════════════════════════════════
# EMISIÓN DE BALANCE (consume 1 crédito salvo creator)
# ══════════════════════════════════════════════════════════════════

@app.post("/emitir-balance", tags=["Balances"])
def emitir(req: EmitirIn, user: dict = Depends(get_current_user)):
    # Verificar créditos
    require_credits(user)

    # Cargar empresa desde DB
    db = get_db()
    emp_row = db.execute("SELECT * FROM empresas WHERE id=?", (req.empresa_id,)).fetchone()
    ej_row  = db.execute("SELECT * FROM ejercicios WHERE id=?", (req.ejercicio_id,)).fetchone()
    cuentas_rows = db.execute(
        "SELECT * FROM cuentas WHERE ejercicio_id=? ORDER BY codigo",
        (req.ejercicio_id,)).fetchall()
    db.close()

    if not emp_row or not ej_row:
        raise HTTPException(404, "Empresa o ejercicio no encontrado")

    cuentas = [Cuenta(
        codigo=r["codigo"], descripcion=r["descripcion"] or "",
        debe=r["debe"], haber=r["haber"], saldo=r["saldo"]
    ) for r in cuentas_rows]

    empresa = Empresa(
        razon_social=emp_row["razon_social"], cuit=emp_row["cuit"],
        tipo=emp_row["tipo"], actividad=emp_row["actividad"] or "",
        domicilio=emp_row["domicilio"] or "",
        capital_suscripto=emp_row["capital_suscripto"] or 0,
        fecha_inscripcion=datetime.strptime(emp_row["fecha_inscripcion"], "%d/%m/%Y").date() if emp_row["fecha_inscripcion"] else None,
        fecha_estatuto=datetime.strptime(emp_row["fecha_estatuto"], "%d/%m/%Y").date() if emp_row["fecha_estatuto"] else None,
        consejo_profesional=emp_row["consejo_profesional"] or "CPCE",
        nro_inscripcion=emp_row["nro_inscripcion"] or "",
        duracion_anos=emp_row["duracion_anos"] or 99,
    )
    ejercicio = Ejercicio(
        numero=ej_row["numero"],
        fecha_inicio=datetime.strptime(ej_row["fecha_inicio"], "%d/%m/%Y").date(),
        fecha_cierre=datetime.strptime(ej_row["fecha_cierre"], "%d/%m/%Y").date(),
        cuentas=cuentas
    )

    motor = MotorContable(ejercicio)
    resultado = motor.calcular(req.es_agropecuaria)
    motor.calcular_axi()

    # Consumir crédito
    consumo = consumir_credito(user["id"], req.ejercicio_id, req.formato)
    if not consumo["ok"]:
        raise HTTPException(402, consumo["error"])

    # Marcar ejercicio como emitido
    marcar_ejercicio_emitido(req.ejercicio_id)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    firmantes = req.firmantes or [{"nombre": "Contador Firmante", "titulo": "Contador Público"}]
    generar_pdf_balance(empresa=empresa, ejercicio=ejercicio, resultado=resultado,
                        cuentas=motor.cuentas, firmantes=firmantes,
                        path=tmp_path, incluir_notas=req.incluir_notas)

    with open(tmp_path, "rb") as f: content = f.read()
    os.unlink(tmp_path)

    nombre = empresa.razon_social.replace(" ", "_")[:25]
    return Response(content=content, media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=LIBRA_{nombre}_EJ{ejercicio.numero}.pdf",
            "X-Creditos-Restantes": str(consumo["creditos_restantes"]),
            "X-Gratis": str(consumo.get("gratis", False)),
        })

# Emisión con cuentas inline (sin guardar en DB)
@app.post("/emitir-balance-inline", tags=["Balances"])
def emitir_inline(req: dict, user: dict = Depends(get_current_user)):
    """Genera PDF directamente desde cuentas enviadas, sin empresa en DB."""
    require_credits(user)
    try:
        emp_data  = req.get("empresa", {})
        ej_data   = req.get("ejercicio", {})
        firmantes = req.get("firmantes", [])

        cuentas = []
        for c in ej_data.get("cuentas", []):
            saldo = c.get("saldo", c.get("debe", 0) - c.get("haber", 0))
            cuentas.append(Cuenta(c["codigo"], c.get("descripcion",""),
                                  c.get("debe",0), c.get("haber",0), saldo))

        empresa = Empresa(
            razon_social=emp_data.get("razon_social",""), cuit=emp_data.get("cuit",""),
            tipo=emp_data.get("tipo","S.A."), actividad=emp_data.get("actividad",""),
            domicilio=emp_data.get("domicilio",""),
            capital_suscripto=emp_data.get("capital_suscripto",0),
            consejo_profesional=emp_data.get("consejo_profesional","CPCE"),
            nro_inscripcion=emp_data.get("nro_inscripcion",""), duracion_anos=99,
        )
        ejercicio = Ejercicio(
            numero=ej_data.get("numero",1),
            fecha_inicio=datetime.strptime(ej_data.get("fecha_inicio","01/01/2025"), "%d/%m/%Y").date(),
            fecha_cierre=datetime.strptime(ej_data.get("fecha_cierre","31/12/2025"), "%d/%m/%Y").date(),
            cuentas=cuentas
        )

        motor = MotorContable(ejercicio)
        resultado = motor.calcular(req.get("es_agropecuaria", False))
        motor.calcular_axi()

        consumo = consumir_credito(user["id"], 0, "pdf")
        if not consumo["ok"]:
            raise HTTPException(402, consumo["error"])

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        generar_pdf_balance(empresa=empresa, ejercicio=ejercicio, resultado=resultado,
                            cuentas=motor.cuentas, firmantes=firmantes or [{"nombre":"Firmante","titulo":"CP"}],
                            path=tmp_path, incluir_notas=req.get("incluir_notas", True))
        with open(tmp_path,"rb") as f: content = f.read()
        os.unlink(tmp_path)

        return Response(content=content, media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=LIBRA_balance.pdf",
                "X-Creditos-Restantes": str(consumo["creditos_restantes"]),
                "X-Gratis": str(consumo.get("gratis",False)),
            })
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(500, str(e))

# ══════════════════════════════════════════════════════════════════
# CRÉDITOS & PAGOS
# ══════════════════════════════════════════════════════════════════

@app.get("/creditos", tags=["Créditos"])
def get_creditos(user: dict = Depends(get_current_user)):
    db = get_db()
    transacciones = db.execute(
        "SELECT * FROM transacciones WHERE usuario_id=? ORDER BY created_at DESC LIMIT 20",
        (user["id"],)).fetchall()
    db.close()
    return {
        "creditos": 999999 if is_creator(user) else user["creditos"],
        "es_creator": is_creator(user),
        "plan": user["plan"],
        "packs": PACKS_CREDITOS,
        "historial": [dict(t) for t in transacciones],
    }

@app.post("/creditos/comprar", tags=["Créditos"])
def comprar(data: ComprarIn, user: dict = Depends(get_current_user)):
    if is_creator(user):
        return {"ok": True, "msg": "Creator no necesita comprar créditos — ilimitado gratuito 🎉"}
    result = crear_preferencia_mp(user["id"], data.pack, data.email_mp)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result

@app.post("/creditos/webhook-mp", tags=["Créditos"])
async def webhook_mp(request: Request):
    """Webhook de MercadoPago. Procesa pagos aprobados."""
    payload = await request.json()
    result = procesar_webhook_mp(payload)
    return result

@app.post("/creditos/agregar-manual", tags=["Créditos"])
def agregar_manual(data: dict, user: dict = Depends(get_current_user)):
    """Solo creator puede agregar créditos manualmente."""
    if not is_creator(user):
        raise HTTPException(403, "Solo el creador puede agregar créditos manualmente")
    uid    = data.get("usuario_id")
    cant   = int(data.get("cantidad", 0))
    monto  = float(data.get("monto", 0))
    result = agregar_creditos(uid, cant, monto, "manual-creator")
    return result

# ══════════════════════════════════════════════════════════════════
# ADMIN (solo creator)
# ══════════════════════════════════════════════════════════════════

@app.get("/admin/usuarios", tags=["Admin"])
def admin_usuarios(user: dict = Depends(get_current_user)):
    if not is_creator(user):
        raise HTTPException(403, "Solo el creador puede ver esto")
    db = get_db()
    users = db.execute("""
        SELECT u.id, u.email, u.nombre, u.rol, u.plan, u.creditos,
               u.activo, u.created_at, u.last_login,
               COUNT(DISTINCT e.id) as empresas
        FROM usuarios u
        LEFT JOIN estudios est ON est.owner_id=u.id
        LEFT JOIN empresas e ON e.estudio_id=est.id AND e.activa=1
        GROUP BY u.id ORDER BY u.created_at DESC
    """).fetchall()
    db.close()
    return {"usuarios": [dict(u) for u in users], "total": len(users)}

@app.get("/admin/stats", tags=["Admin"])
def admin_stats(user: dict = Depends(get_current_user)):
    if not is_creator(user):
        raise HTTPException(403, "Solo el creador puede ver esto")
    db = get_db()
    s = {
        "total_usuarios":   db.execute("SELECT COUNT(*) FROM usuarios WHERE activo=1").fetchone()[0],
        "total_estudios":   db.execute("SELECT COUNT(*) FROM estudios").fetchone()[0],
        "total_empresas":   db.execute("SELECT COUNT(*) FROM empresas WHERE activa=1").fetchone()[0],
        "total_ejercicios": db.execute("SELECT COUNT(*) FROM ejercicios").fetchone()[0],
        "balances_emitidos":db.execute("SELECT COUNT(*) FROM balances_emitidos").fetchone()[0],
        "ingresos_total":   db.execute("SELECT COALESCE(SUM(monto),0) FROM transacciones WHERE tipo='compra_creditos' AND estado='aprobado'").fetchone()[0],
        "creditos_vendidos":db.execute("SELECT COALESCE(SUM(creditos),0) FROM transacciones WHERE tipo='compra_creditos' AND estado='aprobado'").fetchone()[0],
        "nuevos_hoy":       db.execute("SELECT COUNT(*) FROM usuarios WHERE date(created_at)=date('now')").fetchone()[0],
    }
    db.close()
    return s

@app.put("/admin/usuarios/{uid}/creditos", tags=["Admin"])
def admin_set_creditos(uid: int, data: dict, user: dict = Depends(get_current_user)):
    if not is_creator(user):
        raise HTTPException(403, "Solo el creador")
    cantidad = int(data.get("creditos", 0))
    db = get_db()
    db.execute("UPDATE usuarios SET creditos=? WHERE id=?", (cantidad, uid))
    db.commit()
    db.close()
    return {"ok": True, "creditos": cantidad}

@app.put("/admin/usuarios/{uid}/plan", tags=["Admin"])
def admin_set_plan(uid: int, data: dict, user: dict = Depends(get_current_user)):
    if not is_creator(user):
        raise HTTPException(403, "Solo el creador")
    plan = data.get("plan", "free")
    db = get_db()
    db.execute("UPDATE usuarios SET plan=? WHERE id=?", (plan, uid))
    db.commit()
    db.close()
    return {"ok": True, "plan": plan}

@app.delete("/admin/usuarios/{uid}", tags=["Admin"])
def admin_del_usuario(uid: int, user: dict = Depends(get_current_user)):
    if not is_creator(user):
        raise HTTPException(403, "Solo el creador")
    db = get_db()
    db.execute("UPDATE usuarios SET activo=0 WHERE id=?", (uid,))
    db.commit()
    db.close()
    return {"ok": True}

# ══════════════════════════════════════════════════════════════════
# PLAN DE CUENTAS
# ══════════════════════════════════════════════════════════════════

@app.get("/plan-cuentas/{tipo}", tags=["Archivos"])
def plan_cuentas(tipo: str = "comercial"):
    plan = PLANES.get(tipo, PLANES["comercial"])
    return {"tipo": tipo, "cuentas": [{"codigo": c, "descripcion": d} for c, d in plan]}
