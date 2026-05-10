# Advanced DNS Metrics Probing Architecture

When building network diagnostic tools or DNS testing daemons, standard ICMP Ping is insufficient. Use these advanced probes to extract deep infrastructure metrics from an Anycast DNS IP in <1s.

## 1. Physical Edge Node (POP) Identification

Identifies the exact physical datacenter handling the Anycast request via the `CHAOS` class.

- **Probe**: `dig +short CHAOS TXT id.server @<target_ip>` or `hostname.bind`
- **Impl**: UDP/53. Set query class to `3` (CHAOS), type `TXT`.
- **Latency**: < 50ms.

## 2. Egress IP & EDNS Client Subnet (ECS) Support

Reveals the upstream recursive pool IP and whether the DNS server passes client subnet data (crucial for CDN accuracy).

- **Probe**: `dig +short TXT o-o.myaddr.l.google.com @<target_ip>`
- **Impl**: UDP/53. Type `TXT`.
- **Latency**: 100~300ms (requires upstream resolution).

## 3. Protocol Encryption Scan (DoT / DoH)

Verifies modern transport support.

- **Probe**: Async TCP handshake to `853` (DoT) and `443` (DoH).
- **Impl**: Use raw TCP sockets (`net.DialTimeout` / `asyncio.open_connection`). Do not wait for full TLS negotiation—a successful TCP SYN/ACK proves the port is open.
- **Latency**: < 150ms.

## 4. Hijacking & Purity Verification

Tests if the DNS server intercepts unresolved domains (often done by ISP DNS to inject ads).

- **Probe**: `dig A <random_uuid_string>.com @<target_ip>`
- **Impl**: UDP/53. Type `A`.
- **Expected**: `Rcode` MUST be `3` (`NXDOMAIN`). If `0` (`NOERROR`) is returned with an IP, the DNS is poisoned.
- **Latency**: < 200ms.

## 5. ISP / Organization Identity

- **Probe**: Offline MaxMind MMDB (e.g., GeoLite2-ASN).
- **Impl**: Query the target IP against a local ASN database to instantly resolve the backing corporation (e.g., AS132203 -> Tencent).
- **Latency**: 0ms (In-memory).

## Engineering Best Practices for Daemons

1. **Aggressive Concurrency**: Fire all network probes simultaneously.
2. **Strict Timeouts**: Cap TCP/UDP operations at `800ms - 1200ms` max to prevent thread blocking on silent drop/blackholed IPs.
3. **Progressive Streaming**: Use SSE (Server-Sent Events) to yield `asn_geo` at 0ms, `ping` at 30ms, and `ecs` at 300ms so UI panels render incrementally without blocking.
