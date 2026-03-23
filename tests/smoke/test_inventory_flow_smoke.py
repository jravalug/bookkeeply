from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import (
    ACAccount,
    Business,
    Client,
    InventoryItem,
    InventoryMovement,
    InventoryWipBalance,
)
from app.services.inventory_service import InventoryService


class TestInventoryFlowSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        cls.app_context.pop()

    def test_smoke_inventory_wip_and_account_adoption_flow(self):
        client = Client(name="Cliente Smoke")
        business = Business(
            name="Negocio Smoke",
            client=client,
            business_activity=Business.ACTIVITY_RESTAURANT,
            inventory_flow_wip_enabled=True,
        )
        item = InventoryItem(name="Insumo Smoke", unit="kg", stock=0)
        account = ACAccount(code="7101", name="Produccion en proceso")
        db.session.add_all([client, business, item, account])
        db.session.commit()

        adoption = InventoryService.adopt_account_by_code(
            business_id=business.id,
            account_code="7101",
            actor="smoke-test",
            source="unittest",
        )
        self.assertTrue(adoption.is_active)

        supply = InventoryService.create_supply(
            business_id=business.id,
            inventory_item_id=item.id,
            product_variant="Surtido Smoke",
            is_active=True,
        )
        self.assertEqual(supply.business_id, business.id)

        purchase = InventoryService.create_movement(
            business_id=business.id,
            inventory_item_id=item.id,
            movement_type="purchase",
            quantity=12,
            unit="kg",
            account_code="7101",
            document="FAC-SMOKE-001",
            notes="entrada inicial smoke",
        )
        self.assertEqual(purchase.movement_type, "purchase")

        wip_balance = InventoryService.create_wip_balance(
            business_id=business.id,
            inventory_item_id=item.id,
            quantity=5,
            unit="kg",
            account_code="7101",
            notes="pase a wip smoke",
        )
        self.assertEqual(wip_balance.status, InventoryWipBalance.STATUS_OPEN)
        self.assertEqual(wip_balance.remaining_quantity, 5)

        finished = InventoryService.finish_wip_balance(
            business_id=business.id,
            wip_balance_id=wip_balance.id,
            account_code="7101",
            notes="cierre smoke",
        )
        self.assertEqual(finished.status, InventoryWipBalance.STATUS_FINISHED)
        self.assertEqual(finished.remaining_quantity, 0)

        movement_types = {
            movement.movement_type
            for movement in InventoryMovement.query.filter_by(
                business_id=business.id
            ).all()
        }
        self.assertIn("purchase", movement_types)
        self.assertIn("transfer", movement_types)
        self.assertIn("wip_close", movement_types)


if __name__ == "__main__":
    unittest.main()
