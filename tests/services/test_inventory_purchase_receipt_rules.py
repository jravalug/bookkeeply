from datetime import date, datetime
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class TestInventoryPurchaseReceiptRules(unittest.TestCase):
    def test_create_purchase_receipt_requires_supplier_name(self):
        with self.assertRaises(ValueError):
            InventoryService.create_purchase_receipt(
                business_id=1,
                inventory_item_id=2,
                quantity=3.0,
                unit="kg",
                account_code="7101",
                supplier_name="",
                document="FAC-1",
                receipt_date=datetime(2026, 3, 9, 10, 0, 0),
                unit_cost=5.0,
            )

    def test_create_purchase_receipt_computes_total_cost_and_calls_create_movement(
        self,
    ):
        fake_movement = SimpleNamespace(id=100)
        receipt_date = datetime(2026, 3, 9, 11, 0, 0)
        lot_date = date(2026, 3, 20)

        with patch(
            "app.services.inventory_service.InventoryService.create_movement",
            return_value=fake_movement,
        ) as create_movement_mock:
            result = InventoryService.create_purchase_receipt(
                business_id=9,
                inventory_item_id=11,
                quantity=4.0,
                unit="kg",
                account_code="7101",
                supplier_name="Proveedor Demo",
                document="FAC-900",
                receipt_date=receipt_date,
                unit_cost=2.5,
                lot_code="LOTE-900",
                lot_date=lot_date,
                lot_unit="box",
                lot_conversion_factor=24,
                notes="Recepcion inicial",
            )

        self.assertEqual(result, fake_movement)
        create_movement_mock.assert_called_once_with(
            business_id=9,
            inventory_item_id=11,
            movement_type="purchase",
            destination=None,
            quantity=4.0,
            unit="kg",
            unit_cost=2.5,
            total_cost=10.0,
            account_code="7101",
            reference_type="purchase_receipt",
            supplier_name="Proveedor Demo",
            lot_code="LOTE-900",
            lot_date=lot_date,
            lot_unit="box",
            lot_conversion_factor=24,
            movement_date=receipt_date,
            document="FAC-900",
            notes="Recepcion inicial",
        )


if __name__ == "__main__":
    unittest.main()
