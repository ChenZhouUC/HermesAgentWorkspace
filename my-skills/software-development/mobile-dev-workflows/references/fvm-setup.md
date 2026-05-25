# Flutter Version Management (FVM) Setup

FVM allows caching multiple Flutter SDK versions and configuring them per-project to avoid conflicts. Dart SDK is bundled automatically with Flutter.

## Installation (macOS)

```bash
brew tap leoafarias/fvm
brew install fvm
```

## Usage

- Install stable: `fvm install stable`
- Set global default: `fvm global stable`
- Project specific (in project root): `fvm use <version>` (generates `.fvm/` directory, which should be `.gitignore`d)

## Environment PATH

To ensure standard commands resolve to FVM's default:

```bash
# Add to ~/.zshrc
export PATH="$HOME/fvm/default/bin:$PATH"
```

## IDE Configuration

In VS Code / Android Studio, point the Flutter SDK path to `<project_root>/.fvm/flutter_sdk` to ensure isolated code completion and analyzer behavior for that specific project.
