# LIBRA — Plataforma Contable RT 54

Motor contable argentino full-stack.  
**Brian Verón** es el creador — acceso gratuito e ilimitado siempre.  
Los demás usuarios se registran y pagan por créditos vía MercadoPago.

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Frontend | React (JSX) — `libra.jsx` |
| Backend  | Python + FastAPI |
| Motor contable | Python puro — `motor_contable.py` |
| Auth | JWT custom (sin dependencias externas) |
| DB dev | SQLite local |
| DB prod | SQLite persistido en Render Disk / fácil migrar a Supabase |
| PDF | ReportLab |
| Excel | openpyxl |
| Deploy | Render (backend) + Vercel (frontend) |

---

## Funcionalidades implementadas

### Motor contable (`motor_contable.py`)
- [x] Clasificación RT54 automática — EP / EM / RE (umbrales 2025)
- [x] Ajuste por inflación AxI — cuentas monetarias vs no monetarias
- [x] RECPAM calculado por posición monetaria neta
- [x] IPC FACPCE tabla histórica 2021-2025 (60 períodos)
- [x] Validación partida doble + naturaleza de cuentas
- [x] Comparativo entre dos ejercicios
- [x] Indicadores: margen neto, ROA, liquidez corriente, solvencia, endeudamiento
- [x] Exportación Excel enriquecida (con tipo, rubro, subrubro, coef. AxI)
- [x] Generación PDF completo con ReportLab:
  - Carátula con composición del capital
  - ESP (Estado de Situación Patrimonial) dos columnas
  - Estado de Resultados con RECPAM
  - Notas automáticas (base, clasificación, unidad de medida)
  - Bloque de firma del auditor / síndicos
- [x] Importación Excel (columnas: Código, Descripción, Debe, Haber, Saldo)
- [x] Plan de cuentas predefinido: comercial (46 cuentas) y agropecuario (31 cuentas)

### Auth + Users (`auth.py`)
- [x] Registro público con 2 créditos gratuitos de bienvenida
- [x] Login con JWT (72hs de validez)
- [x] Rol `creator` (Brian) — gratuito e ilimitado, nunca descuenta créditos
- [x] Rol `contador` — paga por créditos
- [x] Planes: free / pro / enterprise
- [x] Sistema de créditos: compra, consumo, historial
- [x] Creación automática de estudio al registrarse
- [x] SQLite local (fácil swap a Supabase Postgres)

### API REST (`api_v2.py`) — 35 endpoints
```
POST   /auth/register          Registro público
POST   /auth/login             Login → JWT
GET    /auth/me                Usuario autenticado
PUT    /auth/password          Cambiar contraseña

GET    /estudio                Info + stats del estudio
PUT    /estudio                Actualizar nombre
GET    /estudio/firmantes      Listar firmantes
POST   /estudio/firmantes      Agregar firmante
DELETE /estudio/firmantes/{id} Eliminar firmante

GET    /empresas               Listar empresas con ejercicios
POST   /empresas               Crear empresa
GET    /empresas/{id}          Detalle empresa
PUT    /empresas/{id}          Actualizar empresa
DELETE /empresas/{id}          Desactivar empresa

POST   /ejercicios             Crear ejercicio
GET    /ejercicios/{id}/cuentas   Listar cuentas
POST   /ejercicios/{id}/cuentas   Guardar cuentas

POST   /calcular               Calcular balance + indicadores + RT54
POST   /validar                Validar consistencia contable
POST   /axi                    Aplicar ajuste por inflación
POST   /comparativo            Comparar dos ejercicios
GET    /ipc                    Todos los índices IPC
GET    /ipc/{año}/{mes}        IPC específico
POST   /clasificar-rt54        Clasificar ente por ingresos

POST   /importar-excel         Importar saldos desde Excel
POST   /exportar-excel         Exportar saldos enriquecidos
GET    /plantilla-excel        Descargar plantilla Excel
GET    /plan-cuentas/{tipo}    Plan predefinido (comercial/agropecuario)

POST   /emitir-balance         PDF desde empresa/ejercicio en DB (consume crédito)
POST   /emitir-balance-inline  PDF desde cuentas inline (consume crédito)

GET    /creditos               Saldo + historial de transacciones
POST   /creditos/comprar       Iniciar pago MercadoPago
POST   /creditos/webhook-mp    Webhook MP (pago aprobado)
POST   /creditos/agregar-manual Solo creator: agregar créditos a usuario

GET    /admin/usuarios         Lista todos los usuarios (solo creator)
GET    /admin/stats            Estadísticas globales (solo creator)
PUT    /admin/usuarios/{id}/creditos Ajustar créditos
PUT    /admin/usuarios/{id}/plan     Cambiar plan
DELETE /admin/usuarios/{id}         Desactivar usuario
```

