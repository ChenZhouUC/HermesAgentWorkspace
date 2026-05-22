#!/usr/bin/env swift

// Subscribes to macOS display reconfiguration events
// (CGDisplayRegisterReconfigurationCallback). When the external display link
// renegotiates -- the same event that causes the Logi Options+ daemon to
// silently enter a broken state -- this script SIGKILLs logioptionsplus_agent
// so the existing recovery layers (Logi's own KeepAlive + ai.hermes.logi-watchdog)
// bring up a fresh, healthy process.
//
// Pairs with scripts/logi_options_watchdog (PID-based polling) for full
// coverage of both "really dead" and "alive but broken" failure modes.

import AppKit
import CoreGraphics
import Foundation

let agentPattern = "logioptionsplus_agent --launchd"
let defaultDebounceSeconds: TimeInterval = 3.0

let env = ProcessInfo.processInfo.environment

let hermesHome: String = {
    if let explicit = env["HERMES_HOME"], !explicit.isEmpty {
        return explicit
    }
    let scriptURL = URL(fileURLWithPath: CommandLine.arguments[0]).resolvingSymlinksInPath()
    return scriptURL.deletingLastPathComponent().deletingLastPathComponent().path
}()

let debounceSeconds: TimeInterval = {
    if let raw = env["LOGI_DISPLAY_DEBOUNCE_SECONDS"], let parsed = Double(raw) {
        return max(parsed, 0.5)
    }
    return defaultDebounceSeconds
}()

let logPath = "\(hermesHome)/logs/logi-watchdog.log"

func timestamp() -> String {
    let f = DateFormatter()
    f.dateFormat = "yyyy-MM-dd'T'HH:mm:ssZ"
    f.locale = Locale(identifier: "en_US_POSIX")
    return f.string(from: Date())
}

func log(_ message: String) {
    let line = "[\(timestamp())] \(message)\n"
    if let data = line.data(using: .utf8) {
        let url = URL(fileURLWithPath: logPath)
        if FileManager.default.fileExists(atPath: logPath) {
            if let handle = try? FileHandle(forWritingTo: url) {
                defer { try? handle.close() }
                _ = try? handle.seekToEnd()
                try? handle.write(contentsOf: data)
            }
        } else {
            try? FileManager.default.createDirectory(
                at: url.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            try? data.write(to: url)
        }
    }
    print("[\(timestamp())] \(message)")
    fflush(stdout)
}

final class DisplayReactor {
    static let shared = DisplayReactor()
    private var lastReaction: Date?

    func handle(flags: CGDisplayChangeSummaryFlags) {
        // The callback fires twice per reconfiguration cycle: once with
        // beginConfigurationFlag set (before changes), and once after with
        // the actual change flags. We only react to the "after" event.
        if flags.contains(.beginConfigurationFlag) {
            return
        }

        let relevant: CGDisplayChangeSummaryFlags = [
            .setModeFlag,
            .addFlag,
            .removeFlag,
            .enabledFlag,
            .disabledFlag,
            .setMainFlag,
            .desktopShapeChangedFlag,
        ]
        if flags.intersection(relevant).isEmpty {
            return
        }

        let now = Date()
        if let last = lastReaction, now.timeIntervalSince(last) < debounceSeconds {
            return
        }
        lastReaction = now

        let hex = String(flags.rawValue, radix: 16)
        log("display reconfig (flags=0x\(hex)) → SIGKILL Logi agent")
        forceKillAgent()
    }

    private func forceKillAgent() {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
        task.arguments = ["-9", "-f", agentPattern]
        task.standardOutput = Pipe()
        task.standardError = Pipe()
        do {
            try task.run()
            task.waitUntilExit()
            // Recovery is handled by Logi's own KeepAlive and the bash
            // watchdog (ai.hermes.logi-watchdog); we deliberately don't
            // attempt the restart ourselves to keep responsibilities clean.
        } catch {
            log("pkill failed: \(error)")
        }
    }
}

let callback: CGDisplayReconfigurationCallBack = { _, flags, _ in
    DisplayReactor.shared.handle(flags: flags)
}

log("logi-display-reactor started (debounce=\(Int(debounceSeconds))s)")

let regError = CGDisplayRegisterReconfigurationCallback(callback, nil)
if regError != .success {
    log("CGDisplayRegisterReconfigurationCallback failed: \(regError.rawValue)")
    exit(1)
}

let sigtermSource = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
sigtermSource.setEventHandler {
    log("logi-display-reactor terminated (SIGTERM)")
    exit(0)
}
sigtermSource.resume()
signal(SIGTERM, SIG_IGN)

let sigintSource = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
sigintSource.setEventHandler {
    log("logi-display-reactor terminated (SIGINT)")
    exit(0)
}
sigintSource.resume()
signal(SIGINT, SIG_IGN)

RunLoop.main.run()
