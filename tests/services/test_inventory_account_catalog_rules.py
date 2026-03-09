from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class TestInventoryAccountCatalogRules(unittest.TestCase):
    def test_update_catalog_account_rejects_normative(self):
        fake_account = SimpleNamespace(id=5, code="1586", is_normative=True)

        with patch("app.services.inventory_service.ACAccount") as account_model:
            account_model.query.filter_by.return_value.first.return_value = fake_account
            with self.assertRaises(ValueError) as ctx:
                InventoryService.update_catalog_account(
                    account_code="1586",
                    new_code="1586",
                    new_name="Produccion para la venta",
                )

        self.assertIn("normativo", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
