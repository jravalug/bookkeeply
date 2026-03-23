from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class TestInventorySaleIdempotencyRules(unittest.TestCase):
    def test_create_movement_uses_auto_idempotency_for_sale_reference(self):
        item = SimpleNamespace(id=41, stock=10.0, min_stock=None, average_unit_cost=1.0)

        def _factory(**kwargs):
            return SimpleNamespace(id=911, **kwargs)

        movement_model = MagicMock(side_effect=_factory)
        movement_model.query.filter_by.return_value.first.return_value = None

        with patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=item,
        ), patch(
            "app.services.inventory_service.InventoryService.validate_account_is_adopted"
        ), patch(
            "app.services.inventory_service.InventoryMovement",
            movement_model,
        ), patch(
            "app.services.inventory_service.InventoryService.register_inventory_ledger_for_movement"
        ), patch(
            "app.services.inventory_service.db.session.add"
        ), patch(
            "app.services.inventory_service.db.session.commit"
        ):
            movement = InventoryService.create_movement(
                business_id=3,
                inventory_item_id=41,
                movement_type="consumption",
                quantity=2,
                unit="kg",
                account_code="7101",
                reference_type="sale",
                reference_id=555,
            )

        self.assertEqual(item.stock, 8.0)
        self.assertEqual(
            movement.idempotency_key,
            "auto:sale:3:555:41:consumption:none",
        )

    def test_create_movement_returns_existing_when_sale_auto_idempotent_key_exists(
        self,
    ):
        existing = SimpleNamespace(
            id=77, idempotency_key="auto:sale:3:555:41:consumption:none"
        )
        item = SimpleNamespace(id=41, stock=10.0, min_stock=None, average_unit_cost=1.0)

        movement_model = MagicMock()
        movement_model.query.filter_by.return_value.first.return_value = existing

        with patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=item,
        ), patch(
            "app.services.inventory_service.InventoryService.validate_account_is_adopted"
        ), patch(
            "app.services.inventory_service.InventoryMovement",
            movement_model,
        ):
            movement = InventoryService.create_movement(
                business_id=3,
                inventory_item_id=41,
                movement_type="consumption",
                quantity=2,
                unit="kg",
                account_code="7101",
                reference_type="sale",
                reference_id=555,
            )

        self.assertIs(movement, existing)
        self.assertEqual(item.stock, 10.0)


if __name__ == "__main__":
    unittest.main()
