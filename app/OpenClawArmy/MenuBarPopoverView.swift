import SwiftUI

struct MenuBarPopoverView: View {
    @EnvironmentObject var orchestrator: OrchestratorService

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Image(systemName: "crown.fill")
                    .font(.system(size: 18))
                    .foregroundStyle(
                        LinearGradient(colors: [Color(red: 0.75, green: 0.75, blue: 0.8), .white],
                                       startPoint: .top, endPoint: .bottom)
                    )
                Text("King AI")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(.white)
                Spacer()
                StatusDot(isConnected: orchestrator.isConnected)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Color(red: 0.04, green: 0.04, blue: 0.08))

            Divider().background(Color.gray.opacity(0.2))

            ScrollView {
                VStack(spacing: 12) {
                    if let health = orchestrator.health {
                        PopoverStatRow(title: "Status", value: health.status.capitalized,
                                       color: health.status == "healthy" ? .green : .red)
                        PopoverStatRow(title: "Workflows", value: "\(health.activeWorkflows)", color: .blue)
                        PopoverStatRow(title: "Sessions", value: "\(health.activeChatSessions)", color: .cyan)
                    }

                    if let stats = orchestrator.activityStats {
                        Divider().background(Color.gray.opacity(0.15))
                        PopoverStatRow(title: "Events", value: "\(stats.totalInMemory)", color: .white)
                        PopoverStatRow(title: "Sessions", value: "\(stats.uniqueSessions)", color: .cyan)
                    }

                    Divider().background(Color.gray.opacity(0.15))

                    // Agents
                    VStack(alignment: .leading, spacing: 6) {
                        Text("NEURAL NETWORK")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(.gray)
                            .tracking(1.5)

                        if orchestrator.agents.isEmpty {
                            Text("Connecting...")
                                .font(.system(size: 12))
                                .foregroundColor(.gray)
                        } else {
                            ForEach(orchestrator.agents) { agent in
                                PopoverAgentRow(agent: agent, status: orchestrator.agentStatuses[agent.name])
                            }
                        }
                    }
                }
                .padding(14)
            }

            Divider().background(Color.gray.opacity(0.2))

            // Footer
            HStack(spacing: 12) {
                Button(action: { openMainWindow() }) {
                    Label("Dashboard", systemImage: "rectangle.grid.2x2")
                        .font(.system(size: 11))
                }
                .buttonStyle(.plain)
                .foregroundColor(.cyan)

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
            .background(Color(red: 0.04, green: 0.04, blue: 0.08))
        }
        .background(Color(red: 0.03, green: 0.03, blue: 0.07))
    }

    func openMainWindow() {
        if let window = NSApp.windows.first(where: { $0.title.contains("King") || $0.contentView != nil }) {
            window.makeKeyAndOrderFront(nil)
        }
        NSApp.activate(ignoringOtherApps: true)
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

struct PopoverStatRow: View {
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

struct PopoverAgentRow: View {
    let agent: AgentInfo
    let status: String?

    var statusColor: Color {
        switch status {
        case "alive": return .green
        case "unreachable": return .red
        default: return .yellow
        }
    }

    var roleIcon: String {
        if agent.role == "king" { return "crown.fill" }
        if agent.role == "manager" { return "person.3.fill" }
        if agent.name.contains("coding") { return "chevron.left.forwardslash.chevron.right" }
        if agent.name.contains("agentic") { return "magnifyingglass" }
        return "person.fill"
    }

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: roleIcon)
                .font(.system(size: 10))
                .foregroundColor(.cyan.opacity(0.6))
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
