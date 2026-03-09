from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class TestInventoryAccountingLedgerRules(unittest.TestCase):
    def test_register_inventory_ledger_for_purchase_uses_fefo_when_lot(self):
        movement = SimpleNamespace(
            id=101,
            business_id=5,
            movement_type="purchase",
            destination=None,
            account_code="7101",
            quantity=4.0,
            unit="kg",
            unit_cost=2.5,
            total_cost=None,
            lot_code="LOTE-1",
            document="FAC-1",
            reference_type="invoice",
            reference_id=33,
        )

        def _factory(**kwargs):
            return SimpleNamespace(**kwargs)

        with patch(
            "app.services.inventory_service.InventoryLedgerEntry"
        ) as ledger_model, patch(
            "app.services.inventory_service.db.session.add"
        ) as add_mock, patch(
            "app.services.inventory_service.db.session.commit"
        ) as commit_mock:
            ledger_model.query.filter_by.return_value.first.return_value = None
            ledger_model.side_effect = _factory

            entry = InventoryService.register_inventory_ledger_for_movement(movement)

        self.assertEqual(entry.source_bucket, "supplier")
        self.assertEqual(entry.destination_bucket, "warehouse")
        self.assertIsNone(entry.source_account_code)
        self.assertEqual(entry.destination_account_code, "7101")
        self.assertEqual(entry.amount, 10.0)
        self.assertEqual(entry.valuation_method, "fefo")
        add_mock.assert_called_once()
        commit_mock.assert_called_once()

    def test_upsert_sale_cost_breakdown_rejects_negative_values(self):
        fake_sale = SimpleNamespace(id=90, business_id=9)
        with patch("app.services.inventory_service.Sale") as sale_model:
            sale_model.query.get_or_404.return_value = fake_sale
            with self.assertRaises(ValueError):
                InventoryService.upsert_sale_cost_breakdown(
                    business_id=9,
                    sale_id=90,
                    production_cost=-1,
                    merchandise_cost=2,
                )

    def test_register_inventory_ledger_for_waste_raw_materials_uses_800(self):
        movement = SimpleNamespace(
            id=102,
            business_id=5,
            movement_type="waste",
            destination=None,
            account_code="183",
            quantity=3.0,
            unit="kg",
            unit_cost=4.0,
            total_cost=None,
            lot_code="LOTE-W1",
            document="AJ-1",
            reference_type="adjustment",
            reference_id=34,
        )

        def _factory(**kwargs):
            return SimpleNamespace(**kwargs)

        with patch(
            "app.services.inventory_service.InventoryLedgerEntry"
        ) as ledger_model, patch(
            "app.services.inventory_service.db.session.add"
        ), patch(
            "app.services.inventory_service.db.session.commit"
        ):
            ledger_model.query.filter_by.return_value.first.return_value = None
            ledger_model.side_effect = _factory

            entry = InventoryService.register_inventory_ledger_for_movement(movement)

        self.assertEqual(entry.source_bucket, "warehouse")
        self.assertEqual(entry.destination_bucket, "waste_raw_materials")
        self.assertEqual(entry.source_account_code, "183")
        self.assertEqual(entry.destination_account_code, "800")
        self.assertEqual(entry.amount, 12.0)

    def test_register_inventory_ledger_for_waste_finished_goods_uses_800(self):
        movement = SimpleNamespace(
            id=103,
            business_id=5,
            movement_type="waste",
            destination="finished_goods",
            account_code="188",
            quantity=2.0,
            unit="unit",
            unit_cost=5.0,
            total_cost=None,
            lot_code=None,
            document="AJ-2",
            reference_type="adjustment",
            reference_id=35,
        )

        def _factory(**kwargs):
            return SimpleNamespace(**kwargs)

        with patch(
            "app.services.inventory_service.InventoryLedgerEntry"
        ) as ledger_model, patch(
            "app.services.inventory_service.db.session.add"
        ), patch(
            "app.services.inventory_service.db.session.commit"
        ):
            ledger_model.query.filter_by.return_value.first.return_value = None
            ledger_model.side_effect = _factory

            entry = InventoryService.register_inventory_ledger_for_movement(movement)

        self.assertEqual(entry.source_bucket, "finished_goods")
        self.assertEqual(entry.destination_bucket, "waste_finished_goods")
        self.assertEqual(entry.source_account_code, "188")
        self.assertEqual(entry.destination_account_code, "800")
        self.assertEqual(entry.amount, 10.0)


if __name__ == "__main__":
    unittest.main()
