from datetime import date
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
            adjustment_kind=None,
            destination=None,
            lot_code="LOTE-001",
            lot_date=date(2026, 3, 9),
            lot_unit="box",
            lot_conversion_factor=24.0,
            quantity=10.0,
            unit="kg",
            account_code="7101",
            supplier_name="Proveedor Demo",
            waste_reason=None,
            waste_responsible=None,
            waste_evidence=None,
            min_stock_alert=False,
            min_stock_policy="alert",
            projected_stock=10.0,
            min_stock_threshold=None,
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
                    "lot_date": "2026-03-09",
                    "lot_unit": "box",
                    "lot_conversion_factor": 24,
                    "document": "FAC-001",
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
            adjustment_kind=None,
            quantity=10.0,
            unit="kg",
            inventory_id=None,
            unit_cost=None,
            total_cost=None,
            account_code="7101",
            idempotency_key=None,
            reference_type=None,
            reference_id=None,
            supplier_name=None,
            waste_reason=None,
            waste_responsible=None,
            waste_evidence=None,
            waste_evidence_file_url=None,
            lot_code="LOTE-001",
            lot_date=date(2026, 3, 9),
            lot_unit="box",
            lot_conversion_factor=24.0,
            document="FAC-001",
            notes=None,
        )

    def test_movement_create_returns_400_when_purchase_missing_document(self):
        fake_business = SimpleNamespace(id=8)

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.create_movement",
            side_effect=ValueError(
                "El documento es obligatorio para registrar entradas de compra"
            ),
        ):
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/movement/create",
                json={
                    "inventory_item_id": 5,
                    "movement_type": "purchase",
                    "quantity": 10,
                    "unit": "kg",
                    "account_code": "7101",
                },
            )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertIn("documento", payload["message"].lower())

    def test_movement_create_accepts_negative_adjustment_with_reason(self):
        fake_business = SimpleNamespace(id=8)
        fake_movement = SimpleNamespace(
            id=102,
            movement_type="adjustment",
            adjustment_kind="negative",
            destination=None,
            lot_code=None,
            lot_date=None,
            lot_unit=None,
            lot_conversion_factor=None,
            quantity=2.0,
            unit="kg",
            account_code="7101",
            supplier_name=None,
            waste_reason=None,
            waste_responsible=None,
            waste_evidence=None,
            min_stock_alert=False,
            min_stock_policy="alert",
            projected_stock=8.0,
            min_stock_threshold=None,
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
                    "movement_type": "adjustment",
                    "adjustment_kind": "negative",
                    "quantity": 2,
                    "unit": "kg",
                    "account_code": "7101",
                    "notes": "Conteo fisico por debajo",
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["adjustment_kind"], "negative")
        create_movement_mock.assert_called_once_with(
            business_id=8,
            inventory_item_id=5,
            movement_type="adjustment",
            destination=None,
            adjustment_kind="negative",
            quantity=2.0,
            unit="kg",
            inventory_id=None,
            unit_cost=None,
            total_cost=None,
            account_code="7101",
            idempotency_key=None,
            reference_type=None,
            reference_id=None,
            supplier_name=None,
            waste_reason=None,
            waste_responsible=None,
            waste_evidence=None,
            waste_evidence_file_url=None,
            lot_code=None,
            lot_date=None,
            lot_unit=None,
            lot_conversion_factor=None,
            document=None,
            notes="Conteo fisico por debajo",
        )

    def test_stowage_card_returns_entries(self):
        fake_business = SimpleNamespace(id=9)
        rows = [
            {
                "id": 1,
                "movement_type": "purchase",
                "adjustment_kind": None,
                "destination": None,
                "lot_code": "AUTO-20260309-5-001",
                "quantity": 12.0,
                "delta": 12.0,
                "running_balance": 12.0,
                "unit": "kg",
                "movement_date": None,
                "account_code": "7101",
                "lot_date": date(2026, 3, 9),
                "lot_unit": "box",
                "lot_conversion_factor": 24.0,
                "reference_type": None,
                "reference_id": None,
                "document": "FAC-123",
                "supplier_name": "Proveedor Demo",
                "waste_reason": None,
                "waste_responsible": None,
                "waste_evidence": None,
                "waste_evidence_file_url": None,
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
            location=None,
        )

    def test_stowage_card_accepts_location_filter(self):
        fake_business = SimpleNamespace(id=9)

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_stowage_card",
            return_value=[],
        ) as stowage_mock:
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/movement/stowage-card"
                "?inventory_item_id=5&lot_code=AUTO-20260309-5-001&location=warehouse"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["location"], "warehouse")
        stowage_mock.assert_called_once_with(
            business_id=9,
            inventory_item_id=5,
            lot_code="AUTO-20260309-5-001",
            location="warehouse",
        )

    def test_movement_create_accepts_typed_waste(self):
        fake_business = SimpleNamespace(id=8)
        fake_movement = SimpleNamespace(
            id=103,
            movement_type="waste",
            adjustment_kind=None,
            destination="finished_goods",
            lot_code=None,
            lot_date=None,
            lot_unit=None,
            lot_conversion_factor=None,
            quantity=1.5,
            unit="kg",
            account_code="7101",
            supplier_name=None,
            waste_reason="rotura",
            waste_responsible="Operario 2",
            waste_evidence="Foto interna #44",
            waste_evidence_file_url="https://files.local/mermas/foto_44.jpg",
            min_stock_alert=True,
            min_stock_policy="alert",
            projected_stock=4.5,
            min_stock_threshold=5.0,
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
                    "movement_type": "waste",
                    "destination": "finished_goods",
                    "quantity": 1.5,
                    "unit": "kg",
                    "account_code": "7101",
                    "waste_reason": "rotura",
                    "waste_responsible": "Operario 2",
                    "waste_evidence": "Foto interna #44",
                    "waste_evidence_file_url": "https://files.local/mermas/foto_44.jpg",
                    "notes": "Merma en preparacion",
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["waste_reason"], "rotura")
        self.assertEqual(payload["item"]["waste_responsible"], "Operario 2")
        self.assertTrue(payload["item"]["min_stock_alert"])
        self.assertEqual(payload["item"]["min_stock_policy"], "alert")
        create_movement_mock.assert_called_once_with(
            business_id=8,
            inventory_item_id=5,
            movement_type="waste",
            destination="finished_goods",
            adjustment_kind=None,
            quantity=1.5,
            unit="kg",
            inventory_id=None,
            unit_cost=None,
            total_cost=None,
            account_code="7101",
            idempotency_key=None,
            reference_type=None,
            reference_id=None,
            supplier_name=None,
            waste_reason="rotura",
            waste_responsible="Operario 2",
            waste_evidence="Foto interna #44",
            waste_evidence_file_url="https://files.local/mermas/foto_44.jpg",
            lot_code=None,
            lot_date=None,
            lot_unit=None,
            lot_conversion_factor=None,
            document=None,
            notes="Merma en preparacion",
        )


if __name__ == "__main__":
    unittest.main()
