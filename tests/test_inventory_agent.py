import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = (
    Path(__file__).parents[1]
    / "rpm"
    / "linux-inventory-agent"
    / "src"
    / "linux_inventory_agent.py"
)
SPEC = importlib.util.spec_from_file_location("linux_inventory_agent", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class InventoryAgentTests(unittest.TestCase):
    def test_reads_os_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "os-release"
            path.write_text('PRETTY_NAME="Red Hat Enterprise Linux 9.8"\nID="rhel"\nVERSION_ID="9.8"\n')
            self.assertEqual(MODULE.read_operating_system(path)["id"], "rhel")

    @patch.object(MODULE, "run_command")
    def test_parses_installed_packages(self, run_command):
        run_command.return_value = {
            "success": True,
            "output": "python3|3.9.18-1.el9|x86_64\nbash|5.1.8-9.el9|x86_64",
            "error": "",
        }
        result = MODULE.collect_installed_packages()
        self.assertEqual([item["name"] for item in result["packages"]], ["bash", "python3"])

    @patch.object(MODULE, "run_command")
    def test_command_failure_is_reported(self, run_command):
        run_command.return_value = {"success": False, "output": "", "error": "rpm missing"}
        result = MODULE.collect_installed_packages()
        self.assertEqual(result["packages"], [])
        self.assertEqual(result["error"], "rpm missing")


if __name__ == "__main__":
    unittest.main()

