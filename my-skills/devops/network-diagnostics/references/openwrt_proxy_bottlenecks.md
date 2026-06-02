# OpenWRT Proxy & Routing Bottleneck Diagnostics

When diagnosing slow speeds on transparent proxies running on OpenWRT/ImmortalWRT routers, the root cause is almost always hardware capability and network protocol mechanisms, rather than external bandwidth.

## 1. CPU / AES-NI Bottleneck (Encryption Overhead)

- **The Issue**: Transparent proxies (OpenClash, PassWall, ShadowSocksR Plus+) perform heavy TLS encryption/decryption (e.g., AES-128/256-GCM). While modern PC CPUs have hardware AES-NI instructions, most ARM/MIPS routers do not.
- **Symptom**: Speeds max out at a low threshold (e.g., 50-100 Mbps on a Gigabit connection) while one or more CPU cores hit 100% load (`htop`).
- **Diagnosis**: Run `cat /proc/cpuinfo | grep -i aes`. If missing, the router lacks AES acceleration.
- **Mitigation**: Switch node encryption from AES to `ChaCha20-Poly1305` (a software-optimized stream cipher designed for low-power ARM devices).

## 2. Hardware Offloading vs. TPROXY Conflict

- **The Issue**: Modern routers achieve gigabit routing using Flow Offloading (Hardware NAT/Software Fast Path), bypassing the main CPU.
- **Conflict**: Transparent proxies use `iptables/nftables` with `TPROXY` or `REDIRECT` rules to intercept traffic. This forcefully pulls packets out of the accelerated kernel fast-path into the userspace proxy application, entirely disabling flow offloading for outbound proxy traffic.
- **Mitigation**: Ensure strict split-routing (Bypass CN / GFWList). Only proxy traffic that absolutely must go through the tunnel, leaving domestic traffic to enjoy hardware offloading.

## 3. High-Multiplier "Game Nodes" Speed Parity

- **The Phenomenon**: Users often notice that expensive IPLC/IEPL "game nodes" measure the same speed on both PC and Router, while cheap nodes are much slower on the Router.
- **Explanation**: IPLC nodes are bandwidth-capped at the server side (e.g., 30 Mbps) due to high transit costs. At this low ceiling, even a weak MIPS/ARM router can decrypt the traffic without maxing out its CPU. The bottleneck shifts from the client CPU to the server bandwidth limit.

## 4. Advanced Tuning (ImmortalWRT specific)

If hardware is constrained, ensure these optimizations are enabled:

- **TCP BBR**: Enables aggressive congestion control, drastically improving throughput on high-latency/lossy international connections. (CLI: `net.ipv4.tcp_congestion_control=bbr` or via Turbo ACC GUI).
- **Fake-IP DNS**: Reduces TTFB (Time to First Byte) by immediately returning a dummy IP (e.g., `198.18.x.x`) to the client to begin connection rendering while asynchronously resolving the true IP.
- **Full Cone NAT**: Allows P2P and gaming consoles to achieve NAT 1/2. ImmortalWRT patches this directly into the kernel/firewall; standard OpenWRT mainlines reject it for security philosophy reasons and require manual kernel patching (`iptables-mod-fullconenat`).
