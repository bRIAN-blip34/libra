import React, { useState, useRef, useCallback, useEffect } from "react";

// ─── CONFIG ───────────────────────────────────────────────────────
const API_URL = "https://libra-api-tu-instancia.railway.app"; // ← Cambiá por tu URL

// ─── THEME ───────────────────────────────────────────────────────
const C = {
  bg: "#070A14", surface: "#0D1220", card: "#111827",
  border: "#1A2840", bh: "#2A3F60",
  gold: "#C9A96E", goldD: "#A0804A",
  text: "#EDE8DE", muted: "#6B82A8", hint: "#3D5070",
  green: "#34D39A", red: "#F87171", blue: "#60A5FA", amber: "#FBBF24",
};

// ─── API ─────────────────────────────────────────────────────────
async function callApi(path, body, token, method) {
  const m = method || (body ? "POST" : "GET");
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = "Bearer " + token;
  try {
    const res = await fetch(API_URL + path, {
      method: m,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(function() { return {}; });
    return { ok: res.ok, data: data };
  } catch (e) {
    return { ok: false, data: { detail: "Sin conexión a la API" } };
  }
}

async function callApiBin(path, body, token) {
  try {
    const res = await fetch(API_URL + path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    return { blob: await res.blob(), creditos: res.headers.get("x-creditos-restantes") };
  } catch (e) {
    return null;
  }
}

function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── MOTOR LOCAL (sin API) ────────────────────────────────────────
function calcularLocal(saldos) {
  function get(p) { return saldos.filter(function(r) { return r.codigo.startsWith(p); }); }
  function sum(arr) { return arr.reduce(function(a, r) { return a + (r.saldo || 0); }, 0); }
  var ac = get("1.1"), anc = get("1.2"), pc = get("2.1"), pnc = get("2.2");
  var pn = get("3."), ing = get("4.1"), gas = get("4.2");
  var acs = sum(ac), ancs = sum(anc), ta = acs + ancs;
  var tpc = Math.abs(sum(pc)), tpnc = Math.abs(sum(pnc));
  var tpn = Math.abs(sum(pn));
  var ti = Math.abs(sum(ing)), tg = sum(gas);
  var res = ti - tg, tp = tpc + tpnc, pnr = tpn + res;
  var dif = Math.abs(ta - (tp + pnr));
  return {
    total_activo: ta, total_pasivo: tp, total_pn: pnr,
    resultado: res, total_ingresos: ti, total_gastos: tg,
    activo_corriente: acs, activo_no_corriente: ancs,
    pasivo_corriente: tpc, pasivo_no_corriente: tpnc,
    variacion_ipc: 37.5, recpam: 0,
    cuadra: dif < 100, diferencia: dif,
    rt54: ti > 12e9 ? "RE" : ti > 3.5e9 ? "EM" : "EP",
    margen: ti ? (res / ti * 100) : 0,
    roa: ta ? (res / ta * 100) : 0,
    liquidez: tpc ? acs / tpc : 0,
    solvencia: tp ? ta / tp : 0,
  };
}

var SUBRUBROS = {
  "1.1.1": "Caja y bancos", "1.1.2": "Inversiones financieras",
  "1.1.3": "Créditos impositivos", "1.1.4": "Bienes de cambio",
  "1.1.5": "Bienes de cambio", "1.1.6": "Bienes de cambio",
  "1.1.7": "Otros créditos", "1.1.8": "Créditos por ventas",
  "1.2.1": "Bienes de uso", "1.2.2": "Bienes de uso",
  "1.2.3": "Activos intangibles", "1.2.4": "Activos intangibles",
  "2.1.1": "Proveedores", "2.1.2": "Proveedores",
  "2.1.3": "Deudas fiscales", "2.1.4": "Deudas fiscales",
  "2.1.5": "Deudas fiscales", "2.1.6": "Deudas fiscales",
  "2.1.7": "Partes relacionadas",
  "2.2.1": "Préstamos bancarios", "2.2.2": "Deudas financieras",
  "3.1.1": "Capital suscripto", "3.1.2": "Ajuste del capital",
  "3.1.3": "Resultados no asignados", "3.1.4": "Resultados no asignados",
  "3.1.5": "Reserva legal",
  "4.1.1": "Ingresos por ventas", "4.1.2": "Ingresos por ventas",
  "4.1.3": "Resultados financieros (RECPAM)",
  "4.2.1": "Costo de bienes vendidos", "4.2.2": "Ingresos brutos",
  "4.2.3": "Amortización intangibles", "4.2.4": "Depreciación bienes de uso",
  "4.2.5": "Servicios bancarios", "4.2.6": "Honorarios directores",
  "4.2.7": "Honorarios profesionales",
  "4.2.8": "Resultados financieros (RECPAM)", "4.2.9": "Imp. a las ganancias",
};

function getSub(c) { var k = c.split(".").slice(0, 3).join("."); return SUBRUBROS[k] || "—"; }
function getRub(c) {
  var p = c[0], s = c.split(".")[1];
  if (p === "1") return s === "1" ? "corriente" : "no_corriente";
  if (p === "2") return s === "1" ? "corriente" : "no_corriente";
  if (p === "3") return "patrimonio_neto";
  if (p === "4") return s === "1" ? "ingresos" : "gastos";
  return "—";
}
function getTipo(c) { return ({ "1": "A", "2": "P", "3": "PN", "4": "R" })[c[0]] || "?"; }
function fmt(n) {
  return new Intl.NumberFormat("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 2
  }).format(Math.abs(n || 0));
}
function fmtN(n) {
  return new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(n || 0);
}
function pct(a, b) { return b ? ((a / b) * 100).toFixed(1) + "%" : "—"; }

// ─── BASE UI ──────────────────────────────────────────────────────
var TIPO_COLORS = {
  A:  { label: "Activo",    bg: "#34D39A22", color: "#34D39A", bd: "#34D39A55" },
  P:  { label: "Pasivo",    bg: "#F8717122", color: "#F87171", bd: "#F8717155" },
  PN: { label: "Pat. Neto", bg: "#60A5FA22", color: "#60A5FA", bd: "#60A5FA55" },
  R:  { label: "Resultado", bg: "#FBBF2422", color: "#FBBF24", bd: "#FBBF2455" },
};

function TipoBadge(props) {
  var m = TIPO_COLORS[props.tipo] || { label: props.tipo, bg: "#fff1", color: C.muted, bd: C.border };
  return React.createElement("span", {
    style: {
      background: m.bg, color: m.color, border: "1px solid " + m.bd,
      borderRadius: 4, padding: "2px 7px", fontSize: 10, fontWeight: 700,
      letterSpacing: "0.05em", whiteSpace: "nowrap"
    }
  }, m.label);
}

function Tag(props) {
  var color = props.color || C.gold;
  return React.createElement("span", {
    style: {
      background: color + "22", color: color, border: "1px solid " + color + "44",
      borderRadius: 4, padding: "2px 8px", fontSize: 10, fontWeight: 700,
      letterSpacing: "0.06em", textTransform: "uppercase", whiteSpace: "nowrap"
    }
  }, props.children);
}

function Card(props) {
  var accent = props.accent || C.border;
  return React.createElement("div", {
    onClick: props.onClick,
    style: Object.assign({
      background: C.card, border: "1px solid " + accent,
      borderRadius: 12, padding: "20px 24px",
      cursor: props.onClick ? "pointer" : "default",
      transition: "border-color .2s",
    }, props.style || {}),
    onMouseEnter: props.onClick ? function(e) { e.currentTarget.style.borderColor = C.bh; } : undefined,
    onMouseLeave: props.onClick ? function(e) { e.currentTarget.style.borderColor = accent; } : undefined,
  }, props.children);
}

function Btn(props) {
  var v = props.variant || "primary";
  var small = props.small;
  var loading = props.loading;
  var disabled = props.disabled || loading;
  var variants = {
    primary: { background: C.gold, color: "#0A0E14", border: "none" },
    ghost:   { background: "transparent", color: C.muted, border: "1px solid " + C.border },
    danger:  { background: "#F8717122", color: C.red, border: "1px solid #F8717144" },
    outline: { background: "transparent", color: C.gold, border: "1px solid " + C.gold + "44" },
    blue:    { background: C.blue + "22", color: C.blue, border: "1px solid " + C.blue + "44" },
    green:   { background: C.green + "22", color: C.green, border: "1px solid " + C.green + "44" },
  };
  var vs = variants[v] || variants.primary;
  return React.createElement("button", {
    onClick: disabled ? undefined : props.onClick,
    disabled: disabled,
    style: Object.assign({
      borderRadius: 8, padding: small ? "7px 14px" : "10px 20px",
      fontFamily: "'DM Sans',sans-serif", fontSize: small ? 12 : 14, fontWeight: 600,
      cursor: disabled ? "not-allowed" : "pointer", transition: "all .15s",
      opacity: disabled ? 0.55 : 1, display: "inline-flex", alignItems: "center",
      gap: 6, justifyContent: "center",
    }, vs, props.style || {}),
  }, loading ? React.createElement("span", {
    style: {
      width: 12, height: 12, border: "2px solid currentColor",
      borderTopColor: "transparent", borderRadius: "50%",
      display: "inline-block", animation: "libra-spin .7s linear infinite"
    }
  }) : null, props.children);
}

function Input(props) {
  return React.createElement("div", { style: { marginBottom: 16 } },
    props.label && React.createElement("div", {
      style: { fontSize: 11, color: C.muted, marginBottom: 5, fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase" }
    }, props.label),
    React.createElement("input", {
      type: props.type || "text",
      value: props.value,
      readOnly: props.readOnly,
      placeholder: props.placeholder,
      onChange: function(e) { if (props.onChange) props.onChange(e.target.value); },
      style: {
        width: "100%", background: C.surface, border: "1px solid " + (props.error ? C.red : C.border),
        borderRadius: 8, padding: "10px 14px", color: C.text,
        fontFamily: "'DM Sans',sans-serif", fontSize: 14, outline: "none",
        boxSizing: "border-box", opacity: props.readOnly ? 0.6 : 1,
      }
    }),
    props.error && React.createElement("div", { style: { fontSize: 11, color: C.red, marginTop: 4 } }, props.error)
  );
}

function Alert(props) {
  var types = {
    error:   { c: C.red,   icon: "✗" },
    warning: { c: C.amber, icon: "⚠" },
    success: { c: C.green, icon: "✓" },
    info:    { c: C.blue,  icon: "ℹ" },
  };
  var t = types[props.type] || types.info;
  return React.createElement("div", {
    style: {
      background: t.c + "15", border: "1px solid " + t.c + "44", borderRadius: 8,
      padding: "10px 14px", display: "flex", gap: 8, fontSize: 12, marginBottom: 10,
    }
  },
    React.createElement("span", { style: { color: t.c, fontWeight: 700, flexShrink: 0 } }, t.icon),
    React.createElement("span", { style: { color: C.text } }, props.children)
  );
}

function Stat(props) {
  var color = props.color || C.gold;
  return React.createElement(Card, { style: { display: "flex", alignItems: "center", gap: 14, padding: "16px 20px" } },
    props.icon && React.createElement("div", {
      style: {
        width: 40, height: 40, borderRadius: 10, background: color + "18",
        border: "1px solid " + color + "30", display: "flex", alignItems: "center",
        justifyContent: "center", fontSize: 16, color: color, flexShrink: 0
      }
    }, props.icon),
    React.createElement("div", null,
      React.createElement("div", {
        style: { fontSize: 20, fontWeight: 700, color: color, fontFamily: "'Playfair Display',serif", lineHeight: 1.2 }
      }, props.value),
      React.createElement("div", { style: { fontSize: 11, color: C.muted, marginTop: 3 } }, props.label),
      props.sub && React.createElement("div", { style: { fontSize: 10, color: color, marginTop: 2 } }, props.sub)
    )
  );
}

function PageTitle(props) {
  return React.createElement("div", { style: { marginBottom: 24 } },
    React.createElement("div", { style: { fontSize: 10, color: C.muted, letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 5 } }, props.sub || "Libra"),
    React.createElement("h1", { style: { margin: 0, fontFamily: "'Playfair Display',serif", fontSize: 28, fontWeight: 700, color: C.text } }, props.children)
  );
}

function Toggle(props) {
  return React.createElement("div", {
    style: { display: "flex", background: C.surface, borderRadius: 8, padding: 3, border: "1px solid " + C.border }
  }, props.options.map(function(o) {
    return React.createElement("div", {
      key: o.value,
      onClick: function() { props.onChange(o.value); },
      style: {
        padding: "6px 14px", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 500,
        background: props.value === o.value ? C.gold : "transparent",
        color: props.value === o.value ? "#0A0E14" : C.muted, transition: "all .15s"
      }
    }, o.label);
  }));
}

// ─── DEMO SALDOS ─────────────────────────────────────────────────
var DEMO = [
  { codigo: "1.1.1.1", descripcion: "Banco CC", debe: 31192351, haber: 0, saldo: 31192351 },
  { codigo: "1.1.1.5", descripcion: "Camiseta Suplente", debe: 1429000, haber: 0, saldo: 1429000 },
  { codigo: "1.1.1.6", descripcion: "Camiseta Titular", debe: 1513000, haber: 0, saldo: 1513000 },
  { codigo: "1.2.1.1", descripcion: "Equipo de Computación", debe: 13501326, haber: 0, saldo: 13501326 },
  { codigo: "1.2.1.2", descripcion: "Deprec. Acum. EC", debe: 0, haber: 9000884, saldo: -9000884 },
  { codigo: "1.2.3.3", descripcion: "Costos de Organización", debe: 476926, haber: 0, saldo: 476926 },
  { codigo: "2.1.1.1", descripcion: "Honorarios a Pagar", debe: 0, haber: 439000, saldo: -439000 },
  { codigo: "2.1.3.3", descripcion: "IIBB a Pagar", debe: 0, haber: 569000, saldo: -569000 },
  { codigo: "2.1.4.4", descripcion: "IVA a Pagar", debe: 0, haber: 891009, saldo: -891009 },
  { codigo: "2.1.6.6", descripcion: "Provisión Ganancias", debe: 0, haber: 6197475, saldo: -6197475 },
  { codigo: "2.1.7.7", descripcion: "Honorarios Socio Gerente P.", debe: 0, haber: 4000000, saldo: -4000000 },
  { codigo: "3.1.1.1", descripcion: "Capital suscripto", debe: 0, haber: 5000000, saldo: -5000000 },
  { codigo: "3.1.2.2", descripcion: "Ajuste del capital", debe: 0, haber: 18841278, saldo: -18841278 },
  { codigo: "3.1.3.3", descripcion: "Resultado del Ejercicio", debe: 402421, haber: 0, saldo: 402421 },
  { codigo: "3.1.4.4", descripcion: "Resultados no asignados", debe: 0, haber: 5081132, saldo: -5081132 },
  { codigo: "3.1.5.5", descripcion: "Reserva legal", debe: 0, haber: 246249, saldo: -246249 },
  { codigo: "4.1.1.1", descripcion: "Ventas Camiseta Suplente", debe: 0, haber: 113055222, saldo: -113055222 },
  { codigo: "4.1.1.2", descripcion: "Ventas Camiseta Titular", debe: 0, haber: 118546795, saldo: -118546795 },
  { codigo: "4.2.1.1", descripcion: "Costo de Ventas", debe: 195022799, haber: 0, saldo: 195022799 },
  { codigo: "4.2.2.2", descripcion: "IIBB", debe: 6948031, haber: 0, saldo: 6948031 },
  { codigo: "4.2.4.4", descripcion: "Depreciación Bienes de Uso", debe: 4500442, haber: 0, saldo: 4500442 },
  { codigo: "4.2.6.6", descripcion: "Honorarios Socio Gerente", debe: 4000000, haber: 0, saldo: 4000000 },
  { codigo: "4.2.7.7", descripcion: "Honorarios Profesionales", debe: 4655253, haber: 0, saldo: 4655253 },
  { codigo: "4.2.8.8", descripcion: "RECPAM", debe: 10189636, haber: 0, saldo: 10189636 },
  { codigo: "4.2.9.9", descripcion: "Impuesto a las Ganancias", debe: 6197475, haber: 0, saldo: 6197475 },
];

// ─── AUTH ────────────────────────────────────────────────────────
function AuthScreen(props) {
  var _s = useState("login"); var mode = _s[0]; var setMode = _s[1];
  var _e = useState(""); var email = _e[0]; var setEmail = _e[1];
  var _n = useState(""); var nombre = _n[0]; var setNombre = _n[1];
  var _p = useState(""); var pwd = _p[0]; var setPwd = _p[1];
  var _l = useState(false); var loading = _l[0]; var setLoading = _l[1];
  var _er = useState(""); var error = _er[0]; var setError = _er[1];

  function submit() {
    setError(""); setLoading(true);
    var path = mode === "login" ? "/auth/login" : "/auth/register";
    var body = mode === "login"
      ? { email: email, password: pwd }
      : { email: email, nombre: nombre, password: pwd };
    callApi(path, body).then(function(r) {
      if (r.ok) {
        props.onAuth(r.data);
      } else {
        setError(r.data.detail || (mode === "login" ? "Credenciales incorrectas" : "Error al registrarse"));
      }
      setLoading(false);
    });
  }

  return React.createElement("div", {
    style: { minHeight: "100vh", background: C.bg, display: "flex", fontFamily: "'DM Sans',sans-serif" }
  },
    // Left panel
    React.createElement("div", {
      style: { width: 420, padding: "60px 50px", background: C.surface, borderRight: "1px solid " + C.border, minHeight: "100vh", display: "flex", flexDirection: "column", justifyContent: "center" }
    },
      React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 12, marginBottom: 48 } },
        React.createElement("div", {
          style: { width: 40, height: 40, background: C.gold + "18", border: "1px solid " + C.gold + "44", borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, color: C.gold }
        }, "⚖"),
        React.createElement("div", null,
          React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 20, fontWeight: 700, color: C.gold } }, "LIBRA"),
          React.createElement("div", { style: { fontSize: 9, color: C.hint, letterSpacing: "0.14em", textTransform: "uppercase" } }, "Plataforma contable")
        )
      ),
      React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 26, fontWeight: 700, marginBottom: 8, color: C.text } },
        mode === "login" ? "Bienvenido de nuevo" : "Creá tu cuenta"
      ),
      React.createElement("div", { style: { fontSize: 13, color: C.muted, marginBottom: 32, lineHeight: 1.6 } },
        mode === "login"
          ? "Iniciá sesión para acceder a tu estudio contable."
          : "Registrate con 2 créditos gratuitos para explorar."
      ),
      error && React.createElement(Alert, { type: "error" }, error),
      mode === "register" && React.createElement(Input, { label: "Nombre completo", value: nombre, onChange: setNombre, placeholder: "María García" }),
      React.createElement(Input, { label: "Email", value: email, onChange: setEmail, placeholder: "contador@estudio.com", type: "email" }),
      React.createElement(Input, { label: "Contraseña", value: pwd, onChange: setPwd, placeholder: "••••••••", type: "password" }),
      React.createElement(Btn, { onClick: submit, loading: loading, style: { width: "100%", padding: "12px", marginBottom: 16 } },
        mode === "login" ? "Iniciar sesión" : "Crear cuenta"
      ),
      React.createElement("div", { style: { textAlign: "center", fontSize: 13, color: C.muted } },
        mode === "login" ? "¿No tenés cuenta? " : "¿Ya tenés cuenta? ",
        React.createElement("span", {
          onClick: function() { setMode(mode === "login" ? "register" : "login"); setError(""); },
          style: { color: C.gold, cursor: "pointer", fontWeight: 600 }
        }, mode === "login" ? "Registrate gratis" : "Iniciar sesión")
      )
    ),
    // Right panel
    React.createElement("div", {
      style: { flex: 1, background: "linear-gradient(135deg, " + C.bg + " 0%, #0a1628 100%)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 60 }
    },
      React.createElement("div", { style: { maxWidth: 420, textAlign: "center" } },
        React.createElement("div", { style: { fontSize: 48, marginBottom: 24, opacity: 0.6 } }, "⚖"),
        React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 26, fontWeight: 700, color: C.gold, marginBottom: 16 } }, "Motor contable RT 54"),
        React.createElement("div", { style: { fontSize: 14, color: C.muted, lineHeight: 1.8, marginBottom: 32 } },
          "Ajuste por inflación (AxI), RECPAM automático, clasificación EP/EM/RE, exportación PDF y Excel."
        ),
        [
          "Clasificación automática RT54 — EP / EM / RE",
          "Ajuste por inflación con IPC FACPCE actualizado",
          "RECPAM calculado automáticamente",
          "PDF con carátula, anexos, notas y firma del auditor",
          "Comparativo entre ejercicios en tiempo real",
        ].map(function(t) {
          return React.createElement("div", { key: t, style: { display: "flex", alignItems: "center", gap: 10, marginBottom: 10, textAlign: "left" } },
            React.createElement("span", { style: { color: C.green, fontWeight: 700 } }, "✓"),
            React.createElement("span", { style: { fontSize: 13, color: C.muted } }, t)
          );
        })
      )
    )
  );
}

