from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class TestInventoryMinStockPolicyRules(unittest.TestCase):
    def test_create_movement_blocks_when_policy_is_block_and_breaches_min_stock(self):
        item = SimpleNamespace(id=30, stock=10.0, min_stock=8.0, average_unit_cost=1.0)

        with patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=item,
        ), patch(
            "app.services.inventory_service.InventoryService.validate_account_is_adopted"
        ), patch(
            "app.services.inventory_service.InventoryService._resolve_business_min_stock_policy",
            return_value="block",
        ):
            with self.assertRaises(ValueError):
                InventoryService.create_movement(
                    business_id=1,
                    inventory_item_id=30,
                    movement_type="consumption",
                    quantity=3,
                    unit="kg",
                    account_code="7101",
                )

    def test_create_movement_flags_alert_when_policy_is_alert_and_breaches_min_stock(
        self,
    ):
        item = SimpleNamespace(id=31, stock=10.0, min_stock=8.0, average_unit_cost=1.0)

        def _movement_factory(**kwargs):
            return SimpleNamespace(id=701, **kwargs)

        with patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=item,
        ), patch(
            "app.services.inventory_service.InventoryService.validate_account_is_adopted"
        ), patch(
            "app.services.inventory_service.InventoryService._resolve_business_min_stock_policy",
            return_value="alert",
        ), patch(
            "app.services.inventory_service.InventoryMovement",
            side_effect=_movement_factory,
        ), patch(
            "app.services.inventory_service.InventoryService.register_inventory_ledger_for_movement"
        ), patch(
            "app.services.inventory_service.db.session.add"
        ), patch(
            "app.services.inventory_service.db.session.commit"
        ):
            movement = InventoryService.create_movement(
                business_id=1,
                inventory_item_id=31,
                movement_type="consumption",
                quantity=3,
                unit="kg",
                account_code="7101",
            )

        self.assertEqual(item.stock, 7.0)
        self.assertTrue(movement.min_stock_alert)
        self.assertEqual(movement.min_stock_policy, "alert")
        self.assertEqual(movement.projected_stock, 7.0)
        self.assertEqual(movement.min_stock_threshold, 8.0)


if __name__ == "__main__":
    unittest.main()
