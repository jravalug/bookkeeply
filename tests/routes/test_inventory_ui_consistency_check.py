from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestInventoryUiConsistencyCheck(unittest.TestCase):
    def _read(self, relative_path):
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    def test_item_list_uses_single_items_panel_include(self):
        content = self._read("app/templates/inventory/item_list.html")
        self.assertIn("inventory/partials/_item_panel.html", content)

    def test_accounting_manage_uses_single_content_include(self):
        content = self._read("app/templates/inventory/accounting_manage.html")
        self.assertIn("inventory/partials/_accounting_manage_content.html", content)

    def test_consumption_view_uses_single_content_include(self):
        content = self._read("app/templates/report/inventory_consumption.html")
        self.assertIn("report/partials/_inventory_consumption_content.html", content)


if __name__ == "__main__":
    unittest.main()