// ─── SIDEBAR ─────────────────────────────────────────────────────
function Sidebar(props) {
  var user = props.user;
  var page = props.page;
  var nav = [
    { id: "dashboard", label: "Inicio",         icon: "⬡" },
    { id: "empresas",  label: "Empresas",        icon: "◻" },
    { id: "upload",    label: "Cargar saldos",   icon: "⊞" },
    { id: "config",    label: "Configuración",   icon: "◈" },
  ];
  if (user && user.es_creator) {
    nav.push({ id: "admin", label: "Admin", icon: "⚙" });
  }

  return React.createElement("div", {
    style: { width: 220, background: C.surface, borderRight: "1px solid " + C.border, display: "flex", flexDirection: "column", flexShrink: 0 }
  },
    // Logo
    React.createElement("div", { style: { padding: "26px 20px 22px", borderBottom: "1px solid " + C.border } },
      React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 10 } },
        React.createElement("div", { style: { width: 34, height: 34, background: C.gold + "18", border: "1px solid " + C.gold + "44", borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, color: C.gold } }, "⚖"),
        React.createElement("div", null,
          React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 17, fontWeight: 700, color: C.gold, letterSpacing: "0.05em" } }, "LIBRA"),
          React.createElement("div", { style: { fontSize: 8, color: C.hint, letterSpacing: "0.14em", textTransform: "uppercase" } }, "Plataforma contable")
        )
      )
    ),
    // Nav
    React.createElement("nav", { style: { flex: 1, padding: "14px 10px" } },
      nav.map(function(n) {
        var active = page === n.id || (n.id === "empresas" && (page === "empresa" || page === "emision"));
        return React.createElement("div", {
          key: n.id,
          onClick: function() { props.setPage(n.id); },
          style: {
            display: "flex", alignItems: "center", gap: 9, padding: "8px 12px",
            borderRadius: 8, marginBottom: 2, cursor: "pointer",
            background: active ? C.gold + "18" : "transparent",
            color: active ? C.gold : C.muted, fontSize: 13,
            fontWeight: active ? 600 : 400, transition: "all .15s"
          },
          onMouseEnter: function(e) { if (!active) e.currentTarget.style.background = "#ffffff08"; },
          onMouseLeave: function(e) { if (!active) e.currentTarget.style.background = "transparent"; },
        },
          React.createElement("span", { style: { fontSize: 12, width: 16, textAlign: "center" } }, n.icon),
          n.label,
          n.id === "admin" && React.createElement("span", {
            style: { marginLeft: "auto", background: C.amber + "22", color: C.amber, fontSize: 8, padding: "1px 5px", borderRadius: 3, fontWeight: 700 }
          }, "PRO"),
          active && n.id !== "admin" && React.createElement("div", { style: { marginLeft: "auto", width: 4, height: 4, borderRadius: "50%", background: C.gold } })
        );
      })
    ),
    // Credits badge
    React.createElement("div", { style: { margin: "0 10px 10px", background: C.gold + "10", border: "1px solid " + C.gold + "30", borderRadius: 8, padding: "10px 12px" } },
      React.createElement("div", { style: { fontSize: 10, color: C.goldD, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 3 } },
        user && user.es_creator ? "Creator" : "Estudio activo"
      ),
      React.createElement("div", { style: { fontSize: 13, fontWeight: 600, color: C.gold } },
        (user && user.estudio_nombre) || "Ofi"
      ),
      React.createElement("div", { style: { fontSize: 10, color: C.muted, marginTop: 2 } },
        user && user.es_creator ? "∞ ilimitado y gratuito" : ((user && user.creditos) || 0) + " créditos"
      )
    ),
    // User
    React.createElement("div", { style: { padding: "14px 18px", borderTop: "1px solid " + C.border, display: "flex", alignItems: "center", gap: 10 } },
      React.createElement("div", {
        style: { width: 30, height: 30, borderRadius: "50%", background: C.gold + "25", border: "1px solid " + C.gold + "44", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, color: C.gold, flexShrink: 0 }
      }, user ? user.nombre[0].toUpperCase() : "?"),
      React.createElement("div", { style: { overflow: "hidden" } },
        React.createElement("div", { style: { fontSize: 12, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }, user ? user.nombre : ""),
        React.createElement("div", { style: { fontSize: 10, color: C.muted } }, user && user.es_creator ? "Creator" : "Contador")
      )
    )
  );
}

