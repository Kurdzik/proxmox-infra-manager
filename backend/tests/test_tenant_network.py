import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from src.models import TenantVNet
from src.proxmox import ProxmoxAPIError
from src.services.tenant_network import (
    allocate_next_tenant_subnet,
    derive_tenant_network_settings,
    ensure_tenant_vnet,
)


class FakeAdapter:
    def __init__(self):
        self.zones = {}
        self.vnets = {}
        self.subnets = {}
        self.applied = False
        self.waited = False
        self.missing_status_code = 404
        self.task_log = []
        self.node_network = {}
        self.node_sdn_zone_content = {}
        self.node_network_after_calls = {}
        self.node_network_calls = {}

    def get_sdn_zone(self, zone):
        if zone not in self.zones:
            raise ProxmoxAPIError(self.missing_status_code, '{"data":null}')
        return self.zones[zone]

    def list_sdn_zones(self):
        return list(self.zones.values())

    def create_sdn_zone(self, zone, zone_type="simple", dhcp=None, ipam=None, nodes=None):
        self.zones[zone] = {
            "zone": zone,
            "type": zone_type,
            "dhcp": dhcp,
            "ipam": ipam,
            "nodes": nodes,
        }
        return self.zones[zone]

    def update_sdn_zone(self, zone, config):
        self.zones.setdefault(zone, {"zone": zone}).update(config)
        return self.zones[zone]

    def get_vnet(self, vnet_id):
        if vnet_id not in self.vnets:
            raise ProxmoxAPIError(self.missing_status_code, '{"data":null}')
        return self.vnets[vnet_id]

    def list_vnets(self):
        return list(self.vnets.values())

    def create_vnet(self, vnet_id, zone, tag=None):
        self.vnets[vnet_id] = {"vnet": vnet_id, "zone": zone, "tag": tag}
        return self.vnets[vnet_id]

    def list_sdn_subnets(self, vnet_id):
        return self.subnets.get(vnet_id, [])

    def create_sdn_subnet(self, vnet_id, subnet, gateway, dhcp_start, dhcp_end, snat=True):
        item = {
            "id": f"default-{subnet.replace('/', '-')}",
            "cidr": subnet,
            "gateway": gateway,
            "snat": int(snat),
            "dhcp-range": [{"start-address": dhcp_start, "end-address": dhcp_end}],
        }
        self.subnets.setdefault(vnet_id, []).append(item)
        return item

    def update_sdn_subnet(self, vnet_id, subnet_id, config):
        for item in self.subnets.get(vnet_id, []):
            if item["id"] == subnet_id:
                item.update(config)
                return item
        raise ProxmoxAPIError(404, "not found")

    def apply_sdn(self):
        self.applied = True
        return "UPID:pve:00000000:00000000:00000000:sdnreload::root@pam:"

    def wait_for_task(self, node, upid, poll_interval=5, timeout=900):
        self.waited = True

    def get_task_log(self, node, upid):
        return self.task_log

    def list_node_network(self, node):
        self.node_network_calls[node] = self.node_network_calls.get(node, 0) + 1
        delayed = self.node_network_after_calls.get(node)
        if delayed and self.node_network_calls[node] >= delayed[0]:
            return [{"iface": delayed[1]}]
        return self.node_network.get(node, [])

    def list_node_sdn_zone_content(self, node, zone):
        return self.node_sdn_zone_content.get((node, zone), [])


class TenantNetworkAllocationTests(unittest.TestCase):
    def test_allocates_first_free_24(self):
        self.assertEqual(allocate_next_tenant_subnet([], "10.100.0.0/16"), "10.100.0.0/24")

    def test_skips_used_24(self):
        subnet = allocate_next_tenant_subnet(["10.100.0.0/24"], "10.100.0.0/16")
        self.assertEqual(subnet, "10.100.1.0/24")

    def test_derives_gateway_and_dhcp_range(self):
        settings = derive_tenant_network_settings("10.100.5.0/24")
        self.assertEqual(settings.gateway, "10.100.5.1")
        self.assertEqual(settings.dhcp_start, "10.100.5.100")
        self.assertEqual(settings.dhcp_end, "10.100.5.199")

    def test_rejects_too_small_subnet(self):
        with self.assertRaises(RuntimeError):
            derive_tenant_network_settings("10.100.5.0/25")


class TenantNetworkEnsureTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(self.engine)

    def test_creates_tenant_vnet_zone_subnet_and_applies_sdn(self):
        adapter = FakeAdapter()
        tenant_id = "1234567890abcdef"

        with Session(self.engine) as session:
            vnet = ensure_tenant_vnet(session, adapter, tenant_id, commit=True)
            vnet_id = vnet.vnet_id
            subnet_cidr = vnet.subnet
            gateway = vnet.gateway
            dhcp_start = vnet.dhcp_start
            dhcp_end = vnet.dhcp_end

        self.assertEqual(vnet_id, "vn123456")
        self.assertEqual(subnet_cidr, "10.100.0.0/24")
        self.assertEqual(gateway, "10.100.0.1")
        self.assertEqual(dhcp_start, "10.100.0.100")
        self.assertEqual(dhcp_end, "10.100.0.199")
        self.assertTrue(adapter.applied)
        self.assertTrue(adapter.waited)

        subnet = adapter.subnets[vnet_id][0]
        self.assertEqual(subnet["cidr"], "10.100.0.0/24")
        self.assertEqual(subnet["dhcp-range"][0]["start-address"], "10.100.0.100")
        self.assertEqual(subnet["dhcp-range"][0]["end-address"], "10.100.0.199")

    def test_repairs_existing_hyphenated_vnet_id(self):
        adapter = FakeAdapter()
        tenant_id = "1bb7319876543210"

        with Session(self.engine) as session:
            session.add(
                TenantVNet(
                    tenant_id=tenant_id,
                    vnet_id="vnet-1bb731",
                    zone="default",
                    subnet="10.100.9.0/24",
                )
            )
            session.commit()
            vnet = ensure_tenant_vnet(session, adapter, tenant_id, commit=True)
            vnet_id = vnet.vnet_id

        self.assertEqual(vnet_id, "vn1bb731")
        self.assertIn("vn1bb731", adapter.vnets)

    def test_repairs_existing_too_long_vnet_id(self):
        adapter = FakeAdapter()
        tenant_id = "1bb7319876543210"

        with Session(self.engine) as session:
            session.add(
                TenantVNet(
                    tenant_id=tenant_id,
                    vnet_id="vnet1bb731",
                    zone="default",
                    subnet="10.100.10.0/24",
                )
            )
            session.commit()
            vnet = ensure_tenant_vnet(session, adapter, tenant_id, commit=True)
            vnet_id = vnet.vnet_id

        self.assertEqual(vnet_id, "vn1bb731")
        self.assertIn("vn1bb731", adapter.vnets)

    def test_treats_proxmox_500_data_null_as_missing_zone_and_vnet(self):
        adapter = FakeAdapter()
        adapter.missing_status_code = 500
        tenant_id = "2222227890abcdef"

        with Session(self.engine) as session:
            vnet = ensure_tenant_vnet(session, adapter, tenant_id, commit=True)
            vnet_id = vnet.vnet_id

        self.assertIn("default", adapter.zones)
        self.assertIn(vnet_id, adapter.vnets)
        self.assertTrue(adapter.applied)

    def test_restricts_zone_to_target_node_and_validates_bridge(self):
        adapter = FakeAdapter()
        adapter.node_network["pve1"] = [{"iface": "vn123456"}]
        tenant_id = "1234567890abcdef"

        with Session(self.engine) as session:
            ensure_tenant_vnet(session, adapter, tenant_id, target_node="pve1", commit=True)

        self.assertEqual(adapter.zones["default"]["nodes"], "pve1")

    def test_accepts_sdn_status_available_without_network_interface_listing(self):
        adapter = FakeAdapter()
        adapter.node_sdn_zone_content[("pve1", "default")] = [
            {"vnet": "vn123456", "status": "available"}
        ]
        tenant_id = "1234567890abcdef"

        with Session(self.engine) as session:
            ensure_tenant_vnet(session, adapter, tenant_id, target_node="pve1", commit=True)

        self.assertNotIn("pve1", adapter.node_network_calls)

    def test_waits_for_delayed_node_bridge(self):
        adapter = FakeAdapter()
        adapter.node_network_after_calls["pve1"] = (3, "vn444444")
        tenant_id = "4444447890abcdef"

        with (
            patch("src.services.tenant_network.DEFAULT_SDN_BRIDGE_WAIT_SECONDS", 1),
            patch("src.services.tenant_network.DEFAULT_SDN_BRIDGE_POLL_INTERVAL", 0),
            Session(self.engine) as session,
        ):
            ensure_tenant_vnet(session, adapter, tenant_id, target_node="pve1", commit=True)

        self.assertGreaterEqual(adapter.node_network_calls["pve1"], 3)

    def test_raises_when_sdn_apply_log_reports_missing_dnsmasq(self):
        adapter = FakeAdapter()
        adapter.task_log = [
            {
                "t": "Could not run before_regenerate for DHCP plugin dnsmasq "
                "cannot reload with missing 'dnsmasq' package "
            }
        ]
        tenant_id = "3333337890abcdef"

        with Session(self.engine) as session:
            with self.assertRaisesRegex(RuntimeError, "dnsmasq"):
                ensure_tenant_vnet(session, adapter, tenant_id, target_node="pve1", commit=True)

    def test_persists_existing_tenant_vnet_subnet(self):
        adapter = FakeAdapter()
        tenant_id = "abcdef1234567890"

        with Session(self.engine) as session:
            session.add(
                TenantVNet(
                    tenant_id=tenant_id,
                    vnet_id="vnet-abcdef",
                    zone="default",
                    subnet="10.100.7.0/24",
                )
            )
            session.commit()
            ensure_tenant_vnet(session, adapter, tenant_id, commit=True)
            stored = session.exec(select(TenantVNet).where(TenantVNet.tenant_id == tenant_id)).one()

        self.assertEqual(stored.subnet, "10.100.7.0/24")
        self.assertEqual(stored.gateway, "10.100.7.1")
        self.assertEqual(stored.dhcp_start, "10.100.7.100")
        self.assertEqual(stored.dhcp_end, "10.100.7.199")

    def test_repairs_existing_subnet_without_dhcp_range(self):
        adapter = FakeAdapter()
        adapter.zones["default"] = {
            "zone": "default",
            "type": "simple",
            "dhcp": "dnsmasq",
            "ipam": "pve",
        }
        adapter.vnets["vnfedcba"] = {"vnet": "vnfedcba", "zone": "default"}
        adapter.subnets["vnfedcba"] = [
            {
                "id": "default-10.100.8.0-24",
                "cidr": "10.100.8.0/24",
                "gateway": None,
                "dhcp-range": [],
            }
        ]
        tenant_id = "fedcba9876543210"

        with Session(self.engine) as session:
            session.add(
                TenantVNet(
                    tenant_id=tenant_id,
                    vnet_id="vnfedcba",
                    zone="default",
                    subnet="10.100.8.0/24",
                )
            )
            session.commit()
            ensure_tenant_vnet(session, adapter, tenant_id, commit=True)

        subnet = adapter.subnets["vnfedcba"][0]
        self.assertEqual(subnet["gateway"], "10.100.8.1")
        self.assertEqual(
            subnet["dhcp-range"],
            ["start-address=10.100.8.100,end-address=10.100.8.199"],
        )
        self.assertTrue(adapter.applied)


if __name__ == "__main__":
    unittest.main()
