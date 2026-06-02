---
name: openwrt
description: "Configure and optimize OpenWRT and ImmortalWRT routers for proxy performance and network tuning."
category: devops
---

# OpenWRT / ImmortalWRT Management

Use this skill for diagnosing network bottlenecks, configuring routing, and optimizing transparent proxies on OpenWRT-based systems.

## Key Optimizations for Proxy Throughput

1. **CPU vs Hardware Offloading**: Transparent proxies (TPROXY/REDIRECT) bypass hardware Flow Offloading, forcing pure CPU processing. If a user complains about slow proxy speeds, check `htop` for 100% CPU usage.
2. **Encryption Algorithms**: For ARM/MIPS routers lacking the `AES-NI` instruction set, use `ChaCha20-Poly1305` instead of AES-GCM to drastically reduce CPU load. (Note: Do not do this on x86 machines with AES-NI, where it will be slower).
3. **TCP BBR**: Enable TCP BBR congestion control (`Turbo ACC` in ImmortalWRT) to improve throughput on lossy international links.
4. **DNS Fake-IP**: Use Fake-IP mode (e.g., in OpenClash or PassWall) to eliminate DNS resolution latency during connection handshakes, drastically reducing Time-to-First-Byte (TTFB).
5. **Full Cone NAT**: Essential for P2P and gaming to achieve NAT Type 1/2. This is available in ImmortalWRT by default but requires manual kernel patching and compilation on vanilla OpenWRT.

## Diagnostic Commands

- **Check CPU AES support**: `cat /proc/cpuinfo | grep -i aes`
- **Monitor bottleneck under load**: `opkg update && opkg install htop` then run `htop`.
