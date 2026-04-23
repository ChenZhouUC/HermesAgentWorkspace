#!/usr/bin/env swift

import AppKit
import Foundation

func timestamp() -> String {
    let formatter = DateFormatter()
    formatter.dateFormat = "yyyy-MM-dd HH:mm:ss Z"
    formatter.locale = Locale(identifier: "en_US_POSIX")
    return formatter.string(from: Date())
}

func log(_ message: String) {
    print("[\(timestamp())] \(message)")
    fflush(stdout)
}

func usage() {
    print(
        """
        Usage: vertex_wake_watcher.swift [--help]

        Watches for macOS wake-from-sleep events and runs:
          ~/.hermes/scripts/refresh_vertex_and_restart_gateway

        Environment:
          HERMES_HOME                   Hermes home directory (default: inferred)
          VERTEX_WAKE_DEBOUNCE_SECONDS  Minimum seconds between wake-triggered refreshes (default: 90)
        """
    )
}

let env = ProcessInfo.processInfo.environment
if CommandLine.arguments.contains("--help") || CommandLine.arguments.contains("-h") {
    usage()
    exit(0)
}

let hermesHome: String = {
    if let explicit = env["HERMES_HOME"], !explicit.isEmpty {
        return explicit
    }
    let scriptURL = URL(fileURLWithPath: CommandLine.arguments[0]).resolvingSymlinksInPath()
    return scriptURL.deletingLastPathComponent().deletingLastPathComponent().path
}()

let refreshPath = "\(hermesHome)/scripts/refresh_vertex_and_restart_gateway"
let debounceSeconds = max(Double(env["VERTEX_WAKE_DEBOUNCE_SECONDS"] ?? "") ?? 90.0, 0.0)

final class WakeWatcher {
    private let debounceSeconds: TimeInterval
    private let refreshPath: String
    private var lastRefreshAt: Date?
    private var observer: NSObjectProtocol?

    init(refreshPath: String, debounceSeconds: TimeInterval) {
        self.refreshPath = refreshPath
        self.debounceSeconds = debounceSeconds
    }

    func start() {
        guard FileManager.default.isExecutableFile(atPath: refreshPath) else {
            log("Refresh script is missing or not executable: \(refreshPath)")
            exit(1)
        }

        observer = NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didWakeNotification,
            object: nil,
            queue: OperationQueue.main
        ) { [weak self] _ in
            self?.handleWake()
        }

        log("Vertex wake watcher armed")
        log("Hermes home: \(hermesHome)")
        log("Refresh script: \(refreshPath)")
        log("Wake debounce: \(Int(debounceSeconds))s")
        RunLoop.main.run()
    }

    private func handleWake() {
        let now = Date()
        if let lastRefreshAt, now.timeIntervalSince(lastRefreshAt) < debounceSeconds {
            let elapsed = Int(now.timeIntervalSince(lastRefreshAt))
            log("Wake notification ignored (\(elapsed)s since last refresh, debounce \(Int(debounceSeconds))s)")
            return
        }
        lastRefreshAt = now

        log("Wake notification received; refreshing Vertex token")
        let task = Process()
        task.executableURL = URL(fileURLWithPath: refreshPath)
        task.environment = env
        task.standardOutput = FileHandle.standardOutput
        task.standardError = FileHandle.standardError

        do {
            try task.run()
            task.waitUntilExit()
            if task.terminationStatus == 0 {
                log("Wake-triggered Vertex refresh completed successfully")
            } else {
                log("Wake-triggered Vertex refresh exited with status \(task.terminationStatus)")
            }
        } catch {
            log("Failed to launch wake-triggered Vertex refresh: \(error)")
        }
    }
}

WakeWatcher(refreshPath: refreshPath, debounceSeconds: debounceSeconds).start()
