#!/usr/bin/env python
"""Rebuild and validate inventory stock from historical movements."""

from __future__ import annotations

import argparse
import json
import sys

from app import create_app
from app.models import Business
from app.services.inventory_service import InventoryService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recalcula stock por item desde movimientos historicos y valida "
            "consistencia por negocio."
        )
    )
    parser.add_argument(
        "--business-id",
        type=int,
        help="ID de negocio a procesar.",
    )
    parser.add_argument(
        "--all-businesses",
        action="store_true",
        help="Procesa todos los negocios activos en la base.",
    )
    parser.add_argument(
        "--inventory-item-id",
        type=int,
        default=None,
        help="Opcional: limita la reconstruccion a un item especifico.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica cambios en DB. Sin esta bandera se ejecuta dry-run.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime resultado completo en formato JSON.",
    )
    return parser.parse_args()


def _resolve_business_ids(args: argparse.Namespace) -> list[int]:
    if args.all_businesses:
        rows = Business.query.order_by(Business.id.asc()).all()
        return [int(row.id) for row in rows]

    if args.business_id is None:
        raise ValueError("Debe indicar --business-id o usar --all-businesses")

    if args.business_id <= 0:
        raise ValueError("--business-id debe ser un entero positivo")

    return [args.business_id]


def _run_for_business(
    business_id: int,
    apply_changes: bool,
    inventory_item_id: int | None,
) -> dict:
    rebuild = InventoryService.rebuild_stock_from_history(
        business_id=business_id,
        inventory_item_id=inventory_item_id,
        commit=apply_changes,
    )
    validation = InventoryService.validate_stock_consistency_from_history(
        business_id=business_id,
        inventory_item_id=inventory_item_id,
    )

    return {
        "business_id": business_id,
        "apply": apply_changes,
        "rebuild": rebuild,
        "validation": {
            "is_consistent": validation["is_consistent"],
            "mismatch_count": validation["mismatch_count"],
            "negative_balance_issue_count": validation["negative_balance_issue_count"],
            "missing_item_count": validation["missing_item_count"],
        },
    }


def _print_human_summary(results: list[dict]) -> None:
    print("=" * 72)
    print("RECONSTRUCCION HISTORICA DE STOCK")
    print("=" * 72)

    for result in results:
        business_id = result["business_id"]
        rebuild = result["rebuild"]
        validation = result["validation"]
        print(f"negocio={business_id}")
        print(
            "  movimiento_count={movement_count} item_count={item_count} "
            "updated_count={updated_count} commit_applied={commit_applied}".format(
                movement_count=rebuild.get("movement_count", 0),
                item_count=rebuild.get("item_count", 0),
                updated_count=rebuild.get("updated_count", 0),
                commit_applied=rebuild.get("commit_applied", False),
            )
        )
        print(
            "  consistency: is_consistent={is_consistent} mismatches={mismatch_count} "
            "negative_balances={negative_balance_issue_count} missing_items={missing_item_count}".format(
                is_consistent=validation.get("is_consistent", False),
                mismatch_count=validation.get("mismatch_count", 0),
                negative_balance_issue_count=validation.get(
                    "negative_balance_issue_count", 0
                ),
                missing_item_count=validation.get("missing_item_count", 0),
            )
        )


def main() -> int:
    args = _parse_args()
    app = create_app()

    try:
        with app.app_context():
            business_ids = _resolve_business_ids(args)
            if not business_ids:
                print("No hay negocios para procesar")
                return 0

            results = [
                _run_for_business(
                    business_id=business_id,
                    apply_changes=bool(args.apply),
                    inventory_item_id=args.inventory_item_id,
                )
                for business_id in business_ids
            ]

            if args.json:
                print(json.dumps(results, default=str, ensure_ascii=False, indent=2))
            else:
                _print_human_summary(results)

            has_errors = any(not row["validation"]["is_consistent"] for row in results)
            return 2 if has_errors else 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