// ─── DASHBOARD ───────────────────────────────────────────────────
function Dashboard(props) {
  var h = new Date().getHours();
  var sal = h < 12 ? "Buenos días" : h < 19 ? "Buenas tardes" : "Buenas noches";
  var user = props.user;
  var empresas = props.empresas || [];

  return React.createElement("div", { style: { maxWidth: 1060, margin: "0 auto", padding: "38px 36px" } },
    React.createElement("div", { style: { marginBottom: 32, display: "flex", justifyContent: "space-between", alignItems: "flex-end" } },
      React.createElement("div", null,
        React.createElement("div", { style: { fontSize: 10, color: C.muted, letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 5 } }, sal),
        React.createElement("h1", { style: { margin: 0, fontFamily: "'Playfair Display',serif", fontSize: 32, fontWeight: 700 } }, user ? user.nombre : ""),
        React.createElement("div", { style: { color: C.muted, fontSize: 13, marginTop: 4 } },
          new Date().toLocaleDateString("es-AR", { weekday: "long", year: "numeric", month: "long", day: "numeric" })
        )
      ),
      React.createElement("div", { style: { display: "flex", gap: 10, alignItems: "center" } },
        user && user.es_creator && React.createElement(Tag, { color: C.amber }, "Creator — Sin límites"),
        React.createElement(Btn, { onClick: function() { props.setPage("upload"); } }, "+ Nuevo balance")
      )
    ),
    // Stats
    React.createElement("div", { style: { display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 28 } },
      React.createElement(Stat, { label: "Empresas", value: empresas.length, icon: "◻", color: C.gold }),
      React.createElement(Stat, { label: "Créditos", value: user && user.es_creator ? "∞" : (user && user.creditos || 0), icon: "◈", color: C.amber }),
      React.createElement(Stat, { label: "IPC 2025", value: "37.5%", icon: "◉", color: C.blue }),
      React.createElement(Stat, { label: "Normativa", value: "RT 54", icon: "⊞", color: C.green })
    ),
    // Content
    React.createElement("div", { style: { display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 18 } },
      React.createElement(Card, null,
        React.createElement("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 } },
          React.createElement("div", { style: { fontSize: 11, color: C.muted, letterSpacing: "0.08em", textTransform: "uppercase" } }, "Empresas recientes"),
          React.createElement("span", { onClick: function() { props.setPage("empresas"); }, style: { fontSize: 12, color: C.gold, cursor: "pointer" } }, "Ver todas →")
        ),
        empresas.length === 0
          ? React.createElement("div", { style: { textAlign: "center", padding: "30px 0", color: C.muted, fontSize: 13 } },
              "No hay empresas aún. ",
              React.createElement("span", { onClick: function() { props.setPage("empresas"); }, style: { color: C.gold, cursor: "pointer" } }, "Creá la primera →")
            )
          : empresas.slice(0, 3).map(function(e) {
              return React.createElement("div", {
                key: e.id,
                onClick: function() { props.setEmpresa(e); props.setPage("empresa"); },
                style: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px", borderRadius: 9, background: C.surface, marginBottom: 8, cursor: "pointer", border: "1px solid " + C.border, transition: "border-color .15s" },
                onMouseEnter: function(ev) { ev.currentTarget.style.borderColor = C.bh; },
                onMouseLeave: function(ev) { ev.currentTarget.style.borderColor = C.border; },
              },
                React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 12 } },
                  React.createElement("div", { style: { width: 36, height: 36, borderRadius: 8, background: C.gold + "15", border: "1px solid " + C.gold + "30", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, color: C.gold } }, "◻"),
                  React.createElement("div", null,
                    React.createElement("div", { style: { fontWeight: 600, fontSize: 13 } }, e.razon_social),
                    React.createElement("div", { style: { fontSize: 11, color: C.muted, marginTop: 1 } }, "CUIT " + e.cuit)
                  )
                ),
                React.createElement("div", { style: { display: "flex", gap: 8, alignItems: "center" } },
                  React.createElement(Tag, null, e.tipo),
                  React.createElement("span", { style: { color: C.hint } }, "›")
                )
              );
            })
      ),
      React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: 14 } },
        React.createElement(Card, null,
          React.createElement("div", { style: { fontSize: 11, color: C.muted, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 14 } }, "Acciones rápidas"),
          [
            { icon: "◻", label: "Nueva empresa",    page: "empresas" },
            { icon: "⊞", label: "Cargar saldos",    page: "upload"   },
            { icon: "◈", label: "Comprar créditos", page: "config"   },
          ].map(function(x) {
            if (user && user.es_creator && x.label === "Comprar créditos") return null;
            return React.createElement("div", {
              key: x.label,
              onClick: function() { props.setPage(x.page); },
              style: { display: "flex", alignItems: "center", gap: 10, padding: "9px 12px", borderRadius: 8, cursor: "pointer", fontSize: 13, color: C.muted, transition: "all .15s", marginBottom: 2 },
              onMouseEnter: function(e) { e.currentTarget.style.background = C.surface; e.currentTarget.style.color = C.gold; },
              onMouseLeave: function(e) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = C.muted; },
            },
              React.createElement("span", { style: { fontSize: 12 } }, x.icon),
              x.label
            );
          })
        ),
        React.createElement(Card, { accent: C.gold + "33" },
          React.createElement("div", { style: { fontSize: 10, color: C.goldD, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 } }, "Normativa vigente"),
          React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 15, fontWeight: 600, marginBottom: 8 } }, "RT 54 · FACPCE"),
          React.createElement("div", { style: { fontSize: 12, color: C.muted, lineHeight: 1.7 } }, "Clasificación EP/EM/RE. Ajuste AxI. RECPAM automático. IPC " + new Date().getFullYear() + ".")
        )
      )
    )
  );
}

// ─── EMPRESAS ────────────────────────────────────────────────────
function Empresas(props) {
  var _sf = useState(false); var showForm = _sf[0]; var setShowForm = _sf[1];
  var _fr = useState({ razon_social: "", cuit: "", tipo: "S.A.", actividad: "", domicilio: "", consejo_profesional: "CPCE Buenos Aires", nro_inscripcion: "", capital_suscripto: "" });
  var form = _fr[0]; var setForm = _fr[1];
  var _ld = useState(false); var loading = _ld[0]; var setLoading = _ld[1];

  function setF(k) { return function(v) { setForm(Object.assign({}, form, { [k]: v })); }; }

  function guardar() {
    setLoading(true);
    callApi("/empresas", Object.assign({}, form, { capital_suscripto: parseFloat(form.capital_suscripto) || 0 }), props.token).then(function(r) {
      if (r.ok) { setShowForm(false); props.reload(); }
      setLoading(false);
    });
  }

  return React.createElement("div", { style: { maxWidth: 1060, margin: "0 auto", padding: "38px 36px" } },
    React.createElement("div", { style: { display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 28 } },
      React.createElement(PageTitle, { sub: "Gestión" }, "Empresas"),
      React.createElement(Btn, { onClick: function() { setShowForm(!showForm); } }, showForm ? "✕ Cancelar" : "+ Nueva empresa")
    ),
    showForm && React.createElement(Card, { accent: C.gold + "55", style: { marginBottom: 22 } },
      React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 16, fontWeight: 600, marginBottom: 20, color: C.gold } }, "Nueva empresa"),
      React.createElement("div", { style: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 22px" } },
        React.createElement(Input, { label: "Razón Social *", value: form.razon_social, onChange: setF("razon_social"), placeholder: "INSUMOS Y SERVICIOS S.A." }),
        React.createElement(Input, { label: "CUIT *", value: form.cuit, onChange: setF("cuit"), placeholder: "XX-XXXXXXXX-X" }),
        React.createElement(Input, { label: "Actividad Principal", value: form.actividad, onChange: setF("actividad"), placeholder: "Comercio mayorista" }),
        React.createElement(Input, { label: "Domicilio Legal", value: form.domicilio, onChange: setF("domicilio"), placeholder: "Av. Corrientes 1234" }),
        React.createElement(Input, { label: "N° Inscripción", value: form.nro_inscripcion, onChange: setF("nro_inscripcion"), placeholder: "9481F" }),
        React.createElement(Input, { label: "Capital Suscripto", value: form.capital_suscripto, onChange: setF("capital_suscripto"), type: "number", placeholder: "2000000" })
      ),
      React.createElement("div", { style: { display: "flex", gap: 10 } },
        React.createElement(Btn, { loading: loading, onClick: guardar }, "Guardar empresa"),
        React.createElement(Btn, { variant: "ghost", onClick: function() { setShowForm(false); } }, "Cancelar")
      )
    ),
    props.empresas.length === 0 && !showForm && React.createElement("div", { style: { textAlign: "center", padding: "60px 20px", color: C.muted } },
      React.createElement("div", { style: { fontSize: 48, marginBottom: 16, opacity: 0.3 } }, "◻"),
      React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 18, marginBottom: 8, color: C.text } }, "No hay empresas aún"),
      React.createElement(Btn, { onClick: function() { setShowForm(true); }, style: { marginTop: 8 } }, "+ Nueva empresa")
    ),
    React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: 10 } },
      props.empresas.map(function(e) {
        return React.createElement(Card, {
          key: e.id,
          onClick: function() { props.setEmpresa(e); props.setPage("empresa"); },
          style: { display: "flex", alignItems: "center", justifyContent: "space-between" }
        },
          React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 16 } },
            React.createElement("div", { style: { width: 46, height: 46, borderRadius: 11, background: C.gold + "15", border: "1px solid " + C.gold + "30", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, color: C.gold } }, "◻"),
            React.createElement("div", null,
              React.createElement("div", { style: { fontWeight: 600, fontSize: 15 } }, e.razon_social),
              React.createElement("div", { style: { fontSize: 12, color: C.muted, marginTop: 3 } }, "CUIT " + e.cuit + " · " + (e.actividad || ""))
            )
          ),
          React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 14 } },
            React.createElement(Tag, null, e.tipo),
            React.createElement("div", { style: { width: 28, height: 28, borderRadius: 7, background: C.surface, display: "flex", alignItems: "center", justifyContent: "center", color: C.muted } }, "›")
          )
        );
      })
    )
  );
}

