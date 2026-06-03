---
name: file-naming-conventions
description: Conventions for naming files, project backups, and timestamped artifacts to ensure robust machine parsing and cross-platform sorting.
category: software-development
version: 2026.06.03
author: Chen Zhou <chenzhou@uchicago.edu>
---

# File Naming Conventions

When generating timestamped files, backups, or project archives, adhere to the following naming conventions to ensure they are both human-readable and reliably parsed by machines.

## 1. Project Prefixing

**Pattern:** `ProjectName_...`
Always place the project or context name _before_ the timestamp. This ensures that alphabetical sorting clusters related files together, rather than scattering a single project's history across different days.

**Creative / Presentation Bundles:** When naming a bundle or directory that contains a complete set of presentation materials, assets, and final artifacts, use the prefix **`Folio_`** (e.g., `Folio_ProjectName_YYYYMMDDTHHMMSS+0800`). It is the preferred, highly professional term for creative and design portfolios.

## 2. ISO 8601 Compact Timestamps

**Pattern:** `YYYYMMDDTHHMMSS+ZZZZ`
**Example:** `ProjectName_20260527T143045+0800`

Use the compact ISO 8601 variant with a precise timezone offset.

- **Use `T` as a separator** between date and time (standard ISO 8601).
- **Omit colons (`:`)** in the time portion to maintain cross-platform file system compatibility (Windows blocks `:`).
- **Include numeric timezone offsets** (e.g., `+0800`, `-0500`) instead of alphabetical abbreviations (like `CST`, `EST`). Abbreviations are highly ambiguous and often misparsed by default date libraries.

## 3. Machine Parsing Offsets

Modern language libraries natively support the numeric offset suffix, making this format zero-cost to parse:

- **Python / C / C++ (`strftime`)**: Use `%z` (e.g., `"%Y%m%dT%H%M%S%z"`)
- **Java / Kotlin / JVM**: Use `Z` or `XX` (e.g., `"yyyyMMdd'T'HHmmssZ"`)
- **Go (Golang)**: Use `-0700` (e.g., `"20060102T150405-0700"`)
- **C# / .NET**: Use `zzz` (note: custom formatting may be needed if expecting no colons in the offset)

## 4. URL/URI Safety Fallbacks

If the filename must be strictly URL-safe (where `+` is interpreted as a space) and URL encoding is not guaranteed:

- **Convert to UTC:** Save the time as absolute UTC and append `Z` (e.g., `ProjectName_20260527T063045Z`). Machines can parse the `Z` and convert it back to the user's local timezone for display.
