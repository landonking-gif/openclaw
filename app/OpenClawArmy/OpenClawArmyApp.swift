import SwiftUI

@main
struct KingAIApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var orchestrator = OrchestratorService()

    var body: some Scene {
        WindowGroup {
            DashboardView()
                .environmentObject(orchestrator)
                .frame(minWidth: 1000, minHeight: 700)
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified(showsTitle: false))
        .defaultSize(width: 1200, height: 800)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }

        Settings {
            SettingsView()
                .environmentObject(orchestrator)
        }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var popover: NSPopover!
    var orchestrator = OrchestratorService.shared

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupMenuBar()
        orchestrator.startPolling()
    }

    func setupMenuBar() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)

        if let button = statusItem.button {
            let image = NSImage(systemSymbolName: "crown.fill", accessibilityDescription: "King AI")
            image?.isTemplate = true
            button.image = image
            button.action = #selector(togglePopover)
            button.target = self
        }

        popover = NSPopover()
        popover.contentSize = NSSize(width: 360, height: 440)
        popover.behavior = .transient
        popover.contentViewController = NSHostingController(
            rootView: MenuBarPopoverView().environmentObject(orchestrator)
        )
    }

    @objc func togglePopover() {
        guard let button = statusItem.button else { return }
        if popover.isShown {
            popover.performClose(nil)
        } else {
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
            NSApp.activate(ignoringOtherApps: true)
        }
    }
}

struct SettingsView: View {
    @EnvironmentObject var orchestrator: OrchestratorService
    @State private var urlInput = ""

    var body: some View {
        Form {
            Section("Connection") {
                TextField("API Base URL", text: $urlInput)
                    .onAppear { urlInput = orchestrator.baseURL }
                Button("Save") {
                    orchestrator.baseURL = urlInput
                    orchestrator.fetchAll()
                }
            }
        }
        .padding(20)
        .frame(width: 400, height: 150)
    }
}
