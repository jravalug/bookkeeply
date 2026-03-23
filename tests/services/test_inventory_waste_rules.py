from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class TestInventoryWasteRules(unittest.TestCase):
    def test_create_movement_rejects_waste_without_reason(self):
        with self.assertRaises(ValueError):
            InventoryService.create_movement(
                business_id=1,
                inventory_item_id=1,
                movement_type="waste",
                destination="finished_goods",
                quantity=1,
                unit="kg",
                account_code="7101",
                waste_reason=None,
                waste_responsible="Operario 1",
            )

    def test_create_movement_rejects_waste_without_responsible(self):
        with self.assertRaises(ValueError):
            InventoryService.create_movement(
                business_id=1,
                inventory_item_id=1,
                movement_type="waste",
                destination="finished_goods",
                quantity=1,
                unit="kg",
                account_code="7101",
                waste_reason="rotura",
                waste_responsible="",
            )

    def test_create_movement_accepts_waste_with_file_evidence_url(self):
        item = SimpleNamespace(
            id=44,
            stock=10.0,
            min_stock=2.0,
            average_unit_cost=1.0,
        )

        def _movement_factory(**kwargs):
            return SimpleNamespace(id=901, **kwargs)

        with patch(
            "app.services.inventory_service.InventoryService._get_item_or_404",
            return_value=item,
        ), patch(
            "app.services.inventory_service.InventoryService.validate_account_is_adopted"
        ), patch(
            "app.services.inventory_service.InventoryService.register_inventory_ledger_for_movement"
        ), patch(
            "app.services.inventory_service.InventoryMovement",
            side_effect=_movement_factory,
        ), patch(
            "app.services.inventory_service.db.session.add"
        ), patch(
            "app.services.inventory_service.db.session.commit"
        ):
            movement = InventoryService.create_movement(
                business_id=1,
                inventory_item_id=44,
                movement_type="waste",
                destination="finished_goods",
                quantity=1,
                unit="kg",
                account_code="7101",
                waste_reason="rotura",
                waste_responsible="Operario 5",
                waste_evidence="Descripcion breve",
                waste_evidence_file_url="https://files.local/mermas/foto_44.jpg",
            )

        self.assertEqual(
            movement.waste_evidence_file_url,
            "https://files.local/mermas/foto_44.jpg",
        )

    def test_create_movement_rejects_waste_with_invalid_file_evidence_extension(self):
        with self.assertRaises(ValueError):
            InventoryService.create_movement(
                business_id=1,
                inventory_item_id=1,
                movement_type="waste",
                destination="finished_goods",
                quantity=1,
                unit="kg",
                account_code="7101",
                waste_reason="rotura",
                waste_responsible="Operario 1",
                waste_evidence_file_url="https://files.local/mermas/audio.mp3",
            )


if __name__ == "__main__":
    unittest.main()
