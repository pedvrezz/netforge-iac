# NetForge IaC

NetForge IaC is a dependency-free network source-of-truth validator and configuration generator. You describe VLANs, subnets, DHCP ranges and static hosts once in TOML; NetForge checks the plan and generates documentation plus deployable building blocks.

## What it generates

- Network plan in Markdown
- `systemd-networkd` VLAN interfaces for a Linux router
- `dnsmasq` DHCP ranges, gateway/DNS options and reservations
- Firewall alias inventory in CSV
- Static host inventory in CSV
- Normalized JSON blueprint for other automation

## What it validates

- Duplicate VLAN IDs, names, IPs and MAC addresses
- Overlapping subnets
- Public instead of private IPv4 networks
- Invalid gateways and DHCP ranges
- Gateway included inside a DHCP pool
- Static addresses inside DHCP pools
- Hosts assigned to unknown networks

## Requirements

Python 3.11 or newer. No third-party Python package is required.

## Quick start

```bash
python3 -m netforge examples/lab.toml --check
python3 -m netforge examples/lab.toml --output generated --clean
```

Or install the CLI locally:

```bash
python3 -m pip install .
netforge examples/lab.toml --output generated --clean
```

## Source-of-truth example

```toml
[site]
name = "Company Lab"
domain = "lab.example"
trunk_interface = "eth1"

[[networks]]
name = "management"
vlan_id = 10
subnet = "10.10.10.0/24"
gateway = "10.10.10.1"
dhcp_start = "10.10.10.100"
dhcp_end = "10.10.10.199"
dns_servers = ["10.10.10.10"]
```

See `examples/lab.toml` for a complete four-VLAN design with static reservations.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Operational safety

Generated router files can interrupt connectivity if applied to the wrong interface. Review the diff, keep console or out-of-band access available and stage changes in a lab first.

NetForge deliberately does not generate permissive firewall rules. Segmentation policy needs explicit review rather than automatic trust between VLANs.

## Why this is useful in a portfolio

The repository demonstrates that Infrastructure as Code is more than copying configuration templates. It models the network, validates invariants, creates deterministic artifacts and keeps documentation synchronized with technical configuration.

## License

MIT