### Frontend (`libra.jsx`)
- [x] Pantalla de auth con registro/login (layout de dos columnas)
- [x] Dashboard con stats en tiempo real desde API
- [x] Gestión completa de empresas (CRUD)
- [x] Timeline de ejercicios con estados
- [x] Cargar saldos: drag & drop, importación Excel, validación en tiempo real
- [x] Tabla de cuentas con Código/Descripción/Tipo badge/Rubro/Subrubro/Debe/Haber
- [x] Toggle Original/Reexpresado
- [x] Totales en tiempo real (local + sync con API)
- [x] Emisión de balance con sidebar de 15 secciones:
  - Carátula, Notas, Anexos, Estado de Resultados, ESP, Bienes de Uso, Intangibles, CMV, Partes Relacionadas, Informe del Auditor, Configuración de exportación
- [x] Generación PDF real vía API (con spinner y manejo de errores)
- [x] Panel de créditos con packs y MercadoPago
- [x] Admin panel completo (solo creator): stats globales, tabla de usuarios, edición de créditos/plan, desactivación
- [x] Creator badge con acceso gratuito ilimitado

---

## Deploy en 15 minutos

### 1. Backend en Render (gratis)

```bash
# Subir a GitHub
cd libra-backend
git init && git add . && git commit -m "LIBRA v1.0"
git remote add origin https://github.com/tu-usuario/libra-api.git
git push -u origin main
```

En [render.com](https://render.com):
1. New → Web Service
2. Conectar repositorio
3. Variables de entorno:
   ```
   CREATOR_EMAIL = brianveron2@gmail.com
   LIBRA_SECRET  = (generar secreto largo)
   LIBRA_DB      = /var/data/libra.db
   ```
4. Agregar Disk: `/var/data` — 1GB
5. Deploy → copiar URL (ej: `https://libra-api.onrender.com`)

### 2. Frontend en Vercel

En `libra.jsx` línea 4:
```js
const API_URL = "https://libra-api.onrender.com"; // ← tu URL de Render
```

En [vercel.com](https://vercel.com) → New Project → subir `libra.jsx`  
O usar el artifact directamente en Claude.ai.

### 3. MercadoPago (para pagos reales)

En `api_v2.py` → `crear_preferencia_mp()`:
```python
import mercadopago
sdk = mercadopago.SDK(os.getenv("MP_ACCESS_TOKEN"))
preference_data = {
    "items": [{"title": f"LIBRA {p['creditos']} créditos", "quantity": 1, "unit_price": p['precio']/100}],
    "payer": {"email": email_mp},
    "external_reference": f"{user_id}_{pack}",
    "notification_url": "https://libra-api.onrender.com/creditos/webhook-mp",
    "back_urls": {"success": "https://tu-app.vercel.app?creditos=ok"}
}
result = sdk.preference().create(preference_data)
return {"ok": True, "checkout_url": result["response"]["init_point"]}
```
Agregar a `.env`: `MP_ACCESS_TOKEN=APP_USR-...`

---

## Credenciales por defecto

| Usuario | Email | Password | Rol |
|---------|-------|----------|-----|
| Brian Verón | brianveron2@gmail.com | libra2025 | creator (gratis ∞) |

---

## Lo que queda pendiente (backlog)

- [ ] Estado de Flujo de Efectivo (EFE) — cálculo automático
- [ ] Estado de Evolución del PN — movimientos del período
- [ ] Notas automáticas generadas desde los saldos (2.x, 3.x)
- [ ] Exportación DOCX (python-docx)
- [ ] Multi-estudio real (un usuario → N estudios)
- [ ] Módulo comparativo visual (gráfico de barras)
- [ ] Actualización automática de índices IPC (scraper FACPCE mensual)
- [ ] Webhook MercadoPago completo con verificación de firma
- [ ] Email de bienvenida al registrarse (SendGrid/Resend)
- [ ] Supabase como DB en producción (swap directo)
- [ ] 2FA para cuentas pro/enterprise
