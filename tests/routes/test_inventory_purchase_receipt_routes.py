from datetime import datetime
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryPurchaseReceiptRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_purchase_receipt_create_returns_201(self):
        fake_business = SimpleNamespace(id=21)
        fake_movement = SimpleNamespace(
            id=700,
            movement_type="purchase",
            inventory_item_id=5,
            quantity=12.0,
            unit="kg",
            unit_cost=4.0,
            total_cost=48.0,
            account_code="7101",
            supplier_name="Proveedor Uno",
            document="FAC-777",
            lot_code="LOTE-777",
            lot_date=datetime(2026, 3, 20).date(),
            lot_unit="box",
            lot_conversion_factor=24.0,
            movement_date=datetime(2026, 3, 9, 12, 30, 0),
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.create_purchase_receipt",
            return_value=fake_movement,
        ) as create_receipt_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/purchase-receipt/create",
                json={
                    "inventory_item_id": 5,
                    "quantity": 12,
                    "unit": "kg",
                    "account_code": "7101",
                    "supplier_name": "Proveedor Uno",
                    "document": "FAC-777",
                    "receipt_date": "2026-03-09T12:30:00",
                    "unit_cost": 4.0,
                    "lot_code": "LOTE-777",
                    "lot_date": "2026-03-20",
                    "lot_unit": "box",
                    "lot_conversion_factor": 24,
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["supplier_name"], "Proveedor Uno")
        self.assertEqual(payload["item"]["document"], "FAC-777")
        self.assertEqual(payload["item"]["lot_unit"], "box")
        self.assertEqual(payload["item"]["lot_conversion_factor"], 24.0)
        create_receipt_mock.assert_called_once()
        called_kwargs = create_receipt_mock.call_args.kwargs
        self.assertEqual(str(called_kwargs["lot_date"]), "2026-03-20")

    def test_purchase_receipt_create_rejects_invalid_receipt_date(self):
        fake_business = SimpleNamespace(id=22)

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ):
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/purchase-receipt/create",
                json={
                    "inventory_item_id": 5,
                    "quantity": 12,
                    "unit": "kg",
                    "account_code": "7101",
                    "supplier_name": "Proveedor Uno",
                    "document": "FAC-778",
                    "receipt_date": "09/03/2026",
                    "unit_cost": 4.0,
                },
            )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertIn("receipt_date", payload["message"])


if __name__ == "__main__":
    unittest.main()