// ─── EMPRESA DETALLE ─────────────────────────────────────────────
function EmpresaDetalle(props) {
  var empresa = props.empresa;
  var ejercicios = (empresa && empresa.ejercicios) || [];

  return React.createElement("div", { style: { maxWidth: 1060, margin: "0 auto", padding: "38px 36px" } },
    React.createElement("div", { onClick: function() { props.setPage("empresas"); }, style: { cursor: "pointer", color: C.muted, fontSize: 12, marginBottom: 10 } }, "‹ Volver a Empresas"),
    React.createElement("div", { style: { display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28 } },
      React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 16 } },
        React.createElement("div", { style: { width: 52, height: 52, borderRadius: 12, background: C.gold + "15", border: "1px solid " + C.gold + "30", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, color: C.gold } }, "◻"),
        React.createElement("div", null,
          React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 8, marginBottom: 4 } },
            React.createElement("h1", { style: { margin: 0, fontFamily: "'Playfair Display',serif", fontSize: 22, fontWeight: 700 } }, empresa ? empresa.razon_social : ""),
            React.createElement(Tag, { color: C.green }, "Activa")
          ),
          React.createElement("div", { style: { color: C.muted, fontSize: 13 } }, empresa ? "CUIT " + empresa.cuit : "")
        )
      ),
      React.createElement(Btn, { onClick: function() { props.setPage("upload"); } }, "+ Cargar saldos")
    ),
    React.createElement("div", { style: { fontSize: 11, color: C.muted, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 16 } }, "Ejercicios"),
    ejercicios.length === 0 && React.createElement(Card, { style: { textAlign: "center", padding: "30px 20px" } },
      React.createElement("div", { style: { color: C.muted, fontSize: 13 } }, "No hay ejercicios. Cargá saldos para crear el primero."),
      React.createElement(Btn, { onClick: function() { props.setPage("upload"); }, style: { marginTop: 12 } }, "⊞ Cargar saldos")
    ),
    React.createElement("div", { style: { position: "relative" } },
      ejercicios.length > 1 && React.createElement("div", { style: { position: "absolute", left: 19, top: 20, bottom: 20, width: 1, background: C.border } }),
      ejercicios.map(function(ej, i) {
        return React.createElement("div", { key: ej.id || i, style: { display: "flex", gap: 18, marginBottom: 14 } },
          React.createElement("div", { style: { width: 38, height: 38, borderRadius: "50%", background: i === 0 ? C.gold : C.surface, border: "2px solid " + (i === 0 ? C.gold : C.border), display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 700, color: i === 0 ? "#0A0E14" : C.muted, flexShrink: 0, zIndex: 1 } }, ej.numero),
          React.createElement(Card, { style: { flex: 1, padding: "16px 20px" } },
            React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 8, marginBottom: i === 0 ? 10 : 0 } },
              i === 0 && React.createElement(Tag, { color: C.blue }, "Actual"),
              React.createElement(Tag, { color: ej.estado === "emitido" ? C.green : C.amber }, ej.estado || "borrador"),
              React.createElement("span", { style: { fontWeight: 600, fontSize: 14 } }, "Ejercicio N° " + ej.numero)
            ),
            React.createElement("div", { style: { fontSize: 12, color: C.muted, marginBottom: i === 0 ? 10 : 0 } }, ej.fecha_inicio + " – " + ej.fecha_cierre),
            i === 0 && React.createElement("div", { style: { display: "flex", gap: 10 } },
              React.createElement(Btn, { variant: "ghost", small: true, onClick: function() { props.setPage("upload"); } }, "⊞ Cargar Cuentas y Saldos"),
              React.createElement(Btn, { small: true, onClick: function() { props.setPage("emision"); } }, "⚖ Emisión de Balance")
            )
          )
        );
      })
    ),
    React.createElement(Card, { style: { marginTop: 20 } },
      React.createElement("div", { style: { fontSize: 11, color: C.muted, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 16 } }, "Datos del registro"),
      React.createElement("div", { style: { display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 20 } },
        [
          ["Consejo Profesional", empresa && empresa.consejo_profesional || "—"],
          ["N° Inscripción",      empresa && empresa.nro_inscripcion || "—"],
          ["Fecha Inscripción",   empresa && empresa.fecha_inscripcion || "—"],
          ["Duración",            empresa && empresa.duracion_anos ? empresa.duracion_anos + " años" : "99 años"],
          ["Capital Suscripto",   fmt(empresa && empresa.capital_suscripto || 0)],
          ["Tipo",                empresa && empresa.tipo || "—"],
        ].map(function(kv) {
          return React.createElement("div", { key: kv[0] },
            React.createElement("div", { style: { fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 } }, kv[0]),
            React.createElement("div", { style: { fontSize: 14, fontWeight: 500 } }, kv[1])
          );
        })
      )
    )
  );
}

