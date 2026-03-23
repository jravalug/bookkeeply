from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class TestInventoryAverageCostRules(unittest.TestCase):
    def test_create_movement_purchase_recalculates_weighted_average_cost(self):
        item = SimpleNamespace(id=10, stock=10.0, average_unit_cost=2.0)

        def _movement_factory(**kwargs):
            return SimpleNamespace(id=501, **kwargs)

        with patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=item,
        ), patch(
            "app.services.inventory_service.InventoryService.validate_account_is_adopted"
        ), patch(
            "app.services.inventory_service.InventoryService.register_inventory_ledger_for_movement"
        ), patch(
            "app.services.inventory_service.InventoryMovement",
            side_effect=_movement_factory,
        ), patch(
            "app.services.inventory_service.db.session.add"
        ), patch(
            "app.services.inventory_service.db.session.commit"
        ):
            movement = InventoryService.create_movement(
                business_id=1,
                inventory_item_id=10,
                movement_type="purchase",
                quantity=5,
                unit="kg",
                unit_cost=4.0,
                total_cost=None,
                account_code="7101",
                lot_code="LOTE-10",
                document="FAC-10",
            )

        self.assertEqual(movement.movement_type, "purchase")
        self.assertEqual(item.stock, 15.0)
        self.assertAlmostEqual(item.average_unit_cost, (10.0 * 2.0 + 5.0 * 4.0) / 15.0)

    def test_create_movement_purchase_uses_total_cost_to_recalculate_average(self):
        item = SimpleNamespace(id=20, stock=8.0, average_unit_cost=3.0)

        def _movement_factory(**kwargs):
            return SimpleNamespace(id=502, **kwargs)

        with patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=item,
        ), patch(
            "app.services.inventory_service.InventoryService.validate_account_is_adopted"
        ), patch(
            "app.services.inventory_service.InventoryService.register_inventory_ledger_for_movement"
        ), patch(
            "app.services.inventory_service.InventoryMovement",
            side_effect=_movement_factory,
        ), patch(
            "app.services.inventory_service.db.session.add"
        ), patch(
            "app.services.inventory_service.db.session.commit"
        ):
            InventoryService.create_movement(
                business_id=1,
                inventory_item_id=20,
                movement_type="purchase",
                quantity=2,
                unit="kg",
                unit_cost=None,
                total_cost=10.0,
                account_code="7101",
                lot_code="LOTE-20",
                document="FAC-20",
            )

        expected_average = (8.0 * 3.0 + 2.0 * 5.0) / 10.0
        self.assertEqual(item.stock, 10.0)
        self.assertAlmostEqual(item.average_unit_cost, expected_average)

    def test_create_movement_negative_adjustment_does_not_change_average_cost(self):
        item = SimpleNamespace(id=30, stock=10.0, average_unit_cost=6.5)

        def _movement_factory(**kwargs):
            return SimpleNamespace(id=503, **kwargs)

        with patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=item,
        ), patch(
            "app.services.inventory_service.InventoryService.validate_account_is_adopted"
        ), patch(
            "app.services.inventory_service.InventoryService.register_inventory_ledger_for_movement"
        ), patch(
            "app.services.inventory_service.InventoryMovement",
            side_effect=_movement_factory,
        ), patch(
            "app.services.inventory_service.db.session.add"
        ), patch(
            "app.services.inventory_service.db.session.commit"
        ):
            InventoryService.create_movement(
                business_id=1,
                inventory_item_id=30,
                movement_type="adjustment",
                adjustment_kind="negative",
                quantity=4,
                unit="kg",
                unit_cost=3.0,
                account_code="7101",
                notes="Conteo fisico",
            )

        self.assertEqual(item.stock, 6.0)
        self.assertEqual(item.average_unit_cost, 6.5)


if __name__ == "__main__":
    unittest.main()
