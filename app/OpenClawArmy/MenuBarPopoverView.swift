import SwiftUI

struct MenuBarPopoverView: View {
    @EnvironmentObject var orchestrator: OrchestratorService

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Image(systemName: "ant.circle.fill")
                    .font(.system(size: 18))
                    .foregroundColor(.purple)
                Text("OpenClaw Army")
                    .font(.system(size: 14, weight: .semibold))
                Spacer()
                StatusDot(isConnected: orchestrator.isConnected)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Color.black.opacity(0.3))

            Divider().background(Color.gray.opacity(0.3))

            ScrollView {
                VStack(spacing: 12) {
                    // Quick Stats
                    if let health = orchestrator.health {
                        QuickStatsRow(title: "Status", value: health.status.capitalized, color: health.status == "healthy" ? .green : .red)
                        QuickStatsRow(title: "Active Workflows", value: "\(health.activeWorkflows)", color: .blue)
                        QuickStatsRow(title: "Chat Sessions", value: "\(health.activeChatSessions)", color: .purple)
                    }

                    if let quality = orchestrator.quality {
                        Divider().background(Color.gray.opacity(0.2))
                        QuickStatsRow(title: "Tools", value: "\(quality.toolCount)", color: .cyan)
                        QuickStatsRow(title: "Lines of Code", value: "\(quality.lineCount)", color: .orange)
                        QuickStatsRow(title: "Compile", value: quality.compileOk ? "OK" : "FAIL", color: quality.compileOk ? .green : .red)
                    }

                    if let stats = orchestrator.activityStats {
                        Divider().background(Color.gray.opacity(0.2))
                        QuickStatsRow(title: "Total Activities", value: "\(stats.total)", color: .white)
                        if stats.recentErrors > 0 {
                            QuickStatsRow(title: "Recent Errors", value: "\(stats.recentErrors)", color: .red)
                        }
                    }

                    Divider().background(Color.gray.opacity(0.2))

                    // Agent Status
                    VStack(alignment: .leading, spacing: 6) {
                        Text("AGENTS")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(.gray)
                            .tracking(1.5)

                        if orchestrator.agents.isEmpty {
                            Text("Loading...")
                                .font(.system(size: 12))
                                .foregroundColor(.gray)
                        } else {
                            ForEach(orchestrator.agents) { agent in
                                AgentRow(agent: agent, status: orchestrator.agentStatuses[agent.name])
                            }
                        }
                    }
                }
                .padding(14)
            }

            Divider().background(Color.gray.opacity(0.3))

            // Footer actions
            HStack(spacing: 12) {
                Button(action: { openDashboard() }) {
                    Label("Dashboard", systemImage: "rectangle.grid.2x2")
                        .font(.system(size: 11))
                }
                .buttonStyle(.plain)
                .foregroundColor(.purple)

                Spacer()

                Button(action: { orchestrator.fetchAll() }) {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 11))
                }
                .buttonStyle(.plain)
                .foregroundColor(.gray)

                Button(action: { NSApp.terminate(nil) }) {
                    Image(systemName: "power")
                        .font(.system(size: 11))
                }
                .buttonStyle(.plain)
                .foregroundColor(.red.opacity(0.7))
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(Color.black.opacity(0.3))
        }
        .background(Color(nsColor: NSColor(red: 0.04, green: 0.04, blue: 0.08, alpha: 1.0)))
    }

    func openDashboard() {
        // Focus or open the main window
        if let window = NSApp.windows.first(where: { $0.title.contains("OpenClaw") || $0.contentView is NSHostingView<DashboardView> }) {
            window.makeKeyAndOrderFront(nil)
        } else {
            // Open new window
            NSApp.activate(ignoringOtherApps: true)
        }
    }
}

struct StatusDot: View {
    let isConnected: Bool
    @State private var pulse = false

    var body: some View {
        Circle()
            .fill(isConnected ? Color.green : Color.red)
            .frame(width: 8, height: 8)
            .scaleEffect(pulse ? 1.3 : 1.0)
            .animation(.easeInOut(duration: 1).repeatForever(autoreverses: true), value: pulse)
            .onAppear { pulse = true }
    }
}

struct QuickStatsRow: View {
    let title: String
    let value: String
    let color: Color

    var body: some View {
        HStack {
            Text(title)
                .font(.system(size: 12))
                .foregroundColor(.gray)
            Spacer()
            Text(value)
                .font(.system(size: 12, weight: .semibold, design: .monospaced))
                .foregroundColor(color)
        }
    }
}

struct AgentRow: View {
    let agent: AgentInfo
    let status: String?

    var statusColor: Color {
        switch status {
        case "online": return .green
        case "offline": return .red
        default: return .gray
        }
    }

    var roleIcon: String {
        if agent.name.contains("king") { return "crown.fill" }
        if agent.name.contains("manager") || agent.name.contains("alpha") || agent.name.contains("beta") || agent.name.contains("gamma") { return "person.3.fill" }
        if agent.name.contains("coding") { return "chevron.left.forwardslash.chevron.right" }
        if agent.name.contains("agentic") { return "magnifyingglass" }
        return "person.fill"
    }

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: roleIcon)
                .font(.system(size: 10))
                .foregroundColor(.purple.opacity(0.6))
                .frame(width: 14)
            Text(agent.name)
                .font(.system(size: 11, design: .monospaced))
                .foregroundColor(.white.opacity(0.8))
            Spacer()
            Text(":\(agent.port)")
                .font(.system(size: 10, design: .monospaced))
                .foregroundColor(.gray.opacity(0.5))
            Circle()
                .fill(statusColor)
                .frame(width: 6, height: 6)
        }
    }
}
