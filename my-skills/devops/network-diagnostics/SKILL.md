---
name: network-diagnostics
description: Advanced network and DNS probing, diagnostics, and metrics (CHAOS / ECS / NXDOMAIN / DoT-DoH / ASN).
category: devops
---

# Network Diagnostics & Advanced DNS Probing

When standard `ping` is insufficient (ICMP often deprioritized by firewalls and unrelated to DNS resolution performance), use this skill to extract deep routing and security metrics from a DNS resolver IP.

**Full architecture, latency budgets, and engineering best-practices for building a sub-second probing daemon are in [`references/advanced_dns_probing.md`](references/advanced_dns_probing.md).**
**For diagnosing transparent proxy slowdowns on OpenWRT/ARM routers (AES-NI, TPROXY, BBR, Full Cone NAT), see [`references/openwrt_proxy_bottlenecks.md`](references/openwrt_proxy_bottlenecks.md).** Read that file before designing a probing tool. The summary below is a quick-reference cheatsheet.

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
