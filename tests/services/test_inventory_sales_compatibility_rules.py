from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class TestInventorySalesCompatibilityRules(unittest.TestCase):
    def test_transfer_to_sales_floor_rejects_when_flow_disabled(self):
        with patch(
            "app.services.inventory_service.InventoryService._resolve_business_inventory_flows",
            return_value=(False, True),
        ):
            with self.assertRaises(ValueError):
                InventoryService.transfer_to_sales_floor(
                    business_id=1,
                    inventory_item_id=4,
                    quantity=1,
                    unit="kg",
                    account_code="7101",
                )

    def test_transfer_to_sales_floor_rejects_production_only_item(self):
        with patch(
            "app.services.inventory_service.InventoryService._resolve_business_inventory_flows",
            return_value=(True, True),
        ), patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=SimpleNamespace(usage_type="production_input"),
        ):
            with self.assertRaises(ValueError):
                InventoryService.transfer_to_sales_floor(
                    business_id=1,
                    inventory_item_id=4,
                    quantity=1,
                    unit="kg",
                    account_code="7101",
                )

    def test_create_wip_balance_rejects_when_wip_flow_disabled(self):
        with patch(
            "app.services.inventory_service.InventoryService._resolve_business_inventory_flows",
            return_value=(True, False),
        ):
            with self.assertRaises(ValueError):
                InventoryService.create_wip_balance(
                    business_id=2,
                    inventory_item_id=9,
                    quantity=2,
                    unit="kg",
                    account_code="7101",
                )

    def test_create_wip_balance_rejects_sale_direct_item(self):
        with patch(
            "app.services.inventory_service.InventoryService._resolve_business_inventory_flows",
            return_value=(True, True),
        ), patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=SimpleNamespace(usage_type="sale_direct"),
        ):
            with self.assertRaises(ValueError):
                InventoryService.create_wip_balance(
                    business_id=2,
                    inventory_item_id=9,
                    quantity=2,
                    unit="kg",
                    account_code="7101",
                )


if __name__ == "__main__":
    unittest.main()
