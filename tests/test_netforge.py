from __future__ import annotations

from pathlib import Path
import tempfile
import tomllib
import unittest

from netforge.generator import generate
from netforge.model import parse_blueprint


ROOT = Path(__file__).resolve().parents[1]


class NetForgeTests(unittest.TestCase):
    def load_example(self):
        with (ROOT / "examples" / "lab.toml").open("rb") as handle:
            return parse_blueprint(tomllib.load(handle))

    def test_example_is_valid(self):
        blueprint = self.load_example()
        self.assertEqual(4, len(blueprint.networks))
        self.assertEqual(3, len(blueprint.hosts))

    def test_generates_expected_artifacts(self):
        blueprint = self.load_example()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "generated"
            files = generate(blueprint, output)
            self.assertGreaterEqual(len(files), 10)
            dnsmasq = (output / "dnsmasq" / "vlans.conf").read_text(encoding="utf-8")
            self.assertIn("interface=vlan10", dnsmasq)
            self.assertIn("dhcp-host=02:00:00:00:40:10,10.10.40.10,ad01", dnsmasq)
            trunk = (output / "systemd-networkd" / "10-trunk.network").read_text(encoding="utf-8")
            self.assertIn("VLAN=vlan40", trunk)

    def test_rejects_overlapping_subnets(self):
        data = {
            "site": {"name": "test", "domain": "test.local"},
            "networks": [
                {"name": "one", "vlan_id": 10, "subnet": "10.0.0.0/24", "gateway": "10.0.0.1"},
                {"name": "two", "vlan_id": 20, "subnet": "10.0.0.128/25", "gateway": "10.0.0.129"},
            ],
        }
        with self.assertRaisesRegex(ValueError, "Overlapping subnets"):
            parse_blueprint(data)

    def test_rejects_static_ip_in_dhcp_pool(self):
        data = {
            "site": {"name": "test", "domain": "test.local"},
            "networks": [{
                "name": "users", "vlan_id": 10, "subnet": "10.0.10.0/24", "gateway": "10.0.10.1",
                "dhcp_start": "10.0.10.100", "dhcp_end": "10.0.10.200"
            }],
            "hosts": [{
                "name": "bad-host", "network": "users", "address": "10.0.10.150",
                "mac": "02:00:00:00:00:01"
            }]
        }
        with self.assertRaisesRegex(ValueError, "overlaps the DHCP pool"):
            parse_blueprint(data)


if __name__ == "__main__":
    unittest.main()