// ─── CUENTAS Y SALDOS ────────────────────────────────────────────
function UploadSaldos(props) {
  var _s = useState(props.saldos || []); var saldos = _s[0]; var setSaldos = _s[1];
  var _st = useState(props.saldos && props.saldos.length > 0 ? "loaded" : "idle"); var status = _st[0]; var setStatus = _st[1];
  var _dr = useState(false); var dragging = _dr[0]; var setDragging = _dr[1];
  var _md = useState("actual"); var modo = _md[0]; var setModo = _md[1];
  var _re = useState(null); var resultado = _re[0]; var setResultado = _re[1];
  var _vl = useState(null); var validacion = _vl[0]; var setValidacion = _vl[1];
  var _ld = useState(""); var loading = _ld[0]; var setLoading = _ld[1];
  var fileRef = useRef(null);

  useEffect(function() {
    if (saldos.length > 0) {
      setResultado(calcularLocal(saldos));
      callApi("/calcular", { numero: 1, fecha_inicio: "01/01/2025", fecha_cierre: "31/12/2025", cuentas: saldos }, props.token).then(function(r) {
        if (r.ok && r.data.resultado) {
          var d = r.data.resultado;
          setResultado(Object.assign({}, d, { total_activo: d.total_activo, total_pasivo: d.total_pasivo, total_pn: d.total_pn_con_resultado, resultado: d.resultado_ejercicio, activo_corriente: d.activo_corriente, activo_no_corriente: d.activo_no_corriente, pasivo_corriente: d.pasivo_corriente, total_ingresos: d.total_ingresos, total_gastos: d.total_gastos, rt54: d.clasificacion_rt54, variacion_ipc: d.variacion_ipc, recpam: d.recpam, cuadra: d.cuadra, diferencia: d.diferencia, margen: d.margen_neto, roa: d.roa, liquidez: d.liquidez_corriente, solvencia: d.solvencia }));
        }
      });
    }
  }, [saldos]);

  function parseFile(file) {
    var reader = new FileReader();
    reader.onload = function(e) {
      if (window.XLSX) {
        try {
          var wb = window.XLSX.read(e.target.result, { type: "array" });
          var ws = wb.Sheets[wb.SheetNames[0]];
          var rows = window.XLSX.utils.sheet_to_json(ws);
          var parsed = rows.map(function(r) {
            var debe = parseFloat(r["Debe"] || r["debe"] || 0);
            var haber = parseFloat(r["Haber"] || r["haber"] || 0);
            return {
              codigo: String(r["Código"] || r["Codigo"] || r["codigo"] || ""),
              descripcion: String(r["Descripción"] || r["Descripcion"] || r["descripcion"] || ""),
              debe: debe, haber: haber,
              saldo: parseFloat(r["Saldo"] || r["saldo"] || (debe - haber)),
            };
          }).filter(function(r) { return r.codigo; });
          setSaldos(parsed.length > 0 ? parsed : DEMO);
        } catch (err) {
          setSaldos(DEMO);
        }
      } else {
        setSaldos(DEMO);
      }
      setStatus("loaded");
    };
    reader.readAsArrayBuffer(file);
  }

  function handleValidar() {
    setLoading("val");
    callApi("/validar", { numero: 1, fecha_inicio: "01/01/2025", fecha_cierre: "31/12/2025", cuentas: saldos }, props.token).then(function(r) {
      if (r.ok) {
        setValidacion(r.data);
      } else {
        setValidacion({ cuadra: resultado && resultado.cuadra, errores: [], total_errores: 0, total_advertencias: 0 });
      }
      setLoading("");
    });
  }

  var B = resultado || (saldos.length > 0 ? calcularLocal(saldos) : null);

  return React.createElement("div", { style: { maxWidth: 1100, margin: "0 auto", padding: "38px 36px" } },
    React.createElement("div", { style: { display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 20 } },
      React.createElement(PageTitle, { sub: "Ejercicio contable" }, "Cuentas y Saldos"),
      status === "loaded" && React.createElement("div", { style: { display: "flex", gap: 10, alignItems: "center" } },
        React.createElement(Toggle, { value: modo, onChange: setModo, options: [{ value: "actual", label: "Original" }, { value: "reexpresado", label: "Reexpresado" }] }),
        React.createElement(Btn, { variant: "ghost", small: true, onClick: function() { setSaldos([]); setStatus("idle"); setResultado(null); setValidacion(null); } }, "Reemplazar"),
        React.createElement(Btn, { variant: "ghost", small: true, loading: loading === "val", onClick: handleValidar }, "◈ Validar"),
        React.createElement(Btn, { onClick: function() { props.setSaldos(saldos); props.setPage("emision"); } }, "⚖ Emisión de Balance")
      )
    ),

    validacion && React.createElement("div", { style: { marginBottom: 16 } },
      React.createElement(Alert, { type: validacion.cuadra ? "success" : "error" },
        validacion.cuadra ? "Balance cuadra · Partida doble verificada" : "Balance NO cuadra. Diferencia: " + fmt(validacion.diferencia || 0)
      ),
      (validacion.errores || []).map(function(err, i) {
        return React.createElement(Alert, { key: i, type: err.tipo === "error" ? "error" : "warning" },
          "[" + err.codigo + "] " + err.mensaje + (err.descripcion ? " — " + err.descripcion : "")
        );
      })
    ),

    status === "idle" && React.createElement("div", {
      onDrop: function(e) { e.preventDefault(); setDragging(false); if (e.dataTransfer.files[0]) parseFile(e.dataTransfer.files[0]); },
      onDragOver: function(e) { e.preventDefault(); setDragging(true); },
      onDragLeave: function() { setDragging(false); },
      onClick: function() { fileRef.current && fileRef.current.click(); },
      style: { border: "2px dashed " + (dragging ? C.gold : C.border), borderRadius: 16, padding: "64px 40px", textAlign: "center", cursor: "pointer", background: dragging ? C.gold + "08" : C.surface, transition: "all .2s" }
    },
      React.createElement("div", { style: { fontSize: 44, marginBottom: 14, opacity: 0.5 } }, "⊞"),
      React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 22, marginBottom: 8 } }, "Arrastrá tu archivo Excel aquí"),
      React.createElement("div", { style: { color: C.muted, fontSize: 13, marginBottom: 24 } }, "Formatos: .xlsx · .xls · .csv"),
      React.createElement("div", { style: { display: "flex", gap: 12, justifyContent: "center" } },
        React.createElement(Btn, {
          onClick: function(e) { e.stopPropagation(); fileRef.current && fileRef.current.click(); }
        }, "Seleccionar archivo"),
        React.createElement(Btn, {
          variant: "ghost",
          onClick: function(e) { e.stopPropagation(); setSaldos(DEMO); setStatus("loaded"); }
        }, "Usar datos de demo")
      ),
      React.createElement("input", { ref: fileRef, type: "file", accept: ".xlsx,.xls,.csv", style: { display: "none" }, onChange: function(e) { if (e.target.files[0]) parseFile(e.target.files[0]); } })
    ),

    status === "loaded" && B && React.createElement("div", null,
      React.createElement("div", { style: { display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" } },
        React.createElement("div", { style: { background: C.blue + "15", border: "1px solid " + C.blue + "33", borderRadius: 8, padding: "7px 14px", fontSize: 12 } },
          React.createElement("span", { style: { color: C.blue, fontWeight: 700, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em" } }, "RT 54 "),
          React.createElement("span", { style: { fontWeight: 600 } }, "Entidad " + (B.rt54 === "EP" ? "Pequeña" : B.rt54 === "EM" ? "Mediana" : "Restante") + " (" + B.rt54 + ")")
        ),
        React.createElement("div", { style: { background: C.amber + "15", border: "1px solid " + C.amber + "33", borderRadius: 8, padding: "7px 14px", fontSize: 12, color: C.amber } },
          "IPC: ", React.createElement("strong", null, B.variacion_ipc + "%")
        )
      ),
      React.createElement("div", { style: { display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 20 } },
        React.createElement(Stat, { label: "Activo", value: fmt(B.total_activo), color: C.green, icon: "+" }),
        React.createElement(Stat, { label: "Pasivo", value: fmt(B.total_pasivo), color: C.red, icon: "−" }),
        React.createElement(Stat, { label: "Patrimonio Neto", value: fmt(B.total_pn), color: C.blue, icon: "=" }),
        React.createElement(Stat, { label: "Resultado", value: fmt(B.resultado), color: B.resultado >= 0 ? C.green : C.red, icon: "◈" })
      ),
      React.createElement(Card, null,
        React.createElement("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 } },
          React.createElement("div", null,
            React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 16, fontWeight: 600 } }, "Sumas y Saldos"),
            React.createElement("div", { style: { fontSize: 12, color: C.muted, marginTop: 3 } },
              saldos.length + " cuentas · ",
              React.createElement("span", { style: { color: B.cuadra ? C.green : C.red } }, B.cuadra ? "● Balanceado" : "● Desbalanceado")
            )
          )
        ),
        React.createElement("div", { style: { overflowX: "auto", maxHeight: 460, overflowY: "auto" } },
          React.createElement("table", { style: { width: "100%", borderCollapse: "collapse", fontSize: 12 } },
            React.createElement("thead", { style: { position: "sticky", top: 0, background: C.card, zIndex: 1 } },
              React.createElement("tr", { style: { borderBottom: "1px solid " + C.border } },
                ["Código", "Descripción", "Tipo", "Rubro", "Subrubro", "Debe", "Haber"].map(function(h, i) {
                  return React.createElement("th", { key: h, style: { textAlign: i > 4 ? "right" : "left", padding: "8px 10px", color: C.muted, fontWeight: 600, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.04em", whiteSpace: "nowrap" } }, h);
                })
              )
            ),
            React.createElement("tbody", null,
              saldos.map(function(r, i) {
                return React.createElement("tr", {
                  key: i,
                  style: { borderBottom: "1px solid " + C.border + "18" },
                  onMouseEnter: function(e) { e.currentTarget.style.background = "#ffffff06"; },
                  onMouseLeave: function(e) { e.currentTarget.style.background = "transparent"; },
                },
                  React.createElement("td", { style: { padding: "7px 10px", fontFamily: "monospace", fontSize: 11, color: C.muted, whiteSpace: "nowrap" } }, r.codigo),
                  React.createElement("td", { style: { padding: "7px 10px", fontSize: 13 } }, r.descripcion),
                  React.createElement("td", { style: { padding: "7px 10px" } }, React.createElement(TipoBadge, { tipo: r.tipo || getTipo(r.codigo) })),
                  React.createElement("td", { style: { padding: "7px 10px", fontSize: 11, color: C.muted, whiteSpace: "nowrap" } }, r.rubro || getRub(r.codigo)),
                  React.createElement("td", { style: { padding: "7px 10px", fontSize: 11, color: C.muted, maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }, r.subrubro || getSub(r.codigo)),
                  React.createElement("td", { style: { padding: "7px 10px", textAlign: "right", color: r.debe ? C.text : C.hint, fontFamily: "monospace", fontSize: 11 } }, r.debe ? fmtN(r.debe) : "$ 0,00"),
                  React.createElement("td", { style: { padding: "7px 10px", textAlign: "right", color: r.haber ? C.text : C.hint, fontFamily: "monospace", fontSize: 11 } }, r.haber ? fmtN(r.haber) : "$ 0,00")
                );
              })
            )
          )
        )
      )
    )
  );
}

// ─── EMISIÓN DE BALANCE ───────────────────────────────────────────
function EmisionBalance(props) {
  var saldos = props.saldos || DEMO;
  var emp = props.empresa || { razon_social: "Empresa Demo", cuit: "30-00000000-0", tipo: "S.A.", actividad: "—", domicilio: "—", capitalSuscripto: 0 };
  var B = calcularLocal(saldos);
  var _sec = useState("caratula"); var sec = _sec[0]; var setSec = _sec[1];
  var _lp = useState(false); var loadingPDF = _lp[0]; var setLoadingPDF = _lp[1];
  var _msg = useState(null); var msg = _msg[0]; var setMsg = _msg[1];
  var _if = useState({ juan: true, nahuel: true }); var inclFirmas = _if[0]; var setInclFirmas = _if[1];

  var SECCIONES = [
    { id: "caratula", label: "Carátula" },
    { id: "notas",    label: "Notas I" },
    { id: "esp",      label: "A. Vto." },
    { id: "ame",      label: "A. ME" },
    { id: "bsuso",    label: "A. Bs. Uso" },
    { id: "intang",   label: "A. Intang." },
    { id: "cmv",      label: "A. CMV" },
    { id: "auditor",  label: "Inf. Auditor" },
    { id: "exportar", label: "Exportar" },
  ];

  function emitirPDF() {
    setLoadingPDF(true); setMsg(null);
    var firmantes = [];
    if (inclFirmas.juan) firmantes.push({ nombre: "Juan García", titulo: "Contador Público" });
    if (inclFirmas.nahuel) firmantes.push({ nombre: "Nahuel López", titulo: "Síndico" });
    var payload = {
      empresa: { razon_social: emp.razon_social || emp.razonSocial, cuit: emp.cuit, tipo: emp.tipo, actividad: emp.actividad, domicilio: emp.domicilio || "—", capital_suscripto: emp.capital_suscripto || emp.capitalSuscripto || 0, consejo_profesional: emp.consejo_profesional || "CPCE Buenos Aires", nro_inscripcion: emp.nro_inscripcion || "" },
      ejercicio: { numero: 1, fecha_inicio: "01/01/2025", fecha_cierre: "31/12/2025", cuentas: saldos },
      firmantes: firmantes, incluir_notas: true,
    };
    callApiBin("/emitir-balance-inline", payload, props.token).then(function(r) {
      if (r) {
        downloadBlob(r.blob, "LIBRA_balance.pdf");
        setMsg({ type: "success", text: "✓ PDF generado" + (r.creditos ? " · Créditos restantes: " + r.creditos : " — Gratuito 🎉") });
      } else {
        setMsg({ type: "warning", text: "API no disponible. Configurá la URL en Configuración → General." });
      }
      setLoadingPDF(false);
    });
  }

  function renderLinea(label, value, opts) {
    var gold = opts && opts.gold;
    var bold = opts && opts.bold;
    var indent = opts && opts.indent;
    var sep = opts && opts.sep;
    return React.createElement("div", {
      style: {
        display: "flex", justifyContent: "space-between",
        padding: sep ? "10px 0" : "4px 0",
        paddingLeft: indent ? 14 : 0,
        borderTop: sep ? "1px solid " + (gold ? C.gold + "44" : C.border) : "none",
        marginTop: sep ? 4 : 0,
      }
    },
      React.createElement("span", { style: { fontSize: 13, fontWeight: (bold || gold) ? 700 : 400, color: gold ? C.gold : bold ? C.text : C.muted, fontFamily: gold ? "'Playfair Display',serif" : "inherit" } }, label),
      React.createElement("span", { style: { fontSize: 13, fontWeight: (bold || gold) ? 700 : 400, color: gold ? C.gold : C.text, fontFamily: "monospace" } }, value)
    );
  }

  function renderSection() {
    if (sec === "caratula") {
      return React.createElement("div", null,
        React.createElement("div", { style: { textAlign: "center", borderBottom: "1px solid " + C.border, paddingBottom: 22, marginBottom: 24 } },
          React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 22, fontWeight: 700, color: C.gold, marginBottom: 6 } }, "ESTADOS CONTABLES"),
          React.createElement("div", { style: { fontSize: 11, color: C.muted, letterSpacing: "0.1em", textTransform: "uppercase" } }, "Al 31/12/2025 — Moneda homogénea")
        ),
        React.createElement("div", { style: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 } },
          [
            ["Denominación del Ente", emp.razon_social || emp.razonSocial],
            ["CUIT N°", emp.cuit],
            ["Domicilio legal", emp.domicilio || "—"],
            ["Actividad principal", emp.actividad || "—"],
            ["Tipo de entidad", emp.tipo || "—"],
            ["Ejercicio N°", "1"],
            ["Período", "1/1/2025 – 31/12/2025"],
            ["Unidad de medida", "Moneda homogénea"],
            ["Clasificación RT 54", "Entidad " + (B.rt54 === "EP" ? "Pequeña" : B.rt54 === "EM" ? "Mediana" : "Restante") + " (" + B.rt54 + ")"],
            ["IPC ejercicio", B.variacion_ipc + "%"],
          ].map(function(kv) {
            return React.createElement("div", { key: kv[0], style: { borderBottom: "1px solid " + C.border + "33", paddingBottom: 10 } },
              React.createElement("div", { style: { fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 3 } }, kv[0]),
              React.createElement("div", { style: { fontSize: 14, fontWeight: 500 } }, kv[1])
            );
          })
        )
      );
    }

    if (sec === "esp") {
      return React.createElement("div", null,
        React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 18, fontWeight: 700, color: C.gold, marginBottom: 4 } }, "Estado de Situación Patrimonial"),
        React.createElement("div", { style: { fontSize: 11, color: C.muted, marginBottom: 20 } }, "Al 31/12/2025 · Moneda homogénea (Nota 1.3)"),
        React.createElement("div", { style: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 } },
          React.createElement("div", null,
            React.createElement("div", { style: { fontSize: 10, fontWeight: 700, color: C.blue, letterSpacing: "0.09em", textTransform: "uppercase", padding: "14px 0 6px", borderTop: "1px solid " + C.blue + "44" } }, "ACTIVO"),
            React.createElement("div", { style: { fontSize: 10, fontWeight: 600, color: C.muted, letterSpacing: "0.07em", textTransform: "uppercase", padding: "10px 0 4px" } }, "Activo Corriente"),
            saldos.filter(function(r) { return r.codigo.startsWith("1.1"); }).map(function(r) { return renderLinea(r.descripcion, fmt(Math.abs(r.saldo)), { indent: true }); }),
            renderLinea("Total Activo Corriente", fmt(B.activo_corriente), { bold: true, sep: true }),
            React.createElement("div", { style: { fontSize: 10, fontWeight: 600, color: C.muted, letterSpacing: "0.07em", textTransform: "uppercase", padding: "10px 0 4px" } }, "Activo No Corriente"),
            saldos.filter(function(r) { return r.codigo.startsWith("1.2"); }).map(function(r) { return renderLinea(r.descripcion, fmt(Math.abs(r.saldo)), { indent: true }); }),
            renderLinea("Total Activo No Corriente", fmt(B.activo_no_corriente), { bold: true, sep: true }),
            renderLinea("TOTAL ACTIVO", fmt(B.total_activo), { gold: true, sep: true })
          ),
          React.createElement("div", null,
            React.createElement("div", { style: { fontSize: 10, fontWeight: 700, color: C.red, letterSpacing: "0.09em", textTransform: "uppercase", padding: "14px 0 6px", borderTop: "1px solid " + C.red + "44" } }, "PASIVO"),
            React.createElement("div", { style: { fontSize: 10, fontWeight: 600, color: C.muted, letterSpacing: "0.07em", textTransform: "uppercase", padding: "10px 0 4px" } }, "Pasivo Corriente"),
            saldos.filter(function(r) { return r.codigo.startsWith("2.1"); }).map(function(r) { return renderLinea(r.descripcion, fmt(Math.abs(r.saldo)), { indent: true }); }),
            renderLinea("Total Pasivo Corriente", fmt(B.pasivo_corriente), { bold: true, sep: true }),
            renderLinea("TOTAL PASIVO", fmt(B.total_pasivo), { gold: true, sep: true }),
            React.createElement("div", { style: { fontSize: 10, fontWeight: 700, color: C.green, letterSpacing: "0.09em", textTransform: "uppercase", padding: "14px 0 6px", borderTop: "1px solid " + C.green + "44" } }, "PATRIMONIO NETO"),
            saldos.filter(function(r) { return r.codigo.startsWith("3."); }).map(function(r) { return renderLinea(r.descripcion, fmt(Math.abs(r.saldo)), { indent: true }); }),
            renderLinea("Resultado del Ejercicio", fmt(B.resultado), { indent: true }),
            renderLinea("TOTAL PATRIMONIO NETO", fmt(B.total_pn), { gold: true, sep: true }),
            React.createElement("div", { style: { marginTop: 12, background: (B.cuadra ? C.green : C.red) + "15", border: "1px solid " + (B.cuadra ? C.green : C.red) + "44", borderRadius: 6, padding: "8px 12px", fontSize: 11, color: B.cuadra ? C.green : C.red } },
              B.cuadra ? "✓ Balance cuadra — Activo = Pasivo + PN" : "✗ Diferencia: " + fmt(B.diferencia)
            )
          )
        )
      );
    }

    if (sec === "ame") {
      return React.createElement("div", null,
        React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 18, fontWeight: 700, color: C.gold, marginBottom: 4 } }, "Estado de Resultados"),
        React.createElement("div", { style: { fontSize: 11, color: C.muted, marginBottom: 20 } }, "Por el ejercicio finalizado el 31/12/2025 · Moneda homogénea (Nota 1.3)"),
        React.createElement("div", { style: { fontSize: 10, fontWeight: 700, color: C.green, letterSpacing: "0.09em", textTransform: "uppercase", padding: "14px 0 6px", borderTop: "1px solid " + C.green + "44" } }, "INGRESOS"),
        saldos.filter(function(r) { return r.codigo.startsWith("4.1"); }).map(function(r) { return renderLinea(r.descripcion, fmt(Math.abs(r.saldo)), { indent: true }); }),
        renderLinea("Total Ingresos", fmt(B.total_ingresos), { bold: true, sep: true }),
        React.createElement("div", { style: { fontSize: 10, fontWeight: 700, color: C.red, letterSpacing: "0.09em", textTransform: "uppercase", padding: "14px 0 6px", borderTop: "1px solid " + C.red + "44" } }, "COSTOS Y GASTOS"),
        saldos.filter(function(r) { return r.codigo.startsWith("4.2"); }).map(function(r) { return renderLinea(r.descripcion, "(" + fmt(r.saldo) + ")", { indent: true }); }),
        renderLinea("Total Costos y Gastos", "(" + fmt(B.total_gastos) + ")", { bold: true, sep: true }),
        renderLinea((B.resultado >= 0 ? "GANANCIA" : "PÉRDIDA") + " DEL EJERCICIO", fmt(Math.abs(B.resultado)), { gold: true, sep: true }),
        React.createElement("div", { style: { marginTop: 20, background: C.surface, borderRadius: 8, padding: "14px 18px" } },
          React.createElement("div", { style: { fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 } }, "Indicadores financieros"),
          [
            ["Margen neto", (B.margen || 0).toFixed(1) + "%", B.resultado >= 0 ? C.green : C.red],
            ["ROA", (B.roa || 0).toFixed(1) + "%", C.blue],
            ["Liquidez corriente", (B.liquidez || 0).toFixed(2) + "x", C.amber],
            ["Solvencia", (B.solvencia || 0).toFixed(2) + "x", C.gold],
            ["RECPAM", fmt(B.recpam || 0), C.muted],
            ["Variación IPC", B.variacion_ipc + "%", C.blue],
          ].map(function(item) {
            return React.createElement("div", { key: item[0], style: { display: "flex", justifyContent: "space-between", fontSize: 12, padding: "6px 0", borderBottom: "1px solid " + C.border + "22" } },
              React.createElement("span", { style: { color: C.muted } }, item[0]),
              React.createElement("span", { style: { fontWeight: 700, color: item[2] } }, item[1])
            );
          })
        )
      );
    }

    if (sec === "notas") {
      return React.createElement("div", null,
        React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 18, fontWeight: 700, color: C.gold, marginBottom: 20 } }, "Notas a los Estados Contables"),
        [
          { n: "1.", t: "Notas generales", items: [
            { n: "1.1.", t: "Bases de preparación", c: "Los presentes estados contables están expresados en pesos en moneda homogénea de cierre y han sido preparados de conformidad con la Resolución Técnica N° 54 — T.O. RT 59, emitida por la FACPCE." },
            { n: "1.2.", t: "Clasificación de la entidad", c: "La entidad reviste el carácter de Entidad " + (B.rt54 === "EP" ? "Pequeña" : B.rt54 === "EM" ? "Mediana" : "Restante") + " (" + B.rt54 + ") según RT 54." },
            { n: "1.3.", t: "Unidad de medida", c: "Los estados contables fueron preparados en moneda homogénea. La variación del índice FACPCE/IPC fue del " + B.variacion_ipc + "% en el ejercicio." },
          ]},
          { n: "2.", t: "Notas al ESP", items: [
            { n: "2.1.", t: "Caja y bancos", c: "El efectivo y saldos bancarios se miden a valor nominal." },
            { n: "2.2.", t: "Bienes de cambio", c: "Los bienes de cambio se miden a costo de adquisición reexpresado a moneda de cierre conforme Nota 1.3." },
          ]},
        ].map(function(sg) {
          return React.createElement("div", { key: sg.n, style: { marginBottom: 24 } },
            React.createElement("div", { style: { fontSize: 14, fontWeight: 700, marginBottom: 10, paddingBottom: 6, borderBottom: "1px solid " + C.border } }, sg.n + " " + sg.t),
            sg.items.map(function(it) {
              return React.createElement("div", { key: it.n, style: { marginBottom: 12, paddingLeft: 16 } },
                React.createElement("div", { style: { fontSize: 13, fontWeight: 600, marginBottom: 4 } }, it.n + " " + it.t),
                React.createElement("div", { style: { fontSize: 13, color: C.muted, lineHeight: 1.7 } }, it.c)
              );
            })
          );
        })
      );
    }

    if (sec === "auditor") {
      return React.createElement("div", null,
        React.createElement("div", { style: { textAlign: "center", marginBottom: 24, borderBottom: "1px solid " + C.border, paddingBottom: 20 } },
          React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 18, fontWeight: 700, color: C.gold } }, "Informe del Auditor Independiente")
        ),
        React.createElement("div", { style: { fontSize: 13, lineHeight: 1.9, color: C.muted } },
          React.createElement("p", { style: { marginBottom: 14 } },
            React.createElement("strong", { style: { color: C.text } }, "Señores"), React.createElement("br", null),
            "Presidente y directores de ", React.createElement("strong", { style: { color: C.text } }, emp.razon_social || emp.razonSocial), React.createElement("br", null),
            "CUIT N° " + emp.cuit
          ),
          React.createElement("p", { style: { marginBottom: 12 } }, "He auditado los estados contables adjuntos de ", React.createElement("strong", { style: { color: C.text } }, emp.razon_social || emp.razonSocial), ", que comprenden el estado de situación patrimonial al 31/12/2025, el estado de resultados y las notas correspondientes al ejercicio finalizado en dicha fecha."),
          React.createElement("p", { style: { marginBottom: 20 } }, "En mi opinión, los estados contables presentan razonablemente la situación patrimonial de la entidad, de conformidad con las normas contables profesionales argentinas."),
          React.createElement("div", { style: { paddingTop: 20, borderTop: "1px solid " + C.border, display: "flex", justifyContent: "space-evenly" } },
            [inclFirmas.juan && { n: "Juan García", t: "Contador Público" }, inclFirmas.nahuel && { n: "Nahuel López", t: "Síndico" }].filter(Boolean).map(function(f) {
              return React.createElement("div", { key: f.n, style: { textAlign: "center" } },
                React.createElement("div", { style: { width: 80, borderTop: "1px solid " + C.muted, margin: "0 auto 8px" } }),
                React.createElement("div", { style: { fontSize: 12, fontWeight: 600, color: C.text } }, f.n),
                React.createElement("div", { style: { fontSize: 10, color: C.muted } }, f.t)
              );
            })
          )
        )
      );
    }

    if (sec === "exportar") {
      var user = props.user;
      return React.createElement("div", null,
        React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 18, fontWeight: 700, color: C.gold, marginBottom: 24 } }, "Configurar exportación"),
        msg && React.createElement(Alert, { type: msg.type }, msg.text),
        user && user.es_creator
          ? React.createElement(Alert, { type: "success" }, "Sos el creador — emisión gratuita e ilimitada 🎉")
          : React.createElement(Alert, { type: "info" }, "Tenés " + ((user && user.creditos) || 0) + " crédito(s). Cada emisión consume 1 crédito."),
        React.createElement("div", { style: { marginBottom: 22, paddingBottom: 20, borderBottom: "1px solid " + C.border } },
          React.createElement("div", { style: { fontSize: 11, color: C.muted, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14 } }, "Firmas en EECC"),
          React.createElement("label", { style: { display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, marginBottom: 10 } },
            React.createElement("input", { type: "checkbox", checked: inclFirmas.juan, onChange: function(e) { setInclFirmas({ juan: e.target.checked, nahuel: inclFirmas.nahuel }); }, style: { accentColor: C.gold } }),
            "Contador — Juan García"
          ),
          React.createElement("label", { style: { display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13 } },
            React.createElement("input", { type: "checkbox", checked: inclFirmas.nahuel, onChange: function(e) { setInclFirmas({ juan: inclFirmas.juan, nahuel: e.target.checked }); }, style: { accentColor: C.gold } }),
            "Síndico — Nahuel López"
          )
        ),
        React.createElement(Btn, {
          style: { width: "100%", padding: "13px", justifyContent: "center" },
          loading: loadingPDF,
          disabled: !user || (!user.es_creator && (user.creditos || 0) < 1),
          onClick: emitirPDF,
        }, user && user.es_creator ? "📄 Generar PDF (gratuito ∞)" : "📄 Generar PDF (consume 1 crédito)")
      );
    }

    // Placeholders for other sections
    return React.createElement("div", null,
      React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 18, fontWeight: 700, color: C.gold, marginBottom: 4 } }, SECCIONES.find(function(s) { return s.id === sec; }) ? SECCIONES.find(function(s) { return s.id === sec; }).label : "Sección"),
      React.createElement("div", { style: { textAlign: "center", padding: "50px 20px", border: "1px dashed " + C.border, borderRadius: 10, color: C.muted, fontSize: 13, marginTop: 20 } }, "Esta sección se genera automáticamente desde los saldos cargados.")
    );
  }

  return React.createElement("div", { style: { maxWidth: 1100, margin: "0 auto", padding: "28px 36px" } },
    React.createElement("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 } },
      React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: C.muted } },
        React.createElement("span", { onClick: function() { props.setPage("empresa"); }, style: { cursor: "pointer" } }, "‹ Empresa"),
        React.createElement("span", { style: { color: C.border } }, "·"),
        React.createElement("span", { style: { color: C.text, fontWeight: 600 } }, emp.razon_social || emp.razonSocial),
        React.createElement("span", { style: { color: C.border } }, "·"),
        React.createElement("span", null, "Emisión de Balance"),
        props.user && props.user.es_creator && React.createElement(Tag, { color: C.amber }, "Creator — Gratis")
      ),
      React.createElement(Btn, { small: true, variant: "ghost", onClick: function() { props.setPage("upload"); } }, "◈ Validar saldos")
    ),
    React.createElement("div", { style: { background: C.surface, border: "1px solid " + C.border, borderRadius: 10, padding: "12px 22px", display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 20, marginBottom: 18, fontSize: 12 } },
      [["Empresa", emp.razon_social || emp.razonSocial || "—"], ["Ejercicio N°", "1"], ["Fecha Inicio", "01/01/2025"], ["Fecha Cierre", "31/12/2025"]].map(function(kv) {
        return React.createElement("div", { key: kv[0] },
          React.createElement("div", { style: { color: C.muted, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 3 } }, kv[0]),
          React.createElement("div", { style: { fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }, kv[1])
        );
      })
    ),
    React.createElement("div", { style: { display: "grid", gridTemplateColumns: "160px 1fr", gap: 14, alignItems: "start" } },
      React.createElement("div", { style: { background: C.surface, border: "1px solid " + C.border, borderRadius: 10, overflow: "hidden", position: "sticky", top: 16 } },
        SECCIONES.map(function(s) {
          return React.createElement("div", {
            key: s.id,
            onClick: function() { setSec(s.id); },
            style: {
              padding: "9px 14px", cursor: "pointer", fontSize: 12,
              background: sec === s.id ? C.gold + "18" : "transparent",
              color: sec === s.id ? C.gold : s.id === "exportar" ? C.green : C.muted,
              fontWeight: sec === s.id ? 600 : s.id === "exportar" ? 600 : 400,
              borderLeft: sec === s.id ? "3px solid " + C.gold : s.id === "exportar" ? "3px solid " + C.green + "33" : "3px solid transparent",
              transition: "all .15s",
            },
            onMouseEnter: function(e) { if (sec !== s.id) e.currentTarget.style.background = "#ffffff08"; },
            onMouseLeave: function(e) { if (sec !== s.id) e.currentTarget.style.background = "transparent"; },
          }, s.label, s.id === "exportar" && React.createElement("span", { style: { marginLeft: 4, fontSize: 9, color: C.green } }, "↓"));
        })
      ),
      React.createElement(Card, { style: { minHeight: 500 } }, renderSection())
    )
  );
}

