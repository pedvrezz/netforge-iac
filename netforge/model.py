from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
import re
from typing import Any

MAC_PATTERN = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")


@dataclass(frozen=True)
class Site:
    name: str
    domain: str
    trunk_interface: str
    dhcp_lease: str


@dataclass(frozen=True)
class Network:
    name: str
    vlan_id: int
    subnet: IPv4Network
    gateway: IPv4Address
    dhcp_start: IPv4Address | None
    dhcp_end: IPv4Address | None
    dns_servers: tuple[IPv4Address, ...]
    description: str

    @property
    def dhcp_enabled(self) -> bool:
        return self.dhcp_start is not None and self.dhcp_end is not None


@dataclass(frozen=True)
class Host:
    name: str
    network: str
    address: IPv4Address
    mac: str
    description: str


@dataclass(frozen=True)
class Blueprint:
    site: Site
    networks: tuple[Network, ...]
    hosts: tuple[Host, ...]


def _required_text(mapping: dict[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _optional_text(mapping: dict[str, Any], key: str, default: str = "") -> str:
    value = mapping.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value.strip()


def parse_blueprint(data: dict[str, Any]) -> Blueprint:
    site_data = data.get("site")
    if not isinstance(site_data, dict):
        raise ValueError("[site] section is required")

    site = Site(
        name=_required_text(site_data, "name", "site"),
        domain=_required_text(site_data, "domain", "site"),
        trunk_interface=_optional_text(site_data, "trunk_interface", "eth1"),
        dhcp_lease=_optional_text(site_data, "dhcp_lease", "12h"),
    )
    if not NAME_PATTERN.fullmatch(site.trunk_interface):
        raise ValueError("site.trunk_interface contains unsupported characters")

    raw_networks = data.get("networks")
    if not isinstance(raw_networks, list) or not raw_networks:
        raise ValueError("At least one [[networks]] entry is required")

    networks: list[Network] = []
    for index, raw in enumerate(raw_networks, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"networks[{index}] must be a table")
        context = f"networks[{index}]"
        name = _required_text(raw, "name", context)
        if not NAME_PATTERN.fullmatch(name):
            raise ValueError(f"{context}.name contains unsupported characters")
        try:
            vlan_id = int(raw["vlan_id"])
            subnet = IPv4Network(str(raw["subnet"]), strict=True)
            gateway = IPv4Address(str(raw["gateway"]))
        except KeyError as exc:
            raise ValueError(f"{context}.{exc.args[0]} is required") from exc
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{context} has an invalid VLAN, subnet or gateway: {exc}") from exc

        dhcp_start_raw = raw.get("dhcp_start")
        dhcp_end_raw = raw.get("dhcp_end")
        if (dhcp_start_raw is None) != (dhcp_end_raw is None):
            raise ValueError(f"{context} must define both dhcp_start and dhcp_end, or neither")
        dhcp_start = IPv4Address(str(dhcp_start_raw)) if dhcp_start_raw is not None else None
        dhcp_end = IPv4Address(str(dhcp_end_raw)) if dhcp_end_raw is not None else None

        raw_dns = raw.get("dns_servers", [str(gateway)])
        if not isinstance(raw_dns, list) or not raw_dns:
            raise ValueError(f"{context}.dns_servers must be a non-empty array")
        dns_servers = tuple(IPv4Address(str(item)) for item in raw_dns)

        networks.append(Network(
            name=name,
            vlan_id=vlan_id,
            subnet=subnet,
            gateway=gateway,
            dhcp_start=dhcp_start,
            dhcp_end=dhcp_end,
            dns_servers=dns_servers,
            description=_optional_text(raw, "description"),
        ))

    raw_hosts = data.get("hosts", [])
    if not isinstance(raw_hosts, list):
        raise ValueError("[[hosts]] entries must be tables")

    hosts: list[Host] = []
    for index, raw in enumerate(raw_hosts, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"hosts[{index}] must be a table")
        context = f"hosts[{index}]"
        mac = _required_text(raw, "mac", context).upper()
        if not MAC_PATTERN.fullmatch(mac):
            raise ValueError(f"{context}.mac must use AA:BB:CC:DD:EE:FF format")
        hosts.append(Host(
            name=_required_text(raw, "name", context),
            network=_required_text(raw, "network", context),
            address=IPv4Address(_required_text(raw, "address", context)),
            mac=mac,
            description=_optional_text(raw, "description"),
        ))

    blueprint = Blueprint(site=site, networks=tuple(networks), hosts=tuple(hosts))
    validate_blueprint(blueprint)
    return blueprint


def validate_blueprint(blueprint: Blueprint) -> None:
    network_names: set[str] = set()
    vlan_ids: set[int] = set()

    for network in blueprint.networks:
        lowered = network.name.casefold()
        if lowered in network_names:
            raise ValueError(f"Duplicate network name: {network.name}")
        network_names.add(lowered)
        if network.vlan_id in vlan_ids:
            raise ValueError(f"Duplicate VLAN ID: {network.vlan_id}")
        vlan_ids.add(network.vlan_id)

        if network.vlan_id < 1 or network.vlan_id > 4094:
            raise ValueError(f"Network {network.name}: vlan_id must be between 1 and 4094")
        if not network.subnet.is_private:
            raise ValueError(f"Network {network.name}: subnet must be private IPv4 space")
        if network.gateway not in network.subnet or network.gateway in {
            network.subnet.network_address,
            network.subnet.broadcast_address,
        }:
            raise ValueError(f"Network {network.name}: gateway must be a usable address inside the subnet")

        if network.dhcp_enabled:
            assert network.dhcp_start is not None and network.dhcp_end is not None
            if network.dhcp_start > network.dhcp_end:
                raise ValueError(f"Network {network.name}: dhcp_start must not exceed dhcp_end")
            for address in (network.dhcp_start, network.dhcp_end):
                if address not in network.subnet or address in {
                    network.subnet.network_address,
                    network.subnet.broadcast_address,
                }:
                    raise ValueError(f"Network {network.name}: DHCP range must use usable addresses inside the subnet")
            if network.dhcp_start <= network.gateway <= network.dhcp_end:
                raise ValueError(f"Network {network.name}: DHCP range must not include the gateway")

    for left_index, left in enumerate(blueprint.networks):
        for right in blueprint.networks[left_index + 1:]:
            if left.subnet.overlaps(right.subnet):
                raise ValueError(f"Overlapping subnets: {left.name} {left.subnet} and {right.name} {right.subnet}")

    by_name = {network.name.casefold(): network for network in blueprint.networks}
    host_names: set[str] = set()
    host_addresses: set[IPv4Address] = set()
    host_macs: set[str] = set()
    for host in blueprint.hosts:
        if not NAME_PATTERN.fullmatch(host.name):
            raise ValueError(f"Host name contains unsupported characters: {host.name}")
        if host.name.casefold() in host_names:
            raise ValueError(f"Duplicate host name: {host.name}")
        host_names.add(host.name.casefold())
        if host.address in host_addresses:
            raise ValueError(f"Duplicate host address: {host.address}")
        host_addresses.add(host.address)
        if host.mac in host_macs:
            raise ValueError(f"Duplicate host MAC: {host.mac}")
        host_macs.add(host.mac)

        network = by_name.get(host.network.casefold())
        if network is None:
            raise ValueError(f"Host {host.name}: unknown network '{host.network}'")
        if host.address not in network.subnet or host.address in {
            network.subnet.network_address,
            network.subnet.broadcast_address,
            network.gateway,
        }:
            raise ValueError(f"Host {host.name}: address must be usable inside network {network.name}")
        if network.dhcp_enabled:
            assert network.dhcp_start is not None and network.dhcp_end is not None
            if network.dhcp_start <= host.address <= network.dhcp_end:
                raise ValueError(f"Host {host.name}: static address overlaps the DHCP pool")
