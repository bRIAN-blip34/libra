"""
LIBRA — Motor Contable RT 54
Motor de procesamiento contable argentino.
Implementa: clasificación RT54, ajuste por inflación AxI,
RECPAM, comparativo, validación y exportación a Excel/PDF.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import date
import math

# ─── Índices IPC FACPCE (base histórica)
# Fuente: FACPCE — índice de precios internos al por mayor (IPIM) / IPC INDEC
# Formato: {(año, mes): índice_acumulado_desde_base_2016}
IPC_FACPCE: dict[tuple[int,int], float] = {
    # 2021
    (2021,1):3.621,(2021,2):3.705,(2021,3):3.822,(2021,4):3.934,(2021,5):4.009,
    (2021,6):4.089,(2021,7):4.168,(2021,8):4.269,(2021,9):4.383,(2021,10):4.503,
    (2021,11):4.622,(2021,12):4.764,
    # 2022
    (2022,1):4.984,(2022,2):5.192,(2022,3):5.478,(2022,4):5.742,(2022,5):6.007,
    (2022,6):6.323,(2022,7):6.702,(2022,8):7.162,(2022,9):7.637,(2022,10):8.096,
    (2022,11):8.541,(2022,12):9.038,
    # 2023
    (2023,1):9.688,(2023,2):10.430,(2023,3):11.222,(2023,4):12.150,(2023,5):13.147,
    (2023,6):14.240,(2023,7):15.474,(2023,8):17.050,(2023,9):19.480,(2023,10):22.210,
    (2023,11):24.770,(2023,12):29.480,
    # 2024
    (2024,1):40.120,(2024,2):50.340,(2024,3):58.910,(2024,4):65.800,(2024,5):71.200,
    (2024,6):77.450,(2024,7):82.300,(2024,8):87.600,(2024,9):92.400,(2024,10):96.800,
    (2024,11):101.200,(2024,12):105.800,
    # 2025
    (2025,1):110.400,(2025,2):114.800,(2025,3):119.200,(2025,4):123.600,(2025,5):127.800,
    (2025,6):131.900,(2025,7):135.600,(2025,8):139.100,(2025,9):142.400,(2025,10):145.600,
    (2025,11):148.700,(2025,12):151.800,
}

def get_ipc(año: int, mes: int) -> float:
    """Devuelve el índice IPC para un período dado. Interpola si no existe."""
    key = (año, mes)
    if key in IPC_FACPCE:
        return IPC_FACPCE[key]
    # Buscar el más cercano
    keys = sorted(IPC_FACPCE.keys())
    for k in reversed(keys):
        if k <= key:
            return IPC_FACPCE[k]
    return IPC_FACPCE[keys[0]]

def coeficiente_actualizacion(fecha_origen: date, fecha_cierre: date) -> float:
    """
    Calcula el coeficiente de actualización para reexpresar valores.
    Coef = IPC_cierre / IPC_origen
    """
    ipc_origen = get_ipc(fecha_origen.year, fecha_origen.month)
    ipc_cierre = get_ipc(fecha_cierre.year, fecha_cierre.month)
    if ipc_origen == 0:
        return 1.0
    return ipc_cierre / ipc_origen

def variacion_ipc_ejercicio(fecha_inicio: date, fecha_cierre: date) -> float:
    """Variación del IPC en el período del ejercicio (%)."""
    ipc_inicio = get_ipc(fecha_inicio.year, fecha_inicio.month)
    ipc_cierre = get_ipc(fecha_cierre.year, fecha_cierre.month)
    if ipc_inicio == 0:
        return 0.0
    return ((ipc_cierre / ipc_inicio) - 1) * 100


# ─── Estructuras de datos ─────────────────────────────────────────

@dataclass
class Cuenta:
    codigo: str
    descripcion: str
    debe: float
    haber: float
    saldo: float
    # Campos enriquecidos
    tipo: str = ""          # A, P, PN, R
    rubro: str = ""         # corriente, no_corriente, etc.
    subrubro: str = ""
    saldo_reexpresado: float = 0.0
    coef_aplicado: float = 1.0
    fecha_incorporacion: Optional[date] = None

@dataclass
class Ejercicio:
    numero: int
    fecha_inicio: date
    fecha_cierre: date
    cuentas: list[Cuenta] = field(default_factory=list)
    moneda_homogenea: bool = True

@dataclass
class Empresa:
    razon_social: str
    cuit: str
    tipo: str               # S.A., S.R.L., etc.
    actividad: str
    domicilio: str
    capital_suscripto: float
    fecha_inscripcion: Optional[date] = None
    fecha_estatuto: Optional[date] = None
    consejo_profesional: str = "CPCE Buenos Aires"
    nro_inscripcion: str = ""
    duracion_anos: int = 99

@dataclass
class ResultadoBalance:
    # ESP
    activo_corriente: float = 0.0
    activo_no_corriente: float = 0.0
    total_activo: float = 0.0
    pasivo_corriente: float = 0.0
    pasivo_no_corriente: float = 0.0
    total_pasivo: float = 0.0
    patrimonio_neto: float = 0.0
    resultado_ejercicio: float = 0.0
    total_pn_con_resultado: float = 0.0
    # Estado de Resultados
    total_ingresos: float = 0.0
    total_gastos: float = 0.0
    # Inflación
    variacion_ipc: float = 0.0
    recpam: float = 0.0
    # Validación
    cuadra: bool = False
    diferencia: float = 0.0
    # Clasificación RT54
    clasificacion_rt54: str = ""  # EP, EM, RE
    es_agropecuaria: bool = False
    # Indicadores
    margen_neto: float = 0.0
    roa: float = 0.0
    liquidez_corriente: float = 0.0
    solvencia: float = 0.0
    endeudamiento: float = 0.0


# ─── Mapa de cuentas RT54 ─────────────────────────────────────────

PLAN_CUENTAS_RT54 = {
    # Activo Corriente
    "1.1.1": {"rubro":"corriente","subrubro":"Caja y bancos","naturaleza":"deudora"},
    "1.1.2": {"rubro":"corriente","subrubro":"Inversiones financieras","naturaleza":"deudora"},
    "1.1.3": {"rubro":"corriente","subrubro":"Créditos impositivos","naturaleza":"deudora"},
    "1.1.4": {"rubro":"corriente","subrubro":"Bienes de cambio","naturaleza":"deudora"},
    "1.1.5": {"rubro":"corriente","subrubro":"Bienes de cambio","naturaleza":"deudora"},
    "1.1.6": {"rubro":"corriente","subrubro":"Bienes de cambio","naturaleza":"deudora"},
    "1.1.7": {"rubro":"corriente","subrubro":"Otros créditos","naturaleza":"deudora"},
    "1.1.8": {"rubro":"corriente","subrubro":"Créditos por ventas","naturaleza":"deudora"},
    "1.1.9": {"rubro":"corriente","subrubro":"Créditos impositivos","naturaleza":"deudora"},
    # Activo No Corriente
    "1.2.1": {"rubro":"no_corriente","subrubro":"Bienes de uso","naturaleza":"deudora"},
    "1.2.2": {"rubro":"no_corriente","subrubro":"Bienes de uso (amortización)","naturaleza":"acreedora"},
    "1.2.3": {"rubro":"no_corriente","subrubro":"Activos intangibles","naturaleza":"deudora"},
    "1.2.4": {"rubro":"no_corriente","subrubro":"Activos intangibles","naturaleza":"deudora"},
    "1.2.5": {"rubro":"no_corriente","subrubro":"Activos intangibles (amortización)","naturaleza":"acreedora"},
    # Pasivo Corriente
    "2.1.1": {"rubro":"corriente","subrubro":"Proveedores de bienes y servicios","naturaleza":"acreedora"},
    "2.1.2": {"rubro":"corriente","subrubro":"Proveedores de bienes y servicios","naturaleza":"acreedora"},
    "2.1.3": {"rubro":"corriente","subrubro":"Deudas fiscales","naturaleza":"acreedora"},
    "2.1.4": {"rubro":"corriente","subrubro":"Deudas fiscales","naturaleza":"acreedora"},
    "2.1.5": {"rubro":"corriente","subrubro":"Deudas fiscales","naturaleza":"acreedora"},
    "2.1.6": {"rubro":"corriente","subrubro":"Deudas fiscales","naturaleza":"acreedora"},
    "2.1.7": {"rubro":"corriente","subrubro":"Deudas con partes relacionadas","naturaleza":"acreedora"},
    # Pasivo No Corriente
    "2.2.1": {"rubro":"no_corriente","subrubro":"Préstamos bancarios","naturaleza":"acreedora"},
    "2.2.2": {"rubro":"no_corriente","subrubro":"Deudas financieras","naturaleza":"acreedora"},
    # Patrimonio Neto
    "3.1.1": {"rubro":"aportes_propietarios","subrubro":"Capital suscripto","naturaleza":"acreedora"},
    "3.1.2": {"rubro":"aportes_propietarios","subrubro":"Ajuste del capital","naturaleza":"acreedora"},
    "3.1.3": {"rubro":"resultados_acumulados","subrubro":"Resultados no asignados","naturaleza":"acreedora"},
    "3.1.4": {"rubro":"resultados_acumulados","subrubro":"Resultados no asignados","naturaleza":"acreedora"},
    "3.1.5": {"rubro":"reservas","subrubro":"Reserva legal","naturaleza":"acreedora"},
    # Ingresos
    "4.1.1": {"rubro":"ingresos","subrubro":"Ingresos netos por venta de bienes o prestación de servicios","naturaleza":"acreedora"},
    "4.1.2": {"rubro":"ingresos","subrubro":"Ingresos netos por venta de bienes o prestación de servicios","naturaleza":"acreedora"},
    "4.1.3": {"rubro":"ingresos","subrubro":"Resultados financieros y por tenencia (incluyendo el RECPAM)","naturaleza":"acreedora"},
    # Gastos
    "4.2.1": {"rubro":"gastos","subrubro":"Costo de los bienes vendidos y servicios prestados","naturaleza":"deudora"},
    "4.2.2": {"rubro":"gastos","subrubro":"Ingresos brutos","naturaleza":"deudora"},
    "4.2.3": {"rubro":"gastos","subrubro":"Amortización de activos intangibles","naturaleza":"deudora"},
    "4.2.4": {"rubro":"gastos","subrubro":"Depreciación bienes de uso","naturaleza":"deudora"},
    "4.2.5": {"rubro":"gastos","subrubro":"Servicios bancarios","naturaleza":"deudora"},
    "4.2.6": {"rubro":"gastos","subrubro":"Honorarios de directores o socio gerente","naturaleza":"deudora"},
    "4.2.7": {"rubro":"gastos","subrubro":"Honorarios profesionales","naturaleza":"deudora"},
    "4.2.8": {"rubro":"gastos","subrubro":"Resultados financieros y por tenencia (incluyendo el RECPAM)","naturaleza":"deudora"},
    "4.2.9": {"rubro":"gastos","subrubro":"Impuesto a las ganancias","naturaleza":"deudora"},
}

def enriquecer_cuenta(cuenta: Cuenta) -> Cuenta:
    """Agrega tipo, rubro y subrubro a una cuenta según su código."""
    p = cuenta.codigo.split(".")
    prefix_3 = ".".join(p[:3]) if len(p) >= 3 else cuenta.codigo

    meta = PLAN_CUENTAS_RT54.get(prefix_3, {})
    cuenta.rubro = meta.get("rubro", "")
    cuenta.subrubro = meta.get("subrubro", "")

    primer_digito = cuenta.codigo[0] if cuenta.codigo else ""
    cuenta.tipo = {"1":"A","2":"P","3":"PN","4":"R"}.get(primer_digito, "?")
    return cuenta


# ─── Motor principal ──────────────────────────────────────────────

class MotorContable:

    def __init__(self, ejercicio: Ejercicio):
        self.ejercicio = ejercicio
        self.cuentas = [enriquecer_cuenta(c) for c in ejercicio.cuentas]

    # ── Filtros ───────────────────────────────────────────────────
    def _get(self, prefijo: str) -> list[Cuenta]:
        return [c for c in self.cuentas if c.codigo.startswith(prefijo)]

    def _sum_saldo(self, cuentas: list[Cuenta]) -> float:
        return sum(c.saldo for c in cuentas)

    # ── Clasificación RT54 ────────────────────────────────────────
    def clasificar_rt54(self, ingresos_anuales: float, es_agropecuaria: bool = False) -> str:
        """
        RT 54 — Clasificación de entes:
        EP (Entidad Pequeña): ingresos ≤ umbral EP
        EM (Entidad Mediana): umbral EP < ingresos ≤ umbral EM
        RE (Restante Entidad): ingresos > umbral EM o condiciones especiales

        Umbrales 2025 (FACPCE, actualizados):
        EP: hasta $3.500.000.000 en ventas anuales
        EM: hasta $12.000.000.000
        RE: más de $12.000.000.000
        """
        UMBRAL_EP = 3_500_000_000
        UMBRAL_EM = 12_000_000_000

        if ingresos_anuales <= UMBRAL_EP:
            return "EP"
        elif ingresos_anuales <= UMBRAL_EM:
            return "EM"
        else:
            return "RE"

    # ── Ajuste por inflación (AxI) ─────────────────────────────────
    def calcular_axi(self, fecha_origen: Optional[date] = None) -> list[Cuenta]:
        """
        Reexpresa cada cuenta aplicando el coeficiente de actualización.
        Para cuentas monetarias (caja, bancos, créditos, deudas): no se ajustan.
        Para cuentas no monetarias (bienes de cambio, uso, capital): sí se ajustan.
        """
        fecha_cierre = self.ejercicio.fecha_cierre
        # Cuentas monetarias: NO se ajustan (ya están en moneda actual)
        MONETARIAS = {"1.1.1","1.1.2","1.1.3","1.1.7","1.1.8","1.1.9",
                      "2.1.1","2.1.2","2.1.3","2.1.4","2.1.5","2.1.6","2.1.7",
                      "2.2.1","2.2.2"}

        for cuenta in self.cuentas:
            prefix_3 = ".".join(cuenta.codigo.split(".")[:3])
            es_monetaria = prefix_3 in MONETARIAS

            if es_monetaria:
                cuenta.saldo_reexpresado = cuenta.saldo
                cuenta.coef_aplicado = 1.0
            else:
                # Usar fecha de origen de la cuenta o inicio del ejercicio
                f_origen = fecha_origen or self.ejercicio.fecha_inicio
                coef = coeficiente_actualizacion(f_origen, fecha_cierre)
                cuenta.saldo_reexpresado = cuenta.saldo * coef
                cuenta.coef_aplicado = coef

        return self.cuentas

    # ── RECPAM ────────────────────────────────────────────────────
    def calcular_recpam(self) -> float:
        """
        RECPAM = Resultado por Exposición a Cambios en el Poder Adquisitivo de la Moneda.
        RECPAM = - (PN_promedio_monetario × variación_IPC_del_período)
        Simplificado: diferencia entre activos y pasivos monetarios × variación IPC.
        """
        fecha_inicio = self.ejercicio.fecha_inicio
        fecha_cierre = self.ejercicio.fecha_cierre

        ipc_inicio = get_ipc(fecha_inicio.year, fecha_inicio.month)
        ipc_cierre = get_ipc(fecha_cierre.year, fecha_cierre.month)
        variacion = (ipc_cierre - ipc_inicio) / ipc_inicio if ipc_inicio else 0

        # Activos monetarios (expuestos)
        monetarios_activo = sum(
            c.saldo for c in self.cuentas
            if c.codigo.startswith("1.1.1") or c.codigo.startswith("1.1.2")
            or c.codigo.startswith("1.1.7") or c.codigo.startswith("1.1.8")
        )
        # Pasivos monetarios (expuestos)
        monetarios_pasivo = abs(sum(
            c.saldo for c in self.cuentas
            if c.codigo.startswith("2.")
        ))

        posicion_monetaria_neta = monetarios_activo - monetarios_pasivo
        recpam = -(posicion_monetaria_neta * variacion)
        return round(recpam, 2)

    # ── Cálculo del balance ───────────────────────────────────────
    def calcular(self, es_agropecuaria: bool = False) -> ResultadoBalance:
        r = ResultadoBalance()

        # Activo
        act_cte  = self._get("1.1")
        act_ncte = self._get("1.2")
        r.activo_corriente    = self._sum_saldo(act_cte)
        r.activo_no_corriente = self._sum_saldo(act_ncte)
        r.total_activo        = r.activo_corriente + r.activo_no_corriente

        # Pasivo
        pas_cte  = self._get("2.1")
        pas_ncte = self._get("2.2")
        r.pasivo_corriente    = abs(self._sum_saldo(pas_cte))
        r.pasivo_no_corriente = abs(self._sum_saldo(pas_ncte))
        r.total_pasivo        = r.pasivo_corriente + r.pasivo_no_corriente

        # Patrimonio Neto (sin resultado)
        pn_cuentas = self._get("3.")
        r.patrimonio_neto = abs(self._sum_saldo(pn_cuentas))

        # Resultado
        ingresos = self._get("4.1")
        gastos   = self._get("4.2")
        r.total_ingresos     = abs(self._sum_saldo(ingresos))
        r.total_gastos       = self._sum_saldo(gastos)
        r.resultado_ejercicio = r.total_ingresos - r.total_gastos
        r.total_pn_con_resultado = r.patrimonio_neto + r.resultado_ejercicio

        # Inflación
        r.variacion_ipc = variacion_ipc_ejercicio(
            self.ejercicio.fecha_inicio,
            self.ejercicio.fecha_cierre
        )
        r.recpam = self.calcular_recpam()

        # Validación partida doble
        lado_deudor   = r.total_activo
        lado_acreedor = r.total_pasivo + r.total_pn_con_resultado
        r.diferencia  = abs(lado_deudor - lado_acreedor)
        r.cuadra      = r.diferencia < 1.0   # tolerancia $1

        # Clasificación RT54
        r.clasificacion_rt54 = self.clasificar_rt54(r.total_ingresos, es_agropecuaria)
        r.es_agropecuaria = es_agropecuaria

        # Indicadores
        if r.total_ingresos:
            r.margen_neto = (r.resultado_ejercicio / r.total_ingresos) * 100
        if r.total_activo:
            r.roa = (r.resultado_ejercicio / r.total_activo) * 100
        if r.pasivo_corriente:
            r.liquidez_corriente = r.activo_corriente / r.pasivo_corriente
        if r.total_pasivo:
            r.solvencia = r.total_activo / r.total_pasivo
            r.endeudamiento = r.total_pasivo / r.total_pn_con_resultado if r.total_pn_con_resultado else 0

        return r

    # ── Validación de saldos ─────────────────────────────────────
    def validar_saldos(self) -> list[dict]:
        """
        Valida errores contables en los saldos cargados.
        Retorna lista de errores y advertencias.
        """
        errores = []
        r = self.calcular()

        # 1. Partida doble
        if not r.cuadra:
            errores.append({
                "tipo": "error",
                "codigo": "PARTIDA_DOBLE",
                "mensaje": f"El balance no cuadra. Diferencia: ${r.diferencia:,.2f}",
                "cuenta": None
            })

        # 2. Cuentas con saldo contrario a su naturaleza
        for cuenta in self.cuentas:
            prefix_3 = ".".join(cuenta.codigo.split(".")[:3])
            meta = PLAN_CUENTAS_RT54.get(prefix_3, {})
            naturaleza = meta.get("naturaleza", "")
            if naturaleza == "deudora" and cuenta.saldo < -1:
                errores.append({
                    "tipo": "advertencia",
                    "codigo": "SALDO_CONTRARIO",
                    "mensaje": f"Cuenta deudora con saldo acreedor",
                    "cuenta": cuenta.codigo,
                    "descripcion": cuenta.descripcion
                })
            elif naturaleza == "acreedora" and cuenta.saldo > 1:
                errores.append({
                    "tipo": "advertencia",
                    "codigo": "SALDO_CONTRARIO",
                    "mensaje": f"Cuenta acreedora con saldo deudor",
                    "cuenta": cuenta.codigo,
                    "descripcion": cuenta.descripcion
                })

        # 3. Sin cuentas de resultado
        if not self._get("4."):
            errores.append({
                "tipo": "advertencia",
                "codigo": "SIN_RESULTADOS",
                "mensaje": "No hay cuentas de resultado cargadas (rubro 4.x.x)",
                "cuenta": None
            })

        # 4. Activo > 0 pero sin caja/banco
        if r.total_activo > 0 and not self._get("1.1.1"):
            errores.append({
                "tipo": "info",
                "codigo": "SIN_DISPONIBILIDADES",
                "mensaje": "No hay cuentas de disponibilidades (1.1.1.x)",
                "cuenta": None
            })

        # 5. Verificar que debe - haber = saldo
        for c in self.cuentas:
            expected = c.debe - c.haber
            if abs(expected - c.saldo) > 1:
                errores.append({
                    "tipo": "error",
                    "codigo": "SALDO_INCONSISTENTE",
                    "mensaje": f"Debe ({c.debe:,.2f}) - Haber ({c.haber:,.2f}) ≠ Saldo ({c.saldo:,.2f})",
                    "cuenta": c.codigo,
                    "descripcion": c.descripcion
                })

        return errores

    # ── Comparativo entre dos ejercicios ─────────────────────────
    def comparar_con(self, otro: "MotorContable") -> dict:
        """Genera análisis comparativo entre dos ejercicios."""
        r_actual    = self.calcular()
        r_anterior  = otro.calcular()

        def variacion(actual, anterior):
            if anterior == 0:
                return None
            return ((actual - anterior) / abs(anterior)) * 100

        return {
            "ejercicio_actual":   self.ejercicio.numero,
            "ejercicio_anterior": otro.ejercicio.numero,
            "activo": {
                "actual": r_actual.total_activo,
                "anterior": r_anterior.total_activo,
                "variacion_pct": variacion(r_actual.total_activo, r_anterior.total_activo)
            },
            "pasivo": {
                "actual": r_actual.total_pasivo,
                "anterior": r_anterior.total_pasivo,
                "variacion_pct": variacion(r_actual.total_pasivo, r_anterior.total_pasivo)
            },
            "pn": {
                "actual": r_actual.total_pn_con_resultado,
                "anterior": r_anterior.total_pn_con_resultado,
                "variacion_pct": variacion(r_actual.total_pn_con_resultado, r_anterior.total_pn_con_resultado)
            },
            "resultado": {
                "actual": r_actual.resultado_ejercicio,
                "anterior": r_anterior.resultado_ejercicio,
                "variacion_pct": variacion(r_actual.resultado_ejercicio, r_anterior.resultado_ejercicio)
            },
            "ingresos": {
                "actual": r_actual.total_ingresos,
                "anterior": r_anterior.total_ingresos,
                "variacion_pct": variacion(r_actual.total_ingresos, r_anterior.total_ingresos)
            },
            "margen_neto": {
                "actual": r_actual.margen_neto,
                "anterior": r_anterior.margen_neto,
            },
            "cuentas_comparadas": self._comparar_cuentas(otro)
        }

    def _comparar_cuentas(self, otro: "MotorContable") -> list[dict]:
        mapa_otro = {c.codigo: c for c in otro.cuentas}
        resultado = []
        for c in self.cuentas:
            ant = mapa_otro.get(c.codigo)
            resultado.append({
                "codigo": c.codigo,
                "descripcion": c.descripcion,
                "tipo": c.tipo,
                "rubro": c.rubro,
                "subrubro": c.subrubro,
                "debe_actual": c.debe,
                "haber_actual": c.haber,
                "saldo_actual": c.saldo,
                "debe_anterior": ant.debe if ant else 0,
                "haber_anterior": ant.haber if ant else 0,
                "saldo_anterior": ant.saldo if ant else 0,
            })
        return resultado


# ─── Importador Excel ─────────────────────────────────────────────

def importar_excel(path: str) -> list[Cuenta]:
    """
    Lee un archivo Excel con formato LIBRA y devuelve lista de Cuenta.
    Columnas esperadas: Código, Descripción, Debe, Haber, Saldo (opcional)
    """
    import openpyxl
    wb = openpyxl.load_workbook(path)
    ws = wb.active

    headers = {}
    cuentas = []

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            for j, cell in enumerate(row):
                if cell:
                    headers[str(cell).strip().lower()] = j
            continue

        def get(names):
            for n in names:
                if n in headers and row[headers[n]] is not None:
                    return row[headers[n]]
            return None

        codigo = get(["código","codigo","code"])
        desc   = get(["descripción","descripcion","description","nombre"])
        debe   = get(["debe","debit"])
        haber  = get(["haber","credit"])
        saldo  = get(["saldo","balance"])

        if not codigo:
            continue

        debe_v  = float(debe or 0)
        haber_v = float(haber or 0)
        saldo_v = float(saldo) if saldo is not None else (debe_v - haber_v)

        cuentas.append(Cuenta(
            codigo=str(codigo).strip(),
            descripcion=str(desc or "").strip(),
            debe=debe_v,
            haber=haber_v,
            saldo=saldo_v,
        ))

    return cuentas


def exportar_excel(cuentas: list[Cuenta], resultado: ResultadoBalance, path: str):
    """Exporta saldos enriquecidos a Excel con formato LIBRA."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sumas y Saldos"

    # Estilos
    GOLD   = "C9A96E"
    DARK   = "0D1220"
    HEADER = Font(bold=True, color="FFFFFF", size=10)
    FILL_H = PatternFill("solid", fgColor="1A2840")
    FILL_A = PatternFill("solid", fgColor="34D39A22"[:-2])
    BORDER = Border(
        bottom=Side(style="thin", color="1A2840"),
    )

    # Fila de totales arriba
    ws.append(["LIBRA — Sumas y Saldos Enriquecidos"])
    ws.append([f"Activo: {resultado.total_activo:,.2f}",
               f"Pasivo: {resultado.total_pasivo:,.2f}",
               f"PN: {resultado.total_pn_con_resultado:,.2f}",
               f"Resultado: {resultado.resultado_ejercicio:,.2f}",
               f"Clasificación RT54: {resultado.clasificacion_rt54}",
               f"IPC ejercicio: {resultado.variacion_ipc:.1f}%"])
    ws.append([])  # fila vacía

    # Headers
    headers = ["Código","Descripción","Tipo","Rubro","Subrubro","Debe","Haber","Saldo","Saldo Reexpresado","Coef. AxI"]
    ws.append(headers)
    for col, _ in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col)
        cell.font = HEADER
        cell.fill = FILL_H
        cell.alignment = Alignment(horizontal="center")

    # Datos
    tipo_labels = {"A":"Activo","P":"Pasivo","PN":"Pat. Neto","R":"Resultado"}
    for c in cuentas:
        ws.append([
            c.codigo,
            c.descripcion,
            tipo_labels.get(c.tipo, c.tipo),
            c.rubro,
            c.subrubro,
            c.debe,
            c.haber,
            c.saldo,
            c.saldo_reexpresado or c.saldo,
            c.coef_aplicado or 1.0,
        ])

    # Ancho columnas
    anchos = [15, 45, 12, 18, 50, 18, 18, 18, 22, 12]
    for i, ancho in enumerate(anchos, 1):
        ws.column_dimensions[get_column_letter(i)].width = ancho

    # Hoja indicadores
    ws2 = wb.create_sheet("Indicadores")
    ws2.append(["Indicador", "Valor"])
    for label, value in [
        ("Margen neto (%)", f"{resultado.margen_neto:.2f}%"),
        ("ROA (%)", f"{resultado.roa:.2f}%"),
        ("Liquidez corriente", f"{resultado.liquidez_corriente:.2f}x"),
        ("Solvencia", f"{resultado.solvencia:.2f}x"),
        ("Endeudamiento", f"{resultado.endeudamiento:.2f}x"),
        ("Variación IPC ejercicio (%)", f"{resultado.variacion_ipc:.2f}%"),
        ("RECPAM estimado", f"{resultado.recpam:,.2f}"),
        ("Clasificación RT54", resultado.clasificacion_rt54),
        ("Balance cuadra", "Sí" if resultado.cuadra else f"NO (Dif: {resultado.diferencia:,.2f})"),
    ]:
        ws2.append([label, value])

    wb.save(path)
    return path


