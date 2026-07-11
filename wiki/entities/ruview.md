---
title: RuView (WiFi Sensing Platform)
created: 2026-05-14
updated: 2026-07-11
type: entity
tags: [agent, ops, edge-computing]
sources: [_living/AI-Applications/RuView-Technical-Research-Deployment.md]
confidence: high
---

# RuView (WiFi Sensing Platform)

RuView is a WiFi sensing platform that leverages Channel State Information (CSI) for non-line-of-sight sensing.

## Core Capabilities

- Through-wall human detection and pose estimation.
- Non-contact vital sign monitoring (respiration, heart rate).
- Activity recognition and crowd counting.

## Technical Positioning

Derived from CMU's "DensePose From WiFi" (2022). It operates purely on edge devices without requiring cloud services or cameras, utilizing inexpensive ESP32-S3 chips as CSI collectors.^[[[_living/AI-Applications/RuView-Technical-Research-Deployment|RuView-Technical-Research-Deployment]]]