// ─── CONFIG ──────────────────────────────────────────────────────
function Config(props) {
  var user = props.user;
  var _tab = useState("general"); var tab = _tab[0]; var setTab = _tab[1];
  var _sel = useState(2); var selected = _sel[0]; var setSelected = _sel[1];
  var _ld = useState(false); var loading = _ld[0]; var setLoading = _ld[1];
  var packs = [
    { n: 1,  precio: 49999,   unit: 49999  },
    { n: 10, precio: 449990,  unit: 44999  },
    { n: 25, precio: 1124975, unit: 44999, popular: true },
    { n: 50, precio: 1999950, unit: 39999  },
  ];

  function comprar() {
    setLoading(true);
    callApi("/creditos/comprar", { pack: String(packs[selected].n), email_mp: user ? user.email : "" }, props.token).then(function(r) {
      if (r.ok && r.data.checkout_url) window.open(r.data.checkout_url, "_blank");
      setLoading(false);
    });
  }

  return React.createElement("div", { style: { maxWidth: 1060, margin: "0 auto", padding: "38px 36px" } },
    React.createElement(PageTitle, { sub: "Ajustes" }, "Configuración"),
    React.createElement("div", { style: { display: "flex", gap: 3, marginBottom: 28, background: C.surface, borderRadius: 10, padding: 4, width: "fit-content", border: "1px solid " + C.border } },
      ["General", "Créditos", "Firmantes"].map(function(t) {
        return React.createElement("div", {
          key: t,
          onClick: function() { setTab(t.toLowerCase()); },
          style: { padding: "8px 18px", borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 500, background: tab === t.toLowerCase() ? C.gold : "transparent", color: tab === t.toLowerCase() ? "#0A0E14" : C.muted, transition: "all .15s" }
        }, t);
      })
    ),
    tab === "general" && React.createElement("div", { style: { maxWidth: 520 } },
      React.createElement(Card, { style: { marginBottom: 18 } },
        React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 16, fontWeight: 600, marginBottom: 20 } }, "Cuenta"),
        React.createElement(Input, { label: "Nombre", value: user ? user.nombre : "", readOnly: true }),
        React.createElement(Input, { label: "Email", value: user ? user.email : "", readOnly: true }),
        user && user.es_creator && React.createElement("div", { style: { background: C.gold + "10", border: "1px solid " + C.gold + "30", borderRadius: 8, padding: "10px 14px", marginBottom: 16 } },
          React.createElement("div", { style: { fontSize: 11, color: C.goldD, fontWeight: 600, marginBottom: 2 } }, "Rol"),
          React.createElement("div", { style: { fontWeight: 600, color: C.gold } }, "Creator — Acceso ilimitado y gratuito ∞")
        ),
        React.createElement("div", { style: { marginBottom: 16 } },
          React.createElement("div", { style: { fontSize: 11, color: C.muted, marginBottom: 5, fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase" } }, "URL de la API"),
          React.createElement("input", { defaultValue: API_URL, style: { width: "100%", background: C.surface, border: "1px solid " + C.border, borderRadius: 8, padding: "10px 14px", color: C.text, fontFamily: "monospace", fontSize: 12, outline: "none", boxSizing: "border-box" } }),
          React.createElement("div", { style: { fontSize: 10, color: C.muted, marginTop: 4 } }, "Gratis: Railway.app o Render.com")
        )
      ),
      React.createElement(Btn, { variant: "danger", onClick: props.onLogout }, "Cerrar sesión")
    ),
    tab === "créditos" && React.createElement("div", { style: { maxWidth: 660 } },
      user && user.es_creator
        ? React.createElement(Card, { style: { textAlign: "center", padding: "40px" } },
            React.createElement("div", { style: { fontSize: 48, fontFamily: "'Playfair Display',serif", fontWeight: 700, color: C.gold, marginBottom: 8 } }, "∞"),
            React.createElement("div", { style: { fontSize: 16, fontWeight: 600, marginBottom: 6 } }, "Creador — Ilimitado y gratuito"),
            React.createElement("div", { style: { fontSize: 13, color: C.muted } }, "Como creador de LIBRA, nunca necesitás comprar créditos.")
          )
        : React.createElement("div", null,
            React.createElement(Card, { style: { marginBottom: 18, display: "flex", alignItems: "center", gap: 20 } },
              React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 48, fontWeight: 700, color: C.gold, lineHeight: 1 } }, (user && user.creditos) || 0),
              React.createElement("div", null,
                React.createElement("div", { style: { fontSize: 15, fontWeight: 600 } }, "Créditos disponibles"),
                React.createElement("div", { style: { fontSize: 12, color: C.muted, marginTop: 3 } }, "Cada emisión de balance consume 1 crédito")
              )
            ),
            React.createElement(Card, null,
              React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 16, fontWeight: 600, marginBottom: 20 } }, "Comprar créditos"),
              React.createElement("div", { style: { display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, marginBottom: 20 } },
                packs.map(function(p, i) {
                  return React.createElement("div", {
                    key: p.n,
                    onClick: function() { setSelected(i); },
                    style: { border: "2px solid " + (selected === i ? C.gold : C.border), borderRadius: 12, padding: "16px 10px", textAlign: "center", cursor: "pointer", background: selected === i ? C.gold + "10" : C.surface, position: "relative", transition: "all .15s" }
                  },
                    p.popular && React.createElement("div", { style: { position: "absolute", top: -10, left: "50%", transform: "translateX(-50%)", background: C.gold, color: "#0A0E14", fontSize: 8, fontWeight: 700, padding: "2px 10px", borderRadius: 20, textTransform: "uppercase", whiteSpace: "nowrap" } }, "Popular"),
                    React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 26, fontWeight: 700, color: selected === i ? C.gold : C.text, lineHeight: 1 } }, p.n),
                    React.createElement("div", { style: { fontSize: 10, color: C.muted, marginBottom: 10 } }, p.n > 1 ? "créditos" : "crédito"),
                    React.createElement("div", { style: { fontWeight: 700, fontSize: 12 } }, fmt(p.precio)),
                    React.createElement("div", { style: { fontSize: 10, color: C.muted } }, fmt(p.unit) + "/c.")
                  );
                })
              ),
              React.createElement(Input, { label: "Email de Mercado Pago", value: (user && user.email) || "", readOnly: true }),
              React.createElement(Btn, { loading: loading, style: { width: "100%", padding: "12px", justifyContent: "center" }, onClick: comprar }, "Pagar con Mercado Pago →")
            )
          )
    ),
    tab === "firmantes" && React.createElement(Card, { style: { maxWidth: 520, textAlign: "center", padding: "50px 30px" } },
      React.createElement("div", { style: { fontSize: 32, marginBottom: 14, opacity: 0.4 } }, "◈"),
      React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 16, fontWeight: 600, marginBottom: 8 } }, "Firmantes del estudio"),
      React.createElement("div", { style: { fontSize: 13, color: C.muted, marginBottom: 20, lineHeight: 1.7 } }, "Los firmantes aparecen al pie de los balances emitidos."),
      React.createElement(Btn, null, "+ Agregar firmante")
    )
  );
}