# ─── Generador PDF (ReportLab) ────────────────────────────────────

def generar_pdf_balance(empresa: Empresa, ejercicio: Ejercicio,
                        resultado: ResultadoBalance, cuentas: list[Cuenta],
                        firmantes: list[dict], path: str,
                        incluir_notas: bool = True) -> str:
    """
    Genera el PDF completo del balance con ReportLab.
    Incluye: carátula, ESP, EdeR, notas, anexos, firma del auditor.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, HRFlowable, PageBreak, KeepTogether)
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.pdfgen import canvas as pdfcanvas

    # Colores LIBRA
    GOLD   = colors.HexColor("#C9A96E")
    DARK   = colors.HexColor("#070A14")
    SURFACE= colors.HexColor("#0D1220")
    BLUE   = colors.HexColor("#60A5FA")
    GREEN  = colors.HexColor("#34D39A")
    RED    = colors.HexColor("#F87171")
    MUTED  = colors.HexColor("#6B82A8")
    LIGHT  = colors.HexColor("#EDE8DE")

    # Estilos
    styles = getSampleStyleSheet()
    s_titulo  = ParagraphStyle("titulo",  parent=styles["Title"],    fontSize=18, textColor=GOLD,  alignment=TA_CENTER, spaceAfter=4)
    s_subtit  = ParagraphStyle("subtit",  parent=styles["Normal"],   fontSize=10, textColor=MUTED, alignment=TA_CENTER, spaceAfter=12)
    s_h1      = ParagraphStyle("h1",      parent=styles["Heading1"], fontSize=13, textColor=GOLD,  spaceBefore=16, spaceAfter=6)
    s_h2      = ParagraphStyle("h2",      parent=styles["Heading2"], fontSize=10, textColor=MUTED, spaceBefore=10, spaceAfter=4, textTransform="uppercase")
    s_body    = ParagraphStyle("body",    parent=styles["Normal"],   fontSize=9,  textColor=colors.black, leading=14, spaceAfter=4)
    s_nota    = ParagraphStyle("nota",    parent=styles["Normal"],   fontSize=8,  textColor=colors.HexColor("#555555"), leading=13, spaceAfter=8)
    s_right   = ParagraphStyle("right",   parent=styles["Normal"],   fontSize=9,  alignment=TA_RIGHT)
    s_label   = ParagraphStyle("label",   parent=styles["Normal"],   fontSize=8,  textColor=MUTED)

    fmt_n = lambda n: f"$ {abs(n):>18,.2f}".replace(",","X").replace(".",",").replace("X",".")

    # Doc
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        rightMargin=1.8*cm, leftMargin=1.8*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    story = []

    def hr(color=GOLD, thickness=1):
        return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=8, spaceBefore=4)

    def tabla_linea(datos, col_widths=None):
        """Tabla estilo contable (sin bordes, líneas horizontales)."""
        t = Table(datos, colWidths=col_widths or [10*cm, 4*cm])
        t.setStyle(TableStyle([
            ("FONTSIZE",   (0,0), (-1,-1), 9),
            ("TEXTCOLOR",  (0,0), (0,-1), colors.HexColor("#333333")),
            ("TEXTCOLOR",  (1,0), (1,-1), colors.black),
            ("ALIGN",      (1,0), (-1,-1), "RIGHT"),
            ("LINEBELOW",  (0,0), (-1,-2), 0.3, colors.HexColor("#DDDDDD")),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("TOPPADDING", (0,0),(-1,-1), 4),
        ]))
        return t

    # ══════ CARÁTULA ══════════════════════════════════════════════
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("ESTADOS CONTABLES", s_titulo))
    story.append(Paragraph(
        f"Al {ejercicio.fecha_cierre.strftime('%d/%m/%Y')} — Moneda homogénea", s_subtit
    ))
    story.append(hr())
    story.append(Spacer(1, 0.5*cm))

    # Datos empresa
    datos_caratula = [
        ["Denominación del Ente", empresa.razon_social],
        ["CUIT N°", empresa.cuit],
        ["Domicilio legal", empresa.domicilio],
        ["Actividad principal", empresa.actividad],
        ["Tipo de entidad", empresa.tipo],
        ["Consejo Profesional", empresa.consejo_profesional],
        ["N° Inscripción", empresa.nro_inscripcion],
        ["Fecha de Inscripción", empresa.fecha_inscripcion.strftime("%d/%m/%Y") if empresa.fecha_inscripcion else "—"],
        ["Fecha de Estatuto", empresa.fecha_estatuto.strftime("%d/%m/%Y") if empresa.fecha_estatuto else "—"],
        ["Duración", f"{empresa.duracion_anos} años"],
        ["Ejercicio N°", str(ejercicio.numero)],
        ["Período", f"{ejercicio.fecha_inicio.strftime('%d/%m/%Y')} – {ejercicio.fecha_cierre.strftime('%d/%m/%Y')}"],
        ["Unidad de medida", "Moneda homogénea"],
        ["Clasificación RT 54", "Entidad " + resultado.clasificacion_rt54 + " (" + {"EP":"Pequeña","EM":"Mediana","RE":"Restante"}.get(resultado.clasificacion_rt54,"") + ")"],
    ]
    t_car = Table(datos_caratula, colWidths=[5*cm, 11*cm])
    t_car.setStyle(TableStyle([
        ("FONTSIZE",  (0,0),(-1,-1), 9),
        ("TEXTCOLOR", (0,0),(0,-1), MUTED),
        ("FONTNAME",  (0,0),(0,-1), "Helvetica"),
        ("FONTNAME",  (1,0),(1,-1), "Helvetica-Bold"),
        ("LINEBELOW", (0,0),(-1,-2), 0.3, colors.HexColor("#EEEEEE")),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("TOPPADDING",(0,0),(-1,-1), 5),
    ]))
    story.append(t_car)
    story.append(Spacer(1, 0.5*cm))

    # Composición del capital
    story.append(Paragraph("Composición del Capital", s_h2))
    t_cap = Table(
        [["Tipo","Cantidad","Clase","V. Nominal","Cap. Suscripto","Cap. Integrado"],
         ["En circulación",
          f"{empresa.capital_suscripto:,.0f}".replace(",","."),
          "Ordinarias","$ 1,00",
          fmt_n(empresa.capital_suscripto),
          fmt_n(empresa.capital_suscripto)]],
        colWidths=[3.5*cm,2.5*cm,2.5*cm,2*cm,3*cm,3*cm]
    )
    t_cap.setStyle(TableStyle([
        ("FONTSIZE",  (0,0),(-1,-1), 8),
        ("BACKGROUND",(0,0),(-1,0), colors.HexColor("#F0F0F0")),
        ("FONTNAME",  (0,0),(-1,0), "Helvetica-Bold"),
        ("ALIGN",     (2,0),(-1,-1), "RIGHT"),
        ("GRID",      (0,0),(-1,-1), 0.3, colors.HexColor("#CCCCCC")),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("TOPPADDING",(0,0),(-1,-1), 5),
    ]))
    story.append(t_cap)
    story.append(PageBreak())

    # ══════ ESTADO DE SITUACIÓN PATRIMONIAL ═══════════════════════
    story.append(Paragraph("Estado de Situación Patrimonial", s_h1))
    story.append(Paragraph(
        f"Al {ejercicio.fecha_cierre.strftime('%d/%m/%Y')} — Comparativo · Moneda homogénea (Nota 1.3)", s_subtit
    ))
    story.append(hr())

    def seccion_esp(cuentas_filtradas, titulo_sub, total_label, total_valor):
        items = [[f"  {c.descripcion}", fmt_n(abs(c.saldo))] for c in cuentas_filtradas]
        items.append([total_label, fmt_n(total_valor)])
        t = tabla_linea(items)
        return [Paragraph(titulo_sub, s_h2), t, Spacer(1,0.3*cm)]

    # Activo
    story.append(Paragraph("ACTIVO", ParagraphStyle("sec", parent=s_h2, textColor=BLUE, fontSize=10)))
    story += seccion_esp([c for c in cuentas if c.codigo.startswith("1.1")],
                         "Activo Corriente", "Total Activo Corriente",resultado.activo_corriente)
    story += seccion_esp([c for c in cuentas if c.codigo.startswith("1.2")],
                         "Activo No Corriente", "Total Activo No Corriente", resultado.activo_no_corriente)
    story.append(tabla_linea([["TOTAL ACTIVO", fmt_n(resultado.total_activo)]]))

    story.append(Spacer(1, 0.6*cm))
    # Pasivo
    story.append(Paragraph("PASIVO", ParagraphStyle("sec2", parent=s_h2, textColor=RED, fontSize=10)))
    story += seccion_esp([c for c in cuentas if c.codigo.startswith("2.1")],
                         "Pasivo Corriente", "Total Pasivo Corriente", resultado.pasivo_corriente)
    story += seccion_esp([c for c in cuentas if c.codigo.startswith("2.2")],
                         "Pasivo No Corriente", "Total Pasivo No Corriente", resultado.pasivo_no_corriente)
    story.append(tabla_linea([["TOTAL PASIVO", fmt_n(resultado.total_pasivo)]]))

    story.append(Spacer(1, 0.6*cm))
    # PN
    story.append(Paragraph("PATRIMONIO NETO", ParagraphStyle("sec3", parent=s_h2, textColor=GREEN, fontSize=10)))
    pn_rows = [[f"  {c.descripcion}", fmt_n(abs(c.saldo))] for c in cuentas if c.codigo.startswith("3.")]
    pn_rows.append(["  Resultado del Ejercicio", fmt_n(resultado.resultado_ejercicio)])
    pn_rows.append(["TOTAL PATRIMONIO NETO", fmt_n(resultado.total_pn_con_resultado)])
    story.append(tabla_linea(pn_rows))
    story.append(PageBreak())

    # ══════ ESTADO DE RESULTADOS ══════════════════════════════════
    story.append(Paragraph("Estado de Resultados", s_h1))
    story.append(Paragraph(
        f"Por el ejercicio finalizado el {ejercicio.fecha_cierre.strftime('%d/%m/%Y')} — Moneda homogénea (Nota 1.3)", s_subtit
    ))
    story.append(hr())

    story.append(Paragraph("INGRESOS", ParagraphStyle("ing", parent=s_h2, textColor=GREEN, fontSize=10)))
    ing_rows = [[f"  {c.descripcion}", fmt_n(abs(c.saldo))] for c in cuentas if c.codigo.startswith("4.1")]
    ing_rows.append(["Total ingresos netos por ventas", fmt_n(resultado.total_ingresos)])
    story.append(tabla_linea(ing_rows))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("COSTOS Y GASTOS", ParagraphStyle("gas", parent=s_h2, textColor=RED, fontSize=10)))
    gas_rows = [[f"  {c.descripcion}", f"({fmt_n(c.saldo)})"] for c in cuentas if c.codigo.startswith("4.2")]
    gas_rows.append(["Total costos y gastos", f"({fmt_n(resultado.total_gastos)})"])
    story.append(tabla_linea(gas_rows))
    story.append(Spacer(1, 0.4*cm))

    label_resultado = "GANANCIA" if resultado.resultado_ejercicio >= 0 else "PÉRDIDA"
    story.append(tabla_linea([[
        f"{label_resultado} DEL EJERCICIO",
        fmt_n(abs(resultado.resultado_ejercicio))
    ]]))
    story.append(Spacer(1, 0.4*cm))

    # RECPAM
    story.append(Paragraph(
        f"RECPAM estimado: {fmt_n(resultado.recpam)} — Variación IPC del ejercicio: {resultado.variacion_ipc:.1f}%",
        s_nota
    ))
    story.append(PageBreak())

    # ══════ NOTAS ════════════════════════════════════════════════
    if incluir_notas:
        story.append(Paragraph("Notas a los Estados Contables", s_h1))
        story.append(hr())
        notas = [
            ("1. Notas generales", [
                ("1.1. Bases de preparación",
                 "Los presentes estados contables están expresados en pesos en moneda homogénea de cierre "
                 "y han sido preparados de conformidad con la Resolución Técnica N° 54 — T.O. RT 59, "
                 "emitida por la FACPCE, adoptada por el Consejo Profesional de Ciencias Económicas."),
                ("1.2. Clasificación de la entidad",
                 "De acuerdo con lo establecido por la referida norma, la entidad reviste el carácter de "
                 "Entidad " + {"EP":"Pequeña","EM":"Mediana","RE":"Restante"}.get(resultado.clasificacion_rt54,"") + " (" + resultado.clasificacion_rt54 + ")."),
                ("1.3. Unidad de medida",
                 f"Los presentes estados contables han sido preparados en moneda homogénea a fecha de cierre. "
                 f"La variación del índice utilizado (FACPCE/IPC INDEC) ha sido del {resultado.variacion_ipc:.1f}% en el ejercicio."),
            ]),
            ("2. Notas al Estado de Situación Patrimonial", [
                ("2.1. Caja y bancos",
                 "El efectivo disponible y los saldos en cuentas bancarias han sido medidos a su valor nominal, "
                 "que coincide con el valor de cotización."),
                ("2.2. Bienes de cambio",
                 "Los bienes de cambio se miden a su costo de adquisición o producción reexpresado a moneda "
                 "de cierre de acuerdo con Nota 1.3, sin superar su valor neto de realización."),
            ]),
        ]
        for titulo_sec, items in notas:
            story.append(Paragraph(titulo_sec, s_h1))
            for titulo_item, texto in items:
                story.append(Paragraph(f"<b>{titulo_item}</b>", s_body))
                story.append(Paragraph(texto, s_nota))
            story.append(Spacer(1, 0.3*cm))
        story.append(PageBreak())

    # ══════ FIRMA DEL AUDITOR ══════════════════════════════════════
    story.append(Paragraph("Informe del Auditor Independiente", s_h1))
    story.append(hr())
    story.append(Paragraph(
        f"<b>Señores</b><br/>Presidente y directores de <b>{empresa.razon_social}</b><br/>CUIT N° {empresa.cuit}",
        s_body
    ))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("<u>Informe sobre los estados contables</u>", s_body))
    story.append(Paragraph("<b>Opinión</b>", s_body))
    story.append(Paragraph(
        f"He auditado los estados contables adjuntos de {empresa.razon_social}, que comprenden el estado de "
        f"situación patrimonial al {ejercicio.fecha_cierre.strftime('%d/%m/%Y')}, el estado de resultados, el "
        f"estado de evolución del patrimonio neto y el estado de flujo de efectivo correspondientes al "
        f"ejercicio finalizado en dicha fecha, así como las notas a los estados contables.",
        s_nota
    ))
    story.append(Paragraph(
        f"En mi opinión, los estados contables adjuntos presentan razonablemente, en todos sus aspectos "
        f"significativos, la situación patrimonial de {empresa.razon_social} al {ejercicio.fecha_cierre.strftime('%d/%m/%Y')}, "
        f"de conformidad con las normas contables profesionales argentinas.",
        s_nota
    ))

    story.append(Spacer(1, 1.2*cm))
    # Bloques de firma
    if firmantes:
        firmas_data = [[
            Paragraph(f"<b>{f.get('nombre','')}</b><br/><font size='8' color='#6B82A8'>{f.get('titulo','')}</font>", s_body)
            for f in firmantes
        ]]
        t_firmas = Table(firmas_data, colWidths=[5*cm] * len(firmantes))
        t_firmas.setStyle(TableStyle([
            ("ALIGN",     (0,0),(-1,-1), "CENTER"),
            ("LINEABOVE", (0,0),(-1,-1), 0.5, MUTED),
            ("TOPPADDING",(0,0),(-1,-1), 8),
        ]))
        story.append(t_firmas)

    # Construir PDF
    doc.build(story)
    return path


# ─── Test / Demo ──────────────────────────────────────────────────

def demo():
    from datetime import date

    cuentas_raw = [
        Cuenta("1.1.1.1","Banco Ciudad CC",    31192351, 0,        31192351),
        Cuenta("1.1.1.5","Camiseta Suplente",   1429000,  0,        1429000 ),
        Cuenta("1.1.1.6","Camiseta Titular",    1513000,  0,        1513000 ),
        Cuenta("1.2.1.1","Equipo Computación", 13501326,  0,        13501326),
        Cuenta("1.2.1.2","Deprec. Acum. EC",        0,   9000884,  -9000884),
        Cuenta("1.2.3.3","Costos Organización",  476926,  0,         476926 ),
        Cuenta("1.2.5.5","Amort. Acum. CO",          0,   190730,   -190730 ),
        Cuenta("2.1.1.1","Honorarios a Pagar",       0,   439000,   -439000 ),
        Cuenta("2.1.3.3","IIBB a Pagar",             0,   569000,   -569000 ),
        Cuenta("2.1.4.4","IVA a Pagar",              0,   891009,   -891009 ),
        Cuenta("2.1.6.6","Prov. Ganancias",          0,  6197475,  -6197475 ),
        Cuenta("2.1.7.7","Hon. Socio Gerente P",     0,  4000000,  -4000000 ),
        Cuenta("3.1.1.1","Capital suscripto",        0,  5000000,  -5000000 ),
        Cuenta("3.1.2.2","Ajuste del capital",       0, 18841278, -18841278 ),
        Cuenta("3.1.3.3","Resultado Ejercicio",  402421,  0,         402421 ),
        Cuenta("3.1.4.4","Resultados no asig.",      0,  5081132,  -5081132 ),
        Cuenta("3.1.5.5","Reserva legal",            0,   246249,   -246249 ),
        Cuenta("4.1.1.1","Ventas Camiseta Sup.",     0, 113055222,-113055222),
        Cuenta("4.1.1.2","Ventas Camiseta Tit.",     0, 118546795,-118546795),
        Cuenta("4.2.1.1","Costo de Ventas",  195022799,  0,       195022799 ),
        Cuenta("4.2.2.2","IIBB",               6948031,  0,         6948031 ),
        Cuenta("4.2.4.4","Deprec. BU",         4500442,  0,         4500442 ),
        Cuenta("4.2.6.6","Hon. Socio Gerente",  4000000,  0,        4000000 ),
        Cuenta("4.2.7.7","Hon. Profesionales",  4655253,  0,        4655253 ),
        Cuenta("4.2.8.8","RECPAM",             10189636,  0,       10189636 ),
        Cuenta("4.2.9.9","Imp. Ganancias",      6197475,  0,        6197475 ),
    ]

    ejercicio = Ejercicio(
        numero=2,
        fecha_inicio=date(2025, 1, 1),
        fecha_cierre=date(2025, 12, 31),
        cuentas=cuentas_raw
    )

    motor = MotorContable(ejercicio)
    resultado = motor.calcular()
    errores   = motor.validar_saldos()
    motor.calcular_axi()

    print("=" * 60)
    print("LIBRA — Motor Contable RT54 — Resultado")
    print("=" * 60)
    print(f"  Activo:          ${resultado.total_activo:>20,.2f}")
    print(f"  Pasivo:          ${resultado.total_pasivo:>20,.2f}")
    print(f"  Patrimonio Neto: ${resultado.total_pn_con_resultado:>20,.2f}")
    print(f"  Resultado:       ${resultado.resultado_ejercicio:>20,.2f}")
    print(f"  Ingresos:        ${resultado.total_ingresos:>20,.2f}")
    print(f"  Gastos:          ${resultado.total_gastos:>20,.2f}")
    print(f"  Variación IPC:   {resultado.variacion_ipc:.1f}%")
    print(f"  RECPAM:          ${resultado.recpam:>20,.2f}")
    print(f"  Clasificación:   {resultado.clasificacion_rt54}")
    print(f"  Balance cuadra:  {'✓ SÍ' if resultado.cuadra else f'✗ NO (Dif: ${resultado.diferencia:,.2f})'}")
    print()
    print("  Indicadores:")
    print(f"    Margen neto:         {resultado.margen_neto:.2f}%")
    print(f"    ROA:                 {resultado.roa:.2f}%")
    print(f"    Liquidez corriente:  {resultado.liquidez_corriente:.2f}x")
    print(f"    Solvencia:           {resultado.solvencia:.2f}x")
    print()
    if errores:
        print(f"  Validaciones ({len(errores)}):")
        for e in errores:
            icon = "🔴" if e["tipo"]=="error" else ("🟡" if e["tipo"]=="advertencia" else "🔵")
            print(f"    {icon} [{e['codigo']}] {e['mensaje']}" + (f" — {e.get('descripcion','')}" if e.get('cuenta') else ""))
    else:
        print("  ✓ Validaciones: Sin errores")
    print()

    # Excel
    exportar_excel(motor.cuentas, resultado, "/home/claude/libra-backend/saldos_exportados.xlsx")
    print("  ✓ Excel exportado: saldos_exportados.xlsx")

    return resultado, motor.cuentas


if __name__ == "__main__":
    demo()
