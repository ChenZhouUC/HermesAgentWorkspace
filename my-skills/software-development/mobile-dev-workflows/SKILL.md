---
name: mobile-dev-workflows
description: Mobile development workflows, SDK management via FVM, and project setup.
category: software-development
---

# Mobile Development Workflows

## SDK Management (FVM)

Always use FVM (Flutter Version Management) for managing Flutter SDKs to avoid version conflicts across projects.

- Note: FVM installs the Dart SDK automatically alongside Flutter.
- **Install**: `brew tap leoafarias/fvm && brew install fvm`
- **Global Setup**: `fvm install stable && fvm global stable`
- **Project Specific**: Run `fvm use <version>` in the project root. This creates a `.fvm/` directory.

## Execution and Workflows

- When working inside an FVM-managed project, always prefix flutter commands: `fvm flutter run`, `fvm flutter pub get`.
- Ensure `.fvm/` is added to the project's `.gitignore`.
- For IDEs (VS Code / Android Studio), point the Flutter SDK path to the project-local `.fvm/flutter_sdk` to ensure code completion matches the isolated version.
