---
name: network-diagnostics
description: Use when probing network, DNS resolver, or OpenWRT/ImmortalWRT proxy performance issues, including CHAOS, ECS, NXDOMAIN, DoT/DoH, and ASN diagnostics.
---

# Network Diagnostics & Advanced DNS Probing

When standard `ping` is insufficient (ICMP often deprioritized by firewalls and unrelated to DNS resolution performance), use this skill to extract deep routing and security metrics from a DNS resolver IP.

**Full architecture, latency budgets, and engineering best-practices for building a sub-second probing daemon are in [`references/advanced_dns_probing.md`](references/advanced_dns_probing.md).**
**For diagnosing transparent proxy slowdowns on OpenWRT/ARM routers (AES-NI, TPROXY, BBR, Full Cone NAT), see [`references/openwrt_proxy_bottlenecks.md`](references/openwrt_proxy_bottlenecks.md) and the "OpenWRT/ImmortalWRT Routing" section below.** Read that file before designing a probing tool. The summary below is a quick-reference cheatsheet.

## OpenWRT / ImmortalWRT Proxy Optimization

When diagnosing OpenWRT-based routers:

1. **CPU vs Hardware Offloading**: Transparent proxies (TPROXY/REDIRECT) bypass hardware Flow Offloading, forcing pure CPU processing. Check `htop` for 100% CPU usage.
2. **Encryption Algorithms**: For ARM/MIPS routers lacking the `AES-NI` instruction set, use `ChaCha20-Poly1305` instead of AES-GCM to drastically reduce CPU load.
3. **TCP BBR**: Enable TCP BBR congestion control (`Turbo ACC` in ImmortalWRT).
4. **DNS Fake-IP**: Use Fake-IP mode to eliminate DNS resolution latency during connection handshakes.
5. **Full Cone NAT**: Essential for P2P/gaming (NAT Type 1/2). Available in ImmortalWRT by default.

- **Diagnostic Commands**: `cat /proc/cpuinfo | grep -i aes`, `htop`.

## Probe Cheatsheet

| #   | Goal                    | CLI                                                         | Notes                                                                                             |
| --- | ----------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| 1   | Identify Anycast POP    | `dig +short CHAOS TXT id.server @<ip>` (or `hostname.bind`) | Set query class `CHAOS` (3), type `TXT`. Returns e.g. `"cn-hangzhou-d"`.                          |
| 2   | Egress IP + ECS support | `dig +short TXT o-o.myaddr.l.google.com @<ip>`              | Reveals upstream egress IP and `edns0-client-subnet` header (crucial for CDN accuracy).           |
| 3   | Hijack / purity test    | `dig A <random-uuid>.com @<ip>`                             | Healthy = `NXDOMAIN` (Rcode 3). `NOERROR` + A record ⇒ hijacked / ad-injecting.                   |
| 4   | DoT / DoH support       | TCP probe to port 853 (DoT) / 443 (DoH)                     | A successful TCP SYN/ACK proves the port is open — no need to complete TLS handshake (sub-150ms). |
| 5   | ASN / org identity      | Local MMDB (`GeoLite2-ASN`)                                 | Offline lookup, 0ms; never use online APIs in a low-latency probe.                                |

## Engineering Pitfalls (When Building Tools)

- **Aggressive timeouts**: cap each probe at 800–1500 ms. Silent blackhole IPs will hang indefinitely otherwise (especially DoT / DoH on filtered networks).
- **Concurrent probing**: fire all independent probes simultaneously in a coroutine / thread pool. Total wall time should equal the slowest successful metric, not the sum.
- **Streaming results**: emit metrics incrementally (e.g., SSE) — `asn_geo` at 0 ms, `chaos` at ~50 ms, `ecs` at ~300 ms — so the UI renders progressively instead of waiting for the slowest probe.
