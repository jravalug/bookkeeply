from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class TestInventoryAccountSubaccountRules(unittest.TestCase):
    def test_unadopt_account_blocks_when_has_active_subaccounts(self):
        fake_account = SimpleNamespace(id=10, code="7101")
        fake_adoption = SimpleNamespace(id=30, is_active=True)

        with patch("app.services.inventory_service.ACAccount") as ac_model, patch(
            "app.services.inventory_service.BusinessAccountAdoption"
        ) as adoption_model, patch(
            "app.services.inventory_service.InventoryMovement"
        ) as movement_model, patch(
            "app.services.inventory_service.BusinessSubAccount"
        ) as subaccount_model:
            ac_model.query.filter_by.return_value.first.return_value = fake_account
            adoption_model.query.filter_by.return_value.first.return_value = (
                fake_adoption
            )
            movement_model.query.filter_by.return_value.first.return_value = None
            subaccount_model.query.filter_by.return_value.first.return_value = (
                SimpleNamespace(id=44, is_active=True)
            )

            with self.assertRaises(ValueError) as ctx:
                InventoryService.unadopt_account_by_code(
                    business_id=7,
                    account_code="7101",
                )

        self.assertIn("subcuentas activas", str(ctx.exception))

    def test_create_business_subaccount_requires_adopted_account_and_logs_audit(self):
        fake_adoption = SimpleNamespace(id=9)

        def _factory(**kwargs):
            return SimpleNamespace(id=55, **kwargs)

        with patch(
            "app.services.inventory_service.InventoryService._get_active_adoption_or_fail",
            return_value=fake_adoption,
        ), patch(
            "app.services.inventory_service.BusinessSubAccount"
        ) as subaccount_model, patch(
            "app.services.inventory_service.db.session.add"
        ) as add_mock, patch(
            "app.services.inventory_service.db.session.commit"
        ) as commit_mock, patch(
            "app.services.inventory_service.InventoryService._log_business_subaccount_event"
        ) as audit_mock:
            subaccount_model.query.filter_by.return_value.first.return_value = None
            subaccount_model.side_effect = _factory

            created = InventoryService.create_business_subaccount(
                business_id=3,
                account_code="7101",
                code="11001",
                name="Materias primas cocina",
                actor="tester",
            )

        self.assertEqual(created.code, "11001")
        self.assertEqual(created.name, "Materias primas cocina")
        self.assertTrue(created.is_active)
        self.assertEqual(created.business_account_adoption_id, 9)
        add_mock.assert_called_once()
        commit_mock.assert_called_once()
        audit_mock.assert_called_once()

    def test_update_business_subaccount_updates_values_and_logs_audit(self):
        fake_subaccount = SimpleNamespace(
            id=77,
            business_id=5,
            business_account_adoption_id=11,
            code="11001",
            name="Nombre anterior",
            is_active=True,
        )

        with patch(
            "app.services.inventory_service.BusinessSubAccount"
        ) as subaccount_model, patch(
            "app.services.inventory_service.db.session.commit"
        ) as commit_mock, patch(
            "app.services.inventory_service.InventoryService._log_business_subaccount_event"
        ) as audit_mock:
            subaccount_model.query.get_or_404.return_value = fake_subaccount
            subaccount_model.query.filter.return_value.first.return_value = None

            updated = InventoryService.update_business_subaccount(
                business_id=5,
                business_sub_account_id=77,
                code="11002",
                name="Nombre nuevo",
                is_active=False,
                actor="tester",
            )

        self.assertEqual(updated.code, "11002")
        self.assertEqual(updated.name, "Nombre nuevo")
        self.assertFalse(updated.is_active)
        commit_mock.assert_called_once()
        audit_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
