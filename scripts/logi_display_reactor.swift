#!/usr/bin/env swift

// Watches for macOS screen wake events via NSWorkspace notifications.
// When the external display link renegotiates (e.g. after an Amphetamine
// session ends, or when the screen returns from sleep), SIGKILLs
// logioptionsplus_agent so the existing recovery layers (Logi's own
// KeepAlive + ai.hermes.logi-watchdog) bring up a fresh, healthy process.
//
// Pairs with scripts/logi_options_watchdog (PID-based polling) for full
// coverage of both "really dead" and "alive but broken" failure modes.
//
// History: an earlier version tried CGDisplayRegisterReconfigurationCallback
// for tighter timing, but the callbacks did not arrive in our launchd
// `swift -interpret` execution context (no WindowServer bootstrap, even
// with NSApplication.run()). NSWorkspace notifications travel through the
// distributed notification center and are known to work from background
// daemons — vertex_wake_watcher.swift uses the same mechanism.

import AppKit
import Foundation

let agentPattern = "logioptionsplus_agent --launchd"
let defaultDebounceSeconds: TimeInterval = 30.0

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

final class WakeReactor {
    static let shared = WakeReactor()
    private var lastReaction: Date?
    private var observers: [NSObjectProtocol] = []

    func start() {
        // Two complementary wake signals (verified empirically 2026-05-22):
        //   - dnc:com.apple.screenIsUnlocked fires immediately on unlock
        //   - NSWorkspace.didWakeNotification fires ~seconds later from
        //     the system power manager
        // Both belong to the same physical wake event; the 30s debounce
        // coalesces them so we SIGKILL Logi exactly once per wake cycle.
        let nc = NSWorkspace.shared.notificationCenter
        let didWakeObserver = nc.addObserver(
            forName: NSWorkspace.didWakeNotification,
            object: nil,
            queue: OperationQueue.main
        ) { [weak self] _ in
            self?.handle(eventName: "didWake")
        }
        observers.append(didWakeObserver)

        let dnc = DistributedNotificationCenter.default()
        let unlockObserver = dnc.addObserver(
            forName: Notification.Name("com.apple.screenIsUnlocked"),
            object: nil,
            queue: OperationQueue.main
        ) { [weak self] _ in
            self?.handle(eventName: "screenIsUnlocked")
        }
        observers.append(unlockObserver)
    }

    func handle(eventName: String) {
        let now = Date()
        if let last = lastReaction, now.timeIntervalSince(last) < debounceSeconds {
            return
        }
        lastReaction = now

        log("\(eventName) → SIGKILL Logi agent")
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

log("logi-display-reactor started (debounce=\(Int(debounceSeconds))s, mode=NSWorkspace)")
WakeReactor.shared.start()

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

// NSWorkspace notifications are delivered to the main RunLoop. Unlike
// CGDisplayReconfigurationCallback, they do NOT require an NSApplication
// bootstrap or WindowServer connection — they ride the distributed
// notification center, which works fine from a background launchd daemon.
RunLoop.main.run()
