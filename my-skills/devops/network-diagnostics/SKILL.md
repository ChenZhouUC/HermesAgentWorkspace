---
name: network-diagnostics
description: "Advanced network and DNS probing, diagnostics, and metrics."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [dns, networking, metrics, debugging, probes]
---

# Network Diagnostics & Advanced DNS Probing

See `references/advanced_dns_probing.md` for a full architecture guide on executing high-concurrency DNS metrics (CHAOS, ECS, DoT/DoH) under 1 second.

## Advanced DNS Metrics (Zero-to-Hero)

When tasked with diagnosing or profiling a DNS resolver (e.g., 8.8.8.8, 223.5.5.5, 119.29.29.29), standard `ping` is insufficient. ICMP latency is often deprioritized by firewalls and does not reflect actual DNS resolution performance.

Use these advanced probes to extract deep routing and security metrics from a single IP address:

### 1. Identify Physical Anycast Node (CHAOS Query)

Find out which specific physical datacenter the Anycast IP is routing you to.

- **CLI Equivalent:** `dig +short CHAOS TXT id.server @<target_ip>` or `hostname.bind`
- **Expected:** A string like `"cn-hangzhou-d"`.
- **Implementation:** In code (e.g., Python `dnspython`), set DNS query class to `CHAOS` (Class 3), type `TXT`.

### 2. Detect Egress IP & ECS (EDNS Client Subnet) Support

Determine the DNS server's actual outbound IP and whether it passes your client subnet to authoritative servers (crucial for CDN accuracy).

- **CLI Equivalent:** `dig +short TXT o-o.myaddr.l.google.com @<target_ip>`
- **Expected:** Returns the egress IP and optionally subnet info like `"edns0-client-subnet 1.2.3.0/24"`.

### 3. DNS Hijacking / Purity Test

Check if the DNS resolver intercepts non-existent domains (often done by ISPs or dirty resolvers to inject ads).

- **CLI Equivalent:** `dig A <random_uuid_string>.com @<target_ip>`
- **Expected:** A healthy DNS returns `NXDOMAIN` (Rcode 3). If it returns `NOERROR` and an A record IP, the resolver is hijacked or dirty.

### 4. Protocol Support (DoT / DoH Port Scan)

Test if the resolver supports modern encryption standards.

- **DoT (DNS over TLS):** TCP port 853.
- **DoH (DNS over HTTPS):** TCP port 443.
- **Fast Probe:** To check support quickly (<150ms) without doing a full heavy TLS handshake, simply assert a successful TCP socket connection to the port (e.g., `nc -vz <ip> 853`). TCP SYN/ACK is enough to prove the port is open and listening.

### 5. ASN & Organization Identity

Do not use online APIs for simple ASN/Geo mapping if low latency is required. Use a local MMDB (like `GeoLite2-ASN` or `ip-location-db`) to instantly resolve the IP to its ASN and organization name (e.g., AS45102 - Alibaba Cloud) with zero network latency.

## DNS Application Engineering Pitfalls

When building apps that test or display these metrics:

- **Aggressive Timeouts:** Network probes can hang indefinitely (especially DoT/DoH on blocked networks). Enforce strict application-level timeouts (e.g., 800ms-1500ms).
- **Concurrent Probing:** Run all independent probes (CHAOS, ECS, NXDOMAIN, Port Scan) simultaneously in a coroutine pool/thread pool. Total execution time should be bounded by the slowest successful metric, not the sum of them.
- **Streaming Returns:** Yield results to the UI incrementally (e.g., via Server-Sent Events / SSE) rather than waiting for the entire batch of probes to finish.
