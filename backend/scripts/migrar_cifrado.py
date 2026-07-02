#!/usr/bin/env python
"""CLI del backfill de cifrado en reposo (Fase 2 Migrate).

Usa la BD de la app (DATABASE_URL) y las llaves (ENC_KEYS/BLIND_INDEX_KEY).
Uso:
    python -m backend.scripts.migrar_cifrado --dry-run   # reporta, no escribe
    python -m backend.scripts.migrar_cifrado             # cifra el histórico
    python -m backend.scripts.migrar_cifrado --verify    # comprueba integridad
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill de cifrado en reposo.")
    ap.add_argument("--dry-run", action="store_true", help="No escribe; solo reporta.")
    ap.add_argument("--verify", action="store_true", help="Comprueba integridad de lo cifrado.")
    args = ap.parse_args()

    from backend.crypto import is_configured
    from backend.database import SessionLocal
    from backend.services.cifrado_backfill import backfill, verify

    if not is_configured():
        print("ERROR: ENC_KEYS/BLIND_INDEX_KEY no configuradas.", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        if args.verify:
            errs = verify(db)
            print("verify: OK" if not errs else f"verify: {len(errs)} ERRORES")
            for e in errs[:50]:
                print("  -", e)
            return 0 if not errs else 1
        rep = backfill(db, dry_run=args.dry_run)
        print(("DRY-RUN " if args.dry_run else "") + "backfill:", rep)
        if args.dry_run:
            print("Nada se escribió. Repite sin --dry-run para aplicar, luego --verify.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