// ─── ADMIN ────────────────────────────────────────────────────────
function AdminPanel(props) {
  var _st = useState(null); var stats = _st[0]; var setStats = _st[1];
  var _us = useState([]); var usuarios = _us[0]; var setUsuarios = _us[1];
  var _tab = useState("stats"); var tab = _tab[0]; var setTab = _tab[1];
  var _ld = useState(true); var loading = _ld[0]; var setLoading = _ld[1];

  useEffect(function() {
    callApi("/admin/stats", null, props.token, "GET").then(function(r) { if (r.ok) setStats(r.data); });
    callApi("/admin/usuarios", null, props.token, "GET").then(function(r) { if (r.ok) { setUsuarios(r.data.usuarios || []); setLoading(false); } });
  }, []);

  function setCreditos(uid, n) {
    callApi("/admin/usuarios/" + uid + "/creditos", { creditos: parseInt(n) }, props.token, "PUT").then(function() {
      setUsuarios(usuarios.map(function(u) { return u.id === uid ? Object.assign({}, u, { creditos: parseInt(n) }) : u; }));
    });
  }

  return React.createElement("div", { style: { maxWidth: 1100, margin: "0 auto", padding: "38px 36px" } },
    React.createElement("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 } },
      React.createElement(PageTitle, { sub: "Panel de control" }, "Admin — Creator"),
      React.createElement(Tag, { color: C.amber }, "CREATOR ACCESS")
    ),
    React.createElement("div", { style: { display: "flex", gap: 3, marginBottom: 24, background: C.surface, borderRadius: 10, padding: 4, width: "fit-content", border: "1px solid " + C.border } },
      ["Stats", "Usuarios"].map(function(t) {
        return React.createElement("div", { key: t, onClick: function() { setTab(t.toLowerCase()); }, style: { padding: "8px 18px", borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 500, background: tab === t.toLowerCase() ? C.gold : "transparent", color: tab === t.toLowerCase() ? "#0A0E14" : C.muted, transition: "all .15s" } }, t);
      })
    ),
    tab === "stats" && stats && React.createElement("div", null,
      React.createElement("div", { style: { display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 16 } },
        React.createElement(Stat, { label: "Total usuarios", value: stats.total_usuarios, icon: "◉", color: C.gold }),
        React.createElement(Stat, { label: "Empresas activas", value: stats.total_empresas, icon: "◻", color: C.blue }),
        React.createElement(Stat, { label: "Balances emitidos", value: stats.balances_emitidos, icon: "⊞", color: C.green }),
        React.createElement(Stat, { label: "Nuevos hoy", value: stats.nuevos_hoy, icon: "★", color: C.amber })
      ),
      React.createElement("div", { style: { display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14 } },
        React.createElement(Stat, { label: "Total estudios", value: stats.total_estudios, icon: "◈", color: C.blue }),
        React.createElement(Stat, { label: "Créditos vendidos", value: stats.creditos_vendidos || 0, icon: "◈", color: C.green }),
        React.createElement(Stat, { label: "Ingresos totales", value: stats.ingresos_total ? fmt(stats.ingresos_total) : "$0", icon: "◈", color: C.gold })
      )
    ),
    tab === "usuarios" && React.createElement(Card, null,
      React.createElement("div", { style: { fontFamily: "'Playfair Display',serif", fontSize: 16, fontWeight: 600, marginBottom: 18 } }, "Usuarios (" + usuarios.length + ")"),
      loading && React.createElement("div", { style: { textAlign: "center", padding: 40, color: C.muted } }, "Cargando..."),
      React.createElement("div", { style: { overflowX: "auto" } },
        React.createElement("table", { style: { width: "100%", borderCollapse: "collapse", fontSize: 12 } },
          React.createElement("thead", null,
            React.createElement("tr", { style: { borderBottom: "1px solid " + C.border } },
              ["ID", "Nombre", "Email", "Rol", "Plan", "Créditos", "Registrado"].map(function(h) {
                return React.createElement("th", { key: h, style: { padding: "8px 10px", textAlign: "left", color: C.muted, fontWeight: 600, fontSize: 10, textTransform: "uppercase", whiteSpace: "nowrap" } }, h);
              })
            )
          ),
          React.createElement("tbody", null,
            usuarios.map(function(u) {
              return React.createElement("tr", {
                key: u.id,
                style: { borderBottom: "1px solid " + C.border + "22" },
                onMouseEnter: function(e) { e.currentTarget.style.background = "#ffffff06"; },
                onMouseLeave: function(e) { e.currentTarget.style.background = "transparent"; },
              },
                React.createElement("td", { style: { padding: "8px 10px", color: C.muted, fontFamily: "monospace" } }, u.id),
                React.createElement("td", { style: { padding: "8px 10px", fontWeight: 500 } }, u.nombre),
                React.createElement("td", { style: { padding: "8px 10px", color: C.muted, fontSize: 11 } }, u.email),
                React.createElement("td", { style: { padding: "8px 10px" } }, React.createElement(Tag, { color: u.rol === "creator" ? C.amber : C.blue }, u.rol)),
                React.createElement("td", { style: { padding: "8px 10px", color: C.muted } }, u.plan),
                React.createElement("td", { style: { padding: "8px 10px" } },
                  u.rol === "creator"
                    ? React.createElement("span", { style: { color: C.amber, fontWeight: 700 } }, "∞")
                    : React.createElement("input", {
                        type: "number",
                        value: u.creditos,
                        onChange: function(e) { setCreditos(u.id, e.target.value); },
                        style: { width: 60, background: C.surface, border: "1px solid " + C.border, borderRadius: 4, padding: "3px 6px", color: C.gold, fontFamily: "monospace", fontSize: 12, textAlign: "center" }
                      })
                ),
                React.createElement("td", { style: { padding: "8px 10px", color: C.muted, fontSize: 11 } }, (u.created_at || "").substring(0, 10) || "—")
              );
            })
          )
        )
      )
    )
  );
}

