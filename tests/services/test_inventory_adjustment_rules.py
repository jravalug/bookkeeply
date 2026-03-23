from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class TestInventoryAdjustmentRules(unittest.TestCase):
    def test_movement_stock_delta_for_negative_adjustment_is_negative(self):
        delta = InventoryService._movement_stock_delta(
            movement_type="adjustment",
            quantity=5,
            adjustment_kind="negative",
        )
        self.assertEqual(delta, -5.0)

    def test_create_movement_rejects_adjustment_without_reason(self):
        with self.assertRaises(ValueError):
            InventoryService.create_movement(
                business_id=1,
                inventory_item_id=1,
                movement_type="adjustment",
                adjustment_kind="positive",
                quantity=1,
                unit="kg",
                account_code="7101",
                notes=None,
            )

    def test_create_movement_rejects_invalid_adjustment_kind(self):
        with self.assertRaises(ValueError):
            InventoryService.create_movement(
                business_id=1,
                inventory_item_id=1,
                movement_type="adjustment",
                adjustment_kind="manual",
                quantity=1,
                unit="kg",
                account_code="7101",
                notes="Ajuste de prueba",
            )


if __name__ == "__main__":
    unittest.main()
