from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryMovementRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_movement_create_accepts_lot_code(self):
        fake_business = SimpleNamespace(id=8)
        fake_movement = SimpleNamespace(
            id=101,
            movement_type="purchase",
            destination=None,
            lot_code="LOTE-001",
            quantity=10.0,
            unit="kg",
            account_code="7101",
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.create_movement",
            return_value=fake_movement,
        ) as create_movement_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/movement/create",
                json={
                    "inventory_item_id": 5,
                    "movement_type": "purchase",
                    "quantity": 10,
                    "unit": "kg",
                    "account_code": "7101",
                    "lot_code": "LOTE-001",
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["lot_code"], "LOTE-001")
        create_movement_mock.assert_called_once_with(
            business_id=8,
            inventory_item_id=5,
            movement_type="purchase",
            destination=None,
            quantity=10.0,
            unit="kg",
            inventory_id=None,
            unit_cost=None,
            total_cost=None,
            account_code="7101",
            idempotency_key=None,
            reference_type=None,
            reference_id=None,
            lot_code="LOTE-001",
            document=None,
            notes=None,
        )

    def test_stowage_card_returns_entries(self):
        fake_business = SimpleNamespace(id=9)
        rows = [
            {
                "id": 1,
                "movement_type": "purchase",
                "destination": None,
                "lot_code": "AUTO-20260309-5-001",
                "quantity": 12.0,
                "delta": 12.0,
                "running_balance": 12.0,
                "unit": "kg",
                "movement_date": None,
                "account_code": "7101",
                "reference_type": None,
                "reference_id": None,
                "document": "FAC-123",
                "notes": "entrada",
            }
        ]

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_stowage_card",
            return_value=rows,
        ) as stowage_mock:
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/movement/stowage-card"
                "?inventory_item_id=5&lot_code=AUTO-20260309-5-001"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["lot_code"], "AUTO-20260309-5-001")
        self.assertEqual(len(payload["item"]["entries"]), 1)
        stowage_mock.assert_called_once_with(
            business_id=9,
            inventory_item_id=5,
            lot_code="AUTO-20260309-5-001",
        )


if __name__ == "__main__":
    unittest.main()
