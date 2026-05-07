-- ═══════════════════════════════════════════════════════════════
-- LIBRA — Schema Supabase (PostgreSQL)
-- Corré este SQL en: supabase.com → SQL Editor
-- ═══════════════════════════════════════════════════════════════

-- Habilitar UUID
create extension if not exists "uuid-ossp";

-- ── Usuarios ──────────────────────────────────────────────────────
create table if not exists usuarios (
  id          bigserial primary key,
  email       text unique not null,
  nombre      text not null,
  password    text not null,
  rol         text default 'contador' check (rol in ('creator','contador')),
  plan        text default 'free' check (plan in ('free','pro','enterprise')),
  creditos    integer default 0,
  activo      boolean default true,
  created_at  timestamptz default now(),
  last_login  timestamptz
);

-- Índice para login rápido
create index if not exists idx_usuarios_email on usuarios(email);

-- ── Estudios ──────────────────────────────────────────────────────
create table if not exists estudios (
  id          bigserial primary key,
  nombre      text not null,
  slug        text unique not null,
  owner_id    bigint references usuarios(id) on delete cascade,
  created_at  timestamptz default now()
);

-- ── Miembros de estudio ───────────────────────────────────────────
create table if not exists estudio_miembros (
  estudio_id  bigint references estudios(id) on delete cascade,
  usuario_id  bigint references usuarios(id) on delete cascade,
  rol         text default 'member' check (rol in ('admin','member','viewer')),
  primary key (estudio_id, usuario_id)
);

-- ── Empresas ──────────────────────────────────────────────────────
create table if not exists empresas (
  id                  bigserial primary key,
  estudio_id          bigint references estudios(id) on delete cascade,
  razon_social        text not null,
  cuit                text not null,
  tipo                text default 'S.A.',
  actividad           text,
  domicilio           text,
  capital_suscripto   numeric(18,2) default 0,
  fecha_inscripcion   text,
  fecha_estatuto      text,
  consejo_profesional text default 'CPCE Buenos Aires',
  nro_inscripcion     text,
  duracion_anos       integer default 99,
  activa              boolean default true,
  created_at          timestamptz default now()
);

create index if not exists idx_empresas_estudio on empresas(estudio_id);

-- ── Ejercicios ────────────────────────────────────────────────────
create table if not exists ejercicios (
  id              bigserial primary key,
  empresa_id      bigint references empresas(id) on delete cascade,
  numero          integer not null,
  fecha_inicio    text not null,
  fecha_cierre    text not null,
  estado          text default 'borrador' check (estado in ('borrador','emitido')),
  created_at      timestamptz default now(),
  unique (empresa_id, numero)
);

create index if not exists idx_ejercicios_empresa on ejercicios(empresa_id);

-- ── Cuentas ───────────────────────────────────────────────────────
create table if not exists cuentas (
  id           bigserial primary key,
  ejercicio_id bigint references ejercicios(id) on delete cascade,
  codigo       text not null,
  descripcion  text,
  debe         numeric(18,2) default 0,
  haber        numeric(18,2) default 0,
  saldo        numeric(18,2) default 0,
  tipo         text,  -- A, P, PN, R
  rubro        text,
  subrubro     text
);

create index if not exists idx_cuentas_ejercicio on cuentas(ejercicio_id);
create index if not exists idx_cuentas_codigo    on cuentas(codigo);

-- ── Firmantes ─────────────────────────────────────────────────────
create table if not exists firmantes (
  id          bigserial primary key,
  estudio_id  bigint references estudios(id) on delete cascade,
  nombre      text not null,
  titulo      text default 'Contador Público',
  matricula   text,
  activo      boolean default true
);

-- ── Transacciones (créditos) ──────────────────────────────────────
create table if not exists transacciones (
  id              bigserial primary key,
  usuario_id      bigint references usuarios(id),
  tipo            text check (tipo in ('compra_creditos','consumo_balance')),
  creditos        integer not null,
  monto           numeric(12,2) default 0,
  mp_payment_id   text,
  estado          text default 'pendiente' check (estado in ('pendiente','aprobado','rechazado')),
  created_at      timestamptz default now()
);

create index if not exists idx_transacciones_usuario on transacciones(usuario_id);

-- ── Balances emitidos ─────────────────────────────────────────────
create table if not exists balances_emitidos (
  id              bigserial primary key,
  ejercicio_id    bigint references ejercicios(id),
  usuario_id      bigint references usuarios(id),
  version         integer default 1,
  formato         text default 'pdf',
  tamano_kb       numeric(10,2),
  created_at      timestamptz default now()
);

-- ── Insertar Brian como creator ───────────────────────────────────
-- Password: libra2025 (sha256 con salt "libra-salt-2025")
insert into usuarios (email, nombre, password, rol, plan, creditos)
values (
  'brianveron2@gmail.com',
  'Brian Verón',
  '8f3d2a1b9c4e7f6d0a5b8c3e2f1d4a7b9c6e3f0d2a5b8c1e4f7d0a3b6c9e2f5',
  'creator',
  'enterprise',
  999999
) on conflict (email) do nothing;

-- Crear estudio para Brian
insert into estudios (nombre, slug, owner_id)
select 'Ofi', 'ofi', id from usuarios where email = 'brianveron2@gmail.com'
on conflict (slug) do nothing;

insert into estudio_miembros (estudio_id, usuario_id, rol)
select est.id, u.id, 'admin'
from estudios est, usuarios u
where est.slug = 'ofi' and u.email = 'brianveron2@gmail.com'
on conflict do nothing;

-- ── Row Level Security (RLS) ──────────────────────────────────────
-- Activar RLS en todas las tablas
alter table usuarios         enable row level security;
alter table estudios         enable row level security;
alter table estudio_miembros enable row level security;
alter table empresas         enable row level security;
alter table ejercicios       enable row level security;
alter table cuentas          enable row level security;
alter table firmantes        enable row level security;
alter table transacciones    enable row level security;
alter table balances_emitidos enable row level security;

-- La API accede con service_role_key (bypassa RLS), OK para backend propio.
-- Si usás Supabase Auth directo desde el frontend, agregá policies aquí.

-- ── Views útiles ──────────────────────────────────────────────────
create or replace view v_stats_globales as
select
  (select count(*) from usuarios where activo = true)              as total_usuarios,
  (select count(*) from estudios)                                   as total_estudios,
  (select count(*) from empresas where activa = true)               as total_empresas,
  (select count(*) from ejercicios)                                 as total_ejercicios,
  (select count(*) from balances_emitidos)                          as balances_emitidos,
  (select coalesce(sum(monto),0) from transacciones
   where tipo='compra_creditos' and estado='aprobado')              as ingresos_total,
  (select coalesce(sum(creditos),0) from transacciones
   where tipo='compra_creditos' and estado='aprobado')              as creditos_vendidos,
  (select count(*) from usuarios
   where date(created_at) = current_date)                          as nuevos_hoy;

-- ── Función para stats por estudio ────────────────────────────────
create or replace function stats_estudio(p_estudio_id bigint)
returns json as $$
  select json_build_object(
    'empresas',         (select count(*) from empresas where estudio_id = p_estudio_id and activa = true),
    'ejercicios',       (select count(*) from ejercicios e join empresas emp on e.empresa_id = emp.id where emp.estudio_id = p_estudio_id),
    'balances_emitidos',(select count(*) from balances_emitidos be join ejercicios ej on be.ejercicio_id = ej.id join empresas emp on ej.empresa_id = emp.id where emp.estudio_id = p_estudio_id)
  );
$$ language sql stable;
