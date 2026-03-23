from datetime import datetime
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class TestInventoryCycleCountRules(unittest.TestCase):
    def test_create_cycle_count_builds_automatic_adjustment_proposal(self):
        fake_item = SimpleNamespace(id=7, stock=10.0)

        def _factory(**kwargs):
            return SimpleNamespace(id=301, **kwargs)

        with patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=fake_item,
        ), patch(
            "app.services.inventory_service.InventoryCycleCount",
            side_effect=_factory,
        ), patch(
            "app.services.inventory_service.db.session.add"
        ), patch(
            "app.services.inventory_service.db.session.commit"
        ):
            count = InventoryService.create_cycle_count(
                business_id=1,
                inventory_item_id=7,
                location="warehouse",
                counted_quantity=8,
                actor="operador_demo",
                counted_at=datetime(2026, 3, 9, 15, 0, 0),
                observation="Conteo manual",
            )

        self.assertEqual(count.theoretical_quantity, 10.0)
        self.assertEqual(count.counted_quantity, 8.0)
        self.assertEqual(count.difference_quantity, -2.0)
        self.assertEqual(count.proposed_adjustment_kind, "negative")
        self.assertEqual(count.actor, "operador_demo")

    def test_reconcile_cycle_count_applies_adjustment_movement(self):
        fake_count = SimpleNamespace(
            id=302,
            business_id=1,
            status="pending",
            location="warehouse",
            difference_quantity=-3.0,
            inventory_item_id=7,
            inventory_item=SimpleNamespace(unit="kg"),
            applied_movement_id=None,
        )
        fake_movement = SimpleNamespace(id=808)

        with patch(
            "app.services.inventory_service.InventoryCycleCount"
        ) as cycle_model, patch(
            "app.services.inventory_service.InventoryService.create_movement",
            return_value=fake_movement,
        ) as create_movement_mock, patch(
            "app.services.inventory_service.db.session.commit"
        ):
            cycle_model.query.get_or_404.return_value = fake_count
            result = InventoryService.reconcile_cycle_count(
                business_id=1,
                cycle_count_id=302,
                account_code="7101",
                actor="supervisor_demo",
                notes="Conciliacion inventario",
            )

        create_movement_mock.assert_called_once_with(
            business_id=1,
            inventory_item_id=7,
            movement_type="adjustment",
            adjustment_kind="negative",
            quantity=3.0,
            unit="kg",
            account_code="7101",
            reference_type="cycle_count",
            reference_id=302,
            notes="Conciliacion inventario",
        )
        self.assertEqual(result.status, "applied")
        self.assertEqual(result.applied_movement_id, 808)


if __name__ == "__main__":
    unittest.main()
