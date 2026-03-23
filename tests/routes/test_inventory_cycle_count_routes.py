from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryCycleCountRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_cycle_count_create_returns_201(self):
        fake_business = SimpleNamespace(id=55)
        fake_row = SimpleNamespace(
            id=1,
            inventory_item_id=7,
            location="warehouse",
            theoretical_quantity=10.0,
            counted_quantity=8.0,
            difference_quantity=-2.0,
            proposed_adjustment_kind="negative",
            status="pending",
            actor="operador_demo",
            counted_at=None,
            observation="Conteo manual",
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.create_cycle_count",
            return_value=fake_row,
        ) as create_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/cycle-count/create",
                json={
                    "inventory_item_id": 7,
                    "location": "warehouse",
                    "counted_quantity": 8,
                    "actor": "operador_demo",
                    "observation": "Conteo manual",
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["proposed_adjustment_kind"], "negative")
        create_mock.assert_called_once()

    def test_cycle_count_reconcile_returns_200(self):
        fake_business = SimpleNamespace(id=55)
        fake_row = SimpleNamespace(
            id=4,
            status="applied",
            applied_movement_id=900,
            difference_quantity=2.0,
            proposed_adjustment_kind="positive",
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.reconcile_cycle_count",
            return_value=fake_row,
        ) as reconcile_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/cycle-count/4/reconcile",
                json={
                    "account_code": "7101",
                    "actor": "supervisor_demo",
                    "notes": "ajuste por conteo",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["applied_movement_id"], 900)
        reconcile_mock.assert_called_once_with(
            business_id=55,
            cycle_count_id=4,
            account_code="7101",
            actor="supervisor_demo",
            notes="ajuste por conteo",
        )


if __name__ == "__main__":
    unittest.main()
