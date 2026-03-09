from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class TestInventorySalesFloorRules(unittest.TestCase):
    def test_list_sales_floor_alerts_calculates_suggestions(self):
        fake_stock = SimpleNamespace(
            inventory_item_id=7,
            inventory_item=SimpleNamespace(name="Harina"),
            current_quantity=2.0,
            min_quantity=3.0,
            max_quantity=10.0,
        )

        with patch(
            "app.services.inventory_service.InventoryService.list_sales_floor_stocks",
            return_value=[fake_stock],
        ), patch(
            "app.services.inventory_service.InventoryService._calculate_sales_floor_average_7_days",
            return_value=1.0,
        ):
            rows = InventoryService.list_sales_floor_alerts(business_id=1)

        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["low_stock"])
        self.assertEqual(rows[0]["suggestion_to_max"], 8.0)
        self.assertEqual(rows[0]["suggestion_by_avg_7_days"], 5.0)

    def test_transfer_to_sales_floor_increments_sales_floor_quantity(self):
        fake_movement = SimpleNamespace(id=55, destination="sales_floor")
        fake_stock = SimpleNamespace(current_quantity=1.5)

        with patch(
            "app.services.inventory_service.InventoryService.create_movement",
            return_value=fake_movement,
        ) as create_movement_mock, patch(
            "app.services.inventory_service.InventoryService._get_or_create_sales_floor_stock",
            return_value=fake_stock,
        ), patch(
            "app.services.inventory_service.db.session.commit"
        ) as commit_mock:
            movement, stock = InventoryService.transfer_to_sales_floor(
                business_id=4,
                inventory_item_id=9,
                quantity=2.0,
                unit="kg",
                account_code="7101",
                lot_code="L-02",
                notes="reposicion",
            )

        self.assertEqual(movement.id, 55)
        self.assertEqual(stock.current_quantity, 3.5)
        create_movement_mock.assert_called_once_with(
            business_id=4,
            inventory_item_id=9,
            movement_type="transfer",
            destination="sales_floor",
            quantity=2.0,
            unit="kg",
            account_code="7101",
            lot_code="L-02",
            notes="reposicion",
        )
        commit_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
