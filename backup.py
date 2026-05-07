#!/usr/bin/env python3
"""
LIBRA — Backup automático de la base de datos
Correr con: python3 backup.py
Agregar a cron: 0 3 * * * /usr/bin/python3 /app/backup.py
"""
import os, shutil, sqlite3, json
from datetime import datetime

DB_PATH     = os.getenv("LIBRA_DB", "/var/data/libra.db")
BACKUP_DIR  = os.getenv("BACKUP_DIR", "/var/data/backups")
MAX_BACKUPS = 7  # Mantener 7 días

def backup():
    if not os.path.exists(DB_PATH):
        print("DB no encontrada:", DB_PATH)
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(BACKUP_DIR, f"libra_{ts}.db")

    # Backup usando la API de SQLite (safe mientras está en uso)
    src_conn = sqlite3.connect(DB_PATH)
    dst_conn = sqlite3.connect(dest)
    src_conn.backup(dst_conn)
    src_conn.close()
    dst_conn.close()

    size_mb = os.path.getsize(dest) / 1024 / 1024

    # Stats del backup
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    stats = {
        "usuarios":  db.execute("SELECT COUNT(*) FROM usuarios WHERE activo=1").fetchone()[0],
        "empresas":  db.execute("SELECT COUNT(*) FROM empresas WHERE activa=1").fetchone()[0],
        "balances":  db.execute("SELECT COUNT(*) FROM balances_emitidos").fetchone()[0],
        "ingresos":  db.execute("SELECT COALESCE(SUM(monto),0) FROM transacciones WHERE tipo='compra_creditos' AND estado='aprobado'").fetchone()[0],
    }
    db.close()

    print(f"✓ Backup creado: {dest} ({size_mb:.2f} MB)")
    print(f"  Usuarios: {stats['usuarios']} | Empresas: {stats['empresas']} | Balances: {stats['balances']}")
    print(f"  Ingresos acumulados: ${stats['ingresos']:,.0f}")

    # Limpiar backups viejos
    backups = sorted([
        os.path.join(BACKUP_DIR, f)
        for f in os.listdir(BACKUP_DIR)
        if f.startswith("libra_") and f.endswith(".db")
    ])
    while len(backups) > MAX_BACKUPS:
        old = backups.pop(0)
        os.remove(old)
        print(f"  Eliminado backup viejo: {old}")

    # Guardar log
    log_path = os.path.join(BACKUP_DIR, "backup_log.json")
    try:
        log = json.loads(open(log_path).read()) if os.path.exists(log_path) else []
    except:
        log = []
    log.append({ "timestamp": ts, "size_mb": round(size_mb, 2), **stats })
    log = log[-30:]  # Últimos 30 registros
    open(log_path, "w").write(json.dumps(log, indent=2))

    return dest

if __name__ == "__main__":
    print("LIBRA — Backup", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    backup()
