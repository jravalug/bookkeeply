from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class TestInventoryUnitConversionRules(unittest.TestCase):
    def test_create_movement_converts_quantity_to_item_base_unit(self):
        item = SimpleNamespace(
            id=52,
            unit="g",
            stock=0.0,
            min_stock=None,
            average_unit_cost=0.0,
        )
        conversion = SimpleNamespace(factor=1000.0)

        def _factory(**kwargs):
            return SimpleNamespace(id=991, **kwargs)

        with patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=item,
        ), patch(
            "app.services.inventory_service.InventoryService.validate_account_is_adopted"
        ), patch(
            "app.services.inventory_service.InventoryUnitConversion"
        ) as conversion_model, patch(
            "app.services.inventory_service.InventoryMovement",
            side_effect=_factory,
        ), patch(
            "app.services.inventory_service.InventoryService.register_inventory_ledger_for_movement"
        ), patch(
            "app.services.inventory_service.db.session.add"
        ), patch(
            "app.services.inventory_service.db.session.commit"
        ):
            conversion_model.query.filter_by.return_value.first.return_value = (
                conversion
            )
            movement = InventoryService.create_movement(
                business_id=3,
                inventory_item_id=52,
                movement_type="purchase",
                quantity=0.123456,
                unit="kg",
                account_code="7101",
                document="FAC-CNV-001",
                lot_code="L-CNV-001",
                notes="Conversion manual para redondeo",
            )

        self.assertEqual(movement.unit, "g")
        self.assertEqual(movement.quantity, 123.46)
        self.assertEqual(item.stock, 123.46)

    def test_create_movement_rejects_when_conversion_is_missing(self):
        item = SimpleNamespace(
            id=53,
            unit="ml",
            stock=0.0,
            min_stock=None,
            average_unit_cost=0.0,
        )

        with patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=item,
        ), patch(
            "app.services.inventory_service.InventoryService.validate_account_is_adopted"
        ), patch(
            "app.services.inventory_service.InventoryUnitConversion"
        ) as conversion_model:
            conversion_model.query.filter_by.return_value.first.return_value = None
            with self.assertRaises(ValueError):
                InventoryService.create_movement(
                    business_id=3,
                    inventory_item_id=53,
                    movement_type="purchase",
                    quantity=1,
                    unit="l",
                    account_code="7101",
                    document="FAC-CNV-002",
                    lot_code="L-CNV-002",
                )

    def test_create_movement_requires_notes_when_conversion_is_non_exact(self):
        item = SimpleNamespace(
            id=54,
            unit="g",
            stock=0.0,
            min_stock=None,
            average_unit_cost=0.0,
        )
        conversion = SimpleNamespace(factor=1000.0)

        with patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=item,
        ), patch(
            "app.services.inventory_service.InventoryService.validate_account_is_adopted"
        ), patch(
            "app.services.inventory_service.InventoryUnitConversion"
        ) as conversion_model:
            conversion_model.query.filter_by.return_value.first.return_value = (
                conversion
            )
            with self.assertRaises(ValueError) as ctx:
                InventoryService.create_movement(
                    business_id=3,
                    inventory_item_id=54,
                    movement_type="purchase",
                    quantity=0.123456,
                    unit="kg",
                    account_code="7101",
                    document="FAC-CNV-003",
                    lot_code="L-CNV-003",
                )

        self.assertIn("motivo", str(ctx.exception).lower())
        self.assertIn("conversion", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