// ─── ROOT ─────────────────────────────────────────────────────────
export default function LibraApp() {
  var _auth = useState(function() {
    try { var s = sessionStorage.getItem("libra_auth"); return s ? JSON.parse(s) : null; } catch (e) { return null; }
  }); var authData = _auth[0]; var setAuthData = _auth[1];
  var _page = useState("dashboard"); var page = _page[0]; var setPage = _page[1];
  var _emp = useState(null); var empresa = _emp[0]; var setEmpresa = _emp[1];
  var _sal = useState(null); var saldos = _sal[0]; var setSaldos = _sal[1];
  var _emps = useState([]); var empresas = _emps[0]; var setEmpresas = _emps[1];
  var _user = useState(null); var user = _user[0]; var setUser = _user[1];

  useEffect(function() {
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&display=swap";
    document.head.appendChild(link);
    var s = document.createElement("script");
    s.src = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js";
    document.head.appendChild(s);
  }, []);

  useEffect(function() {
    if (authData && authData.token) {
      var u = Object.assign({}, authData, { es_creator: authData.rol === "creator" });
      setUser(u);
      callApi("/empresas", null, authData.token, "GET").then(function(r) {
        if (r.ok) setEmpresas(r.data.empresas || []);
      });
      callApi("/auth/me", null, authData.token, "GET").then(function(r) {
        if (r.ok) setUser(Object.assign({}, u, r.data, { es_creator: r.data.rol === "creator" }));
      });
      callApi("/estudio", null, authData.token, "GET").then(function(r) {
        if (r.ok) setUser(function(prev) { return Object.assign({}, prev, { estudio_nombre: r.data.nombre }); });
      });
    }
  }, [authData]);

  function handleAuth(data) {
    var merged = Object.assign({}, data, { es_creator: data.rol === "creator" });
    setAuthData(merged);
    try { sessionStorage.setItem("libra_auth", JSON.stringify(merged)); } catch (e) {}
  }

  function handleLogout() {
    setAuthData(null); setUser(null);
    try { sessionStorage.removeItem("libra_auth"); } catch (e) {}
  }

  function handleSetPage(p) {
    setPage(p);
    if (p !== "empresa" && p !== "emision") setEmpresa(null);
  }

  if (!authData) {
    return React.createElement("div", null,
      React.createElement("style", null, "@keyframes libra-spin { to { transform: rotate(360deg); } }"),
      React.createElement(AuthScreen, { onAuth: handleAuth })
    );
  }

  function renderPage() {
    if (page === "dashboard") return React.createElement(Dashboard, { user: user, empresas: empresas, setPage: handleSetPage, setEmpresa: setEmpresa });
    if (page === "empresas")  return React.createElement(Empresas, { token: authData.token, empresas: empresas, setPage: handleSetPage, setEmpresa: setEmpresa, reload: function() { callApi("/empresas", null, authData.token, "GET").then(function(r) { if (r.ok) setEmpresas(r.data.empresas || []); }); } });
    if (page === "empresa")   return empresa ? React.createElement(EmpresaDetalle, { empresa: empresa, setPage: handleSetPage, token: authData.token }) : React.createElement(Empresas, { token: authData.token, empresas: empresas, setPage: handleSetPage, setEmpresa: setEmpresa, reload: function() {} });
    if (page === "upload")    return React.createElement(UploadSaldos, { token: authData.token, user: user, saldos: saldos, setSaldos: setSaldos, empresa: empresa, setPage: handleSetPage });
    if (page === "emision")   return React.createElement(EmisionBalance, { token: authData.token, user: user, saldos: saldos || DEMO, empresa: empresa, setPage: handleSetPage });
    if (page === "config")    return React.createElement(Config, { token: authData.token, user: user, onLogout: handleLogout });
    if (page === "admin" && user && user.es_creator) return React.createElement(AdminPanel, { token: authData.token, user: user });
    return React.createElement(Dashboard, { user: user, empresas: empresas, setPage: handleSetPage, setEmpresa: setEmpresa });
  }

  return React.createElement("div", {
    style: { display: "flex", height: "100vh", background: C.bg, color: C.text, fontFamily: "'DM Sans',sans-serif", overflow: "hidden" }
  },
    React.createElement("style", null, "@keyframes libra-spin { to { transform: rotate(360deg); } }"),
    React.createElement(Sidebar, { page: page, setPage: handleSetPage, user: user }),
    React.createElement("div", { style: { flex: 1, overflowY: "auto", background: C.bg } }, renderPage())
  );
}
