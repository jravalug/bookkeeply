from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.income_management_service import IncomeManagementService


class TestIncomeInventorySyncRules(unittest.TestCase):
    def setUp(self):
        self.service = IncomeManagementService()

    def test_sync_sale_detail_creates_consumption_for_completed_sale(self):
        sale = SimpleNamespace(id=11, business_id=3, status="completed", excluded=False)
        sale_detail = SimpleNamespace(id=21)

        item_filter = MagicMock()
        item_filter.filter.return_value.all.return_value = [
            SimpleNamespace(id=101, unit="kg")
        ]

        fake_inventory_item_model = SimpleNamespace(query=item_filter, id=MagicMock())
        fake_inventory_item_model.id.in_.return_value = True

        with patch.object(
            self.service,
            "_build_desired_consumption_by_item_for_sale_detail",
            return_value={101: 3.0},
        ), patch.object(
            self.service,
            "_calculate_synced_consumption_by_item_for_sale_detail",
            return_value={101: 0.0},
        ), patch.object(
            self.service,
            "_resolve_inventory_account_code_for_sale",
            return_value="1105",
        ), patch(
            "app.services.income_management_service.InventoryItem",
            fake_inventory_item_model,
        ), patch(
            "app.services.income_management_service.InventoryService.create_movement"
        ) as create_movement:
            self.service._sync_inventory_for_sale_detail(sale, sale_detail)

        create_movement.assert_called_once()
        kwargs = create_movement.call_args.kwargs
        self.assertEqual(kwargs["movement_type"], "consumption")
        self.assertEqual(kwargs["quantity"], 3.0)
        self.assertEqual(kwargs["reference_type"], "sale_inventory_line")
        self.assertEqual(kwargs["reference_id"], 21)

    def test_sync_sale_detail_reverses_when_sale_not_completed(self):
        sale = SimpleNamespace(id=12, business_id=3, status="cancelled", excluded=False)
        sale_detail = SimpleNamespace(id=22)

        item_filter = MagicMock()
        item_filter.filter.return_value.all.return_value = [
            SimpleNamespace(id=101, unit="kg")
        ]

        fake_inventory_item_model = SimpleNamespace(query=item_filter, id=MagicMock())
        fake_inventory_item_model.id.in_.return_value = True

        with patch.object(
            self.service,
            "_calculate_synced_consumption_by_item_for_sale_detail",
            return_value={101: 2.5},
        ), patch.object(
            self.service,
            "_resolve_inventory_account_code_for_sale",
            return_value="1105",
        ), patch(
            "app.services.income_management_service.InventoryItem",
            fake_inventory_item_model,
        ), patch(
            "app.services.income_management_service.InventoryService.create_movement"
        ) as create_movement:
            self.service._sync_inventory_for_sale_detail(sale, sale_detail)

        create_movement.assert_called_once()
        kwargs = create_movement.call_args.kwargs
        self.assertEqual(kwargs["movement_type"], "adjustment")
        self.assertEqual(kwargs["adjustment_kind"], "positive")
        self.assertEqual(kwargs["quantity"], 2.5)

    def test_update_income_triggers_inventory_sync(self):
        income = SimpleNamespace(id=40)
        form = SimpleNamespace(
            payment_method=SimpleNamespace(data="cash"),
            sale_number=SimpleNamespace(data="001"),
            date=SimpleNamespace(data="2026-03-10"),
            status=SimpleNamespace(data="completed"),
            excluded=SimpleNamespace(data=False),
            discount=SimpleNamespace(data=0.0),
            tax=SimpleNamespace(data=0.0),
            specific_business_id=SimpleNamespace(data=None),
            debtor_type=SimpleNamespace(data=None),
            debtor_natural_full_name=SimpleNamespace(data=None),
            debtor_natural_identity_number=SimpleNamespace(data=None),
            debtor_natural_bank_account=SimpleNamespace(data=None),
            debtor_legal_entity_name=SimpleNamespace(data=None),
            debtor_legal_reeup_code=SimpleNamespace(data=None),
            debtor_legal_address=SimpleNamespace(data=None),
            debtor_legal_credit_branch=SimpleNamespace(data=None),
            debtor_legal_bank_account=SimpleNamespace(data=None),
            debtor_legal_contract_number=SimpleNamespace(data=None),
        )

        updated_income = SimpleNamespace(id=40, products=[])

        with patch.object(
            self.service.repository,
            "update_sale",
            return_value=updated_income,
        ), patch.object(
            self.service,
            "_sync_inventory_for_sale",
        ) as sync_mock:
            result = self.service.update_income(income, form)

        self.assertIs(result, updated_income)
        sync_mock.assert_called_once_with(updated_income)

    def test_remove_product_from_income_forces_inventory_reset(self):
        income = SimpleNamespace(id=51)
        sale_detail = SimpleNamespace(id=61, product_id=71)
        removed_product = SimpleNamespace(id=71, name="Pan")

        fake_product_model = SimpleNamespace(
            query=SimpleNamespace(get_or_404=MagicMock(return_value=removed_product))
        )

        with patch.object(
            self.service,
            "_sync_inventory_for_sale_detail",
        ) as sync_mock, patch(
            "app.services.income_management_service.Product",
            fake_product_model,
        ), patch.object(
            self.service.repository,
            "remove_sale_detail",
        ) as remove_detail_mock:
            result = self.service.remove_product_from_income(income, sale_detail)

        self.assertIs(result, removed_product)
        sync_mock.assert_called_once_with(
            sale=income,
            sale_detail=sale_detail,
            force_reset=True,
        )
        remove_detail_mock.assert_called_once_with(51, 61)

    def test_sync_sale_detail_raises_for_product_without_recipe(self):
        sale = SimpleNamespace(id=71, business_id=3, status="completed", excluded=False)
        product = SimpleNamespace(id=9, name="Cafe", raw_materials=[])
        sale_detail = SimpleNamespace(id=31, quantity=2, product=product)

        with self.assertRaises(ValueError) as ctx:
            self.service._sync_inventory_for_sale_detail(sale, sale_detail)

        self.assertIn("no tiene materias primas configuradas", str(ctx.exception))

    def test_sync_sale_detail_raises_for_missing_raw_material_reference(self):
        sale = SimpleNamespace(id=72, business_id=3, status="completed", excluded=False)
        recipe_line = SimpleNamespace(
            raw_material_id=999, raw_material=None, quantity=1.5
        )
        product = SimpleNamespace(id=10, name="Pizza", raw_materials=[recipe_line])
        sale_detail = SimpleNamespace(id=32, quantity=1, product=product)

        fake_inventory_item_model = SimpleNamespace(
            query=SimpleNamespace(get=MagicMock(return_value=None))
        )

        with patch(
            "app.services.income_management_service.InventoryItem",
            fake_inventory_item_model,
        ), self.assertRaises(ValueError) as ctx:
            self.service._sync_inventory_for_sale_detail(sale, sale_detail)

        self.assertIn("Materia prima inexistente", str(ctx.exception))
        self.assertIn("inventory_item_id=999", str(ctx.exception))

    def test_sync_inventory_for_sale_aggregates_recipe_issues(self):
        product_without_recipe = SimpleNamespace(id=1, name="Pan", raw_materials=[])
        product_with_missing_material = SimpleNamespace(
            id=2,
            name="Jugo",
            raw_materials=[
                SimpleNamespace(raw_material_id=404, raw_material=None, quantity=1.0)
            ],
        )
        sale = SimpleNamespace(
            id=73,
            business_id=3,
            status="completed",
            excluded=False,
            products=[
                SimpleNamespace(id=41, quantity=1, product=product_without_recipe),
                SimpleNamespace(
                    id=42, quantity=1, product=product_with_missing_material
                ),
            ],
        )

        fake_inventory_item_model = SimpleNamespace(
            query=SimpleNamespace(get=MagicMock(return_value=None))
        )

        with patch(
            "app.services.income_management_service.InventoryItem",
            fake_inventory_item_model,
        ), self.assertRaises(ValueError) as ctx:
            self.service._sync_inventory_for_sale(sale)

        self.assertIn("Pan", str(ctx.exception))
        self.assertIn("Jugo", str(ctx.exception))

    def test_build_desired_consumption_applies_unit_conversion_equivalences(self):
        raw_material = SimpleNamespace(id=201, unit="g")
        recipe_line = SimpleNamespace(
            raw_material_id=201,
            raw_material=raw_material,
            quantity=0.25,
            unit="kg",
        )
        product = SimpleNamespace(
            id=31,
            name="Masa de pizza",
            raw_materials=[recipe_line],
            is_batch_prepared=False,
            batch_size=1,
        )
        sale = SimpleNamespace(id=88, business_id=3)
        sale_detail = SimpleNamespace(id=45, quantity=2, product=product)

        with patch(
            "app.services.income_management_service.InventoryService._resolve_quantity_in_item_base_unit",
            return_value=(250.0, "g", 1000.0, False),
        ) as resolve_conversion:
            desired = self.service._build_desired_consumption_by_item_for_sale_detail(
                sale=sale,
                sale_detail=sale_detail,
            )

        self.assertEqual(desired, {201: 500.0})
        resolve_conversion.assert_called_once_with(
            business_id=3,
            inventory_item=raw_material,
            quantity=0.25,
            unit="kg",
        )

    def test_build_desired_consumption_uses_batch_size_as_serving_divisor(self):
        raw_material = SimpleNamespace(id=202, unit="g")
        recipe_line = SimpleNamespace(
            raw_material_id=202,
            raw_material=raw_material,
            quantity=2.0,
            unit="kg",
        )
        product = SimpleNamespace(
            id=32,
            name="Salsa base",
            raw_materials=[recipe_line],
            is_batch_prepared=True,
            batch_size=4,
        )
        sale = SimpleNamespace(id=89, business_id=3)
        sale_detail = SimpleNamespace(id=46, quantity=3, product=product)

        with patch(
            "app.services.income_management_service.InventoryService._resolve_quantity_in_item_base_unit",
            return_value=(500.0, "g", 1000.0, False),
        ) as resolve_conversion:
            desired = self.service._build_desired_consumption_by_item_for_sale_detail(
                sale=sale,
                sale_detail=sale_detail,
            )

        self.assertEqual(desired, {202: 1500.0})
        resolve_conversion.assert_called_once_with(
            business_id=3,
            inventory_item=raw_material,
            quantity=0.5,
            unit="kg",
        )


if __name__ == "__main__":
    unittest.main()
