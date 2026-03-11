import SwiftUI
import WebKit

struct DashboardView: View {
    @EnvironmentObject var orchestrator: OrchestratorService
    @State private var selectedTab = 0
    @State private var chatInput = ""
    @State private var chatMessages: [(role: String, text: String)] = []
    @State private var isSending = false

    var body: some View {
        ZStack {
            // Background
            Color(nsColor: NSColor(red: 0.02, green: 0.02, blue: 0.05, alpha: 1.0))
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // Top status bar
                TopStatusBar()
                    .environmentObject(orchestrator)

                // Tab bar
                HStack(spacing: 0) {
                    TabButton(title: "Overview", icon: "rectangle.grid.2x2", index: 0, selected: $selectedTab)
                    TabButton(title: "Chat", icon: "bubble.left.and.bubble.right", index: 1, selected: $selectedTab)
                    TabButton(title: "Agents", icon: "person.3", index: 2, selected: $selectedTab)
                    TabButton(title: "Activity", icon: "list.bullet.rectangle", index: 3, selected: $selectedTab)
                    TabButton(title: "Web Dashboard", icon: "globe", index: 4, selected: $selectedTab)
                    Spacer()
                }
                .padding(.horizontal, 16)
                .padding(.top, 8)
                .background(Color.black.opacity(0.3))

                Divider().background(Color.purple.opacity(0.3))

                // Content
                Group {
                    switch selectedTab {
                    case 0: OverviewTab()
                    case 1: ChatTab(chatInput: $chatInput, chatMessages: $chatMessages, isSending: $isSending)
                    case 2: AgentsTab()
                    case 3: ActivityTab()
                    case 4: WebDashboardTab()
                    default: OverviewTab()
                    }
                }
                .environmentObject(orchestrator)
            }
        }
        .preferredColorScheme(.dark)
    }
}

// MARK: - Top Status Bar

struct TopStatusBar: View {
    @EnvironmentObject var orchestrator: OrchestratorService

    var body: some View {
        HStack(spacing: 16) {
            HStack(spacing: 8) {
                Image(systemName: "ant.circle.fill")
                    .font(.system(size: 20))
                    .foregroundColor(.purple)
                Text("OpenClaw Army")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(.white)
            }

            Spacer()

            if let health = orchestrator.health {
                StatusPill(label: "Server", value: health.status.capitalized, color: health.status == "healthy" ? .green : .red)
            } else {
                StatusPill(label: "Server", value: orchestrator.isConnected ? "Connected" : "Offline", color: orchestrator.isConnected ? .green : .red)
            }

            if let quality = orchestrator.quality {
                StatusPill(label: "Tools", value: "\(quality.toolCount)", color: .cyan)
                StatusPill(label: "Code", value: "\(quality.lineCount)L", color: .orange)
            }

            if let stats = orchestrator.activityStats {
                StatusPill(label: "Events", value: "\(stats.total)", color: .purple)
                if stats.recentErrors > 0 {
                    StatusPill(label: "Errors", value: "\(stats.recentErrors)", color: .red)
                }
            }

            Button(action: { orchestrator.fetchAll() }) {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 12))
                    .foregroundColor(.gray)
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 10)
        .background(
            LinearGradient(
                colors: [Color(red: 0.05, green: 0.03, blue: 0.12), Color(red: 0.02, green: 0.02, blue: 0.06)],
                startPoint: .leading, endPoint: .trailing
            )
        )
    }
}

struct StatusPill: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        HStack(spacing: 4) {
            Text(label)
                .font(.system(size: 10))
                .foregroundColor(.gray)
            Text(value)
                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                .foregroundColor(color)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(color.opacity(0.1))
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(color.opacity(0.2), lineWidth: 1))
    }
}

struct TabButton: View {
    let title: String
    let icon: String
    let index: Int
    @Binding var selected: Int

    var isSelected: Bool { selected == index }

    var body: some View {
        Button(action: { selected = index }) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: 11))
                Text(title)
                    .font(.system(size: 12, weight: isSelected ? .semibold : .regular))
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .foregroundColor(isSelected ? .white : .gray)
            .background(isSelected ? Color.purple.opacity(0.2) : Color.clear)
            .cornerRadius(8)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Overview Tab

struct OverviewTab: View {
    @EnvironmentObject var orchestrator: OrchestratorService

    var body: some View {
        ScrollView {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 280), spacing: 16)], spacing: 16) {
                // System Health Card
                DashboardCard(title: "System Health", icon: "heart.fill", accentColor: .green) {
                    if let health = orchestrator.health {
                        StatRow(label: "Status", value: health.status.capitalized, color: .green)
                        StatRow(label: "Active Workflows", value: "\(health.activeWorkflows)", color: .blue)
                        StatRow(label: "Chat Sessions", value: "\(health.activeChatSessions)", color: .purple)
                    } else {
                        Text(orchestrator.isConnected ? "Loading..." : "Not connected")
                            .foregroundColor(.gray)
                            .font(.system(size: 13))
                    }
                }

                // Code Quality Card
                DashboardCard(title: "Code Quality", icon: "checkmark.shield.fill", accentColor: .cyan) {
                    if let q = orchestrator.quality {
                        StatRow(label: "Compile", value: q.compileOk ? "OK" : "FAIL", color: q.compileOk ? .green : .red)
                        StatRow(label: "Internal Tools", value: "\(q.toolCount)", color: .cyan)
                        StatRow(label: "Lines of Code", value: "\(q.lineCount)", color: .orange)
                    } else {
                        Text("Loading...")
                            .foregroundColor(.gray)
                            .font(.system(size: 13))
                    }
                }

                // Activity Card
                DashboardCard(title: "Activity", icon: "bolt.fill", accentColor: .purple) {
                    if let stats = orchestrator.activityStats {
                        StatRow(label: "Total Events", value: "\(stats.total)", color: .white)
                        StatRow(label: "Recent Errors", value: "\(stats.recentErrors)", color: stats.recentErrors > 0 ? .red : .green)
                        ForEach(Array(stats.byCategory.sorted(by: { $0.value > $1.value }).prefix(4)), id: \.key) { cat, count in
                            StatRow(label: cat, value: "\(count)", color: .gray)
                        }
                    } else {
                        Text("Loading...")
                            .foregroundColor(.gray)
                            .font(.system(size: 13))
                    }
                }

                // Agent Overview Card
                DashboardCard(title: "Agents (\(orchestrator.agents.count))", icon: "person.3.fill", accentColor: .indigo) {
                    let managers = orchestrator.agents.filter { $0.name.contains("manager") || $0.name.contains("king") }
                    let workers = orchestrator.agents.filter { !$0.name.contains("manager") && !$0.name.contains("king") }

                    StatRow(label: "Managers", value: "\(managers.count)", color: .purple)
                    StatRow(label: "Workers", value: "\(workers.count)", color: .blue)

                    if !managers.isEmpty {
                        ForEach(managers) { agent in
                            HStack(spacing: 6) {
                                Circle()
                                    .fill(Color.green.opacity(0.5))
                                    .frame(width: 6, height: 6)
                                Text(agent.name)
                                    .font(.system(size: 11, design: .monospaced))
                                    .foregroundColor(.white.opacity(0.7))
                                Spacer()
                                Text(":\(agent.port)")
                                    .font(.system(size: 10, design: .monospaced))
                                    .foregroundColor(.gray.opacity(0.4))
                            }
                        }
                    }
                }

                // Connection Card
                DashboardCard(title: "Connection", icon: "network", accentColor: .blue) {
                    StatRow(label: "API Base", value: orchestrator.baseURL, color: .white)
                    StatRow(label: "Connected", value: orchestrator.isConnected ? "Yes" : "No", color: orchestrator.isConnected ? .green : .red)
                    if let error = orchestrator.lastError {
                        Text(error)
                            .font(.system(size: 10))
                            .foregroundColor(.red.opacity(0.7))
                            .lineLimit(2)
                    }
                }

                // Recent Activity Card
                DashboardCard(title: "Recent Activity", icon: "clock.fill", accentColor: .orange) {
                    if orchestrator.recentActivity.isEmpty {
                        Text("No recent activity")
                            .foregroundColor(.gray)
                            .font(.system(size: 13))
                    } else {
                        ForEach(orchestrator.recentActivity.prefix(5)) { entry in
                            HStack(spacing: 8) {
                                Circle()
                                    .fill(entry.error != nil ? Color.red : Color.green)
                                    .frame(width: 5, height: 5)
                                Text(entry.summary)
                                    .font(.system(size: 11))
                                    .foregroundColor(.white.opacity(0.7))
                                    .lineLimit(1)
                                Spacer()
                                Text(entry.category)
                                    .font(.system(size: 9))
                                    .foregroundColor(.gray)
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(Color.gray.opacity(0.1))
                                    .cornerRadius(4)
                            }
                        }
                    }
                }
            }
            .padding(20)
        }
    }
}

struct DashboardCard<Content: View>: View {
    let title: String
    let icon: String
    let accentColor: Color
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 12))
                    .foregroundColor(accentColor)
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(.white)
                Spacer()
            }

            Divider().background(accentColor.opacity(0.2))

            content()
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(red: 0.06, green: 0.06, blue: 0.12))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(accentColor.opacity(0.15), lineWidth: 1)
        )
    }
}

struct StatRow: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        HStack {
            Text(label)
                .font(.system(size: 12))
                .foregroundColor(.gray)
            Spacer()
            Text(value)
                .font(.system(size: 12, weight: .medium, design: .monospaced))
                .foregroundColor(color)
        }
    }
}

// MARK: - Chat Tab

struct ChatTab: View {
    @EnvironmentObject var orchestrator: OrchestratorService
    @Binding var chatInput: String
    @Binding var chatMessages: [(role: String, text: String)]
    @Binding var isSending: Bool

    var body: some View {
        VStack(spacing: 0) {
            // Messages
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 10) {
                        ForEach(Array(chatMessages.enumerated()), id: \.offset) { idx, msg in
                            ChatBubble(role: msg.role, text: msg.text)
                                .id(idx)
                        }

                        if isSending {
                            HStack {
                                ProgressView()
                                    .scaleEffect(0.7)
                                Text("Thinking...")
                                    .font(.system(size: 12))
                                    .foregroundColor(.gray)
                                Spacer()
                            }
                            .padding(.horizontal, 20)
                        }
                    }
                    .padding(20)
                }
                .onChange(of: chatMessages.count) {
                    withAnimation {
                        proxy.scrollTo(chatMessages.count - 1, anchor: .bottom)
                    }
                }
            }

            Divider().background(Color.purple.opacity(0.3))

            // Input
            HStack(spacing: 10) {
                TextField("Ask the King AI anything...", text: $chatInput)
                    .textFieldStyle(.plain)
                    .font(.system(size: 14, design: .monospaced))
                    .foregroundColor(.white)
                    .padding(10)
                    .background(Color(red: 0.04, green: 0.04, blue: 0.1))
                    .cornerRadius(8)
                    .onSubmit { sendMessage() }

                Button(action: sendMessage) {
                    Image(systemName: "paperplane.fill")
                        .font(.system(size: 14))
                        .foregroundColor(chatInput.isEmpty ? .gray : .purple)
                }
                .buttonStyle(.plain)
                .disabled(chatInput.isEmpty || isSending)
            }
            .padding(14)
            .background(Color.black.opacity(0.4))
        }
    }

    func sendMessage() {
        let text = chatInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        chatInput = ""
        chatMessages.append((role: "user", text: text))
        isSending = true

        orchestrator.sendChat(message: text) { result in
            DispatchQueue.main.async {
                isSending = false
                switch result {
                case .success(let response):
                    chatMessages.append((role: "assistant", text: response.response))
                case .failure(let error):
                    chatMessages.append((role: "error", text: "Error: \(error.localizedDescription)"))
                }
            }
        }
    }
}

struct ChatBubble: View {
    let role: String
    let text: String

    var isUser: Bool { role == "user" }
    var isError: Bool { role == "error" }

    var body: some View {
        HStack {
            if isUser { Spacer(minLength: 60) }

            VStack(alignment: isUser ? .trailing : .leading, spacing: 4) {
                Text(role.uppercased())
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(isUser ? .purple.opacity(0.6) : isError ? .red.opacity(0.6) : .blue.opacity(0.6))
                    .tracking(1)

                Text(text)
                    .font(.system(size: 13))
                    .foregroundColor(isError ? .red.opacity(0.8) : .white.opacity(0.9))
                    .textSelection(.enabled)
            }
            .padding(12)
            .background(
                RoundedRectangle(cornerRadius: 10)
                    .fill(isUser ? Color(red: 0.1, green: 0.1, blue: 0.24) : isError ? Color(red: 0.2, green: 0.05, blue: 0.05) : Color(red: 0.07, green: 0.07, blue: 0.07))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(isUser ? Color.purple.opacity(0.2) : isError ? Color.red.opacity(0.2) : Color.gray.opacity(0.1), lineWidth: 1)
            )

            if !isUser { Spacer(minLength: 60) }
        }
    }
}

// MARK: - Agents Tab

struct AgentsTab: View {
    @EnvironmentObject var orchestrator: OrchestratorService

    var managers: [AgentInfo] {
        orchestrator.agents.filter { $0.name.contains("manager") || $0.name.contains("king") }
    }

    var workers: [AgentInfo] {
        orchestrator.agents.filter { !$0.name.contains("manager") && !$0.name.contains("king") }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Hierarchy visualization
                Text("AGENT HIERARCHY")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(.gray)
                    .tracking(2)

                // King
                ForEach(managers.filter { $0.name.contains("king") }) { agent in
                    AgentCard(agent: agent, isKing: true, status: orchestrator.agentStatuses[agent.name])
                }

                // Managers + their workers
                HStack(alignment: .top, spacing: 16) {
                    ForEach(managers.filter { !$0.name.contains("king") }) { manager in
                        VStack(spacing: 8) {
                            AgentCard(agent: manager, isKing: false, status: orchestrator.agentStatuses[manager.name])

                            let prefix = managerWorkerPrefix(manager.name)
                            ForEach(workers.filter { $0.name.hasPrefix(prefix) }) { worker in
                                AgentCard(agent: worker, isKing: false, status: orchestrator.agentStatuses[worker.name])
                            }
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
            }
            .padding(20)
        }
        .onAppear {
            for agent in orchestrator.agents {
                orchestrator.checkAgentStatus(agent.name)
            }
        }
    }

    func managerWorkerPrefix(_ managerName: String) -> String {
        if managerName.contains("alpha") { return "general" }
        if managerName.contains("beta") { return "coding" }
        if managerName.contains("gamma") { return "agentic" }
        return ""
    }
}

struct AgentCard: View {
    let agent: AgentInfo
    let isKing: Bool
    let status: String?

    var statusColor: Color {
        switch status {
        case "online": return .green
        case "offline": return .red
        default: return .yellow
        }
    }

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: isKing ? "crown.fill" : agent.name.contains("manager") ? "person.3.fill" : "person.fill")
                .font(.system(size: isKing ? 16 : 12))
                .foregroundColor(isKing ? .yellow : .purple)
                .frame(width: 20)

            VStack(alignment: .leading, spacing: 2) {
                Text(agent.name)
                    .font(.system(size: 12, weight: .semibold, design: .monospaced))
                    .foregroundColor(.white)
                HStack(spacing: 6) {
                    Text(":\(agent.port)")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.gray)
                    if let model = agent.model {
                        Text(model)
                            .font(.system(size: 9))
                            .foregroundColor(.purple.opacity(0.6))
                            .padding(.horizontal, 4)
                            .padding(.vertical, 1)
                            .background(Color.purple.opacity(0.1))
                            .cornerRadius(3)
                    }
                }
            }

            Spacer()

            Circle()
                .fill(statusColor)
                .frame(width: 8, height: 8)
        }
        .padding(10)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(isKing ? Color(red: 0.1, green: 0.08, blue: 0.02) : Color(red: 0.06, green: 0.06, blue: 0.1))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(isKing ? Color.yellow.opacity(0.2) : Color.purple.opacity(0.1), lineWidth: 1)
        )
    }
}

// MARK: - Activity Tab

struct ActivityTab: View {
    @EnvironmentObject var orchestrator: OrchestratorService

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Stats header
            if let stats = orchestrator.activityStats {
                HStack(spacing: 20) {
                    StatPill(label: "Total", value: "\(stats.total)")
                    StatPill(label: "Errors", value: "\(stats.recentErrors)")
                    ForEach(Array(stats.byCategory.sorted(by: { $0.value > $1.value }).prefix(5)), id: \.key) { cat, count in
                        StatPill(label: cat, value: "\(count)")
                    }
                    Spacer()
                }
                .padding(16)
                .background(Color.black.opacity(0.3))

                Divider().background(Color.gray.opacity(0.2))
            }

            // Activity list
            List(orchestrator.recentActivity) { entry in
                HStack(spacing: 10) {
                    Circle()
                        .fill(entry.error != nil ? Color.red : categoryColor(entry.category))
                        .frame(width: 6, height: 6)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(entry.summary)
                            .font(.system(size: 12))
                            .foregroundColor(.white.opacity(0.85))
                            .lineLimit(2)

                        HStack(spacing: 8) {
                            Text(entry.category)
                                .font(.system(size: 9, weight: .medium))
                                .foregroundColor(.purple)
                                .padding(.horizontal, 5)
                                .padding(.vertical, 1)
                                .background(Color.purple.opacity(0.1))
                                .cornerRadius(3)

                            if let mgr = entry.manager, !mgr.isEmpty {
                                Text(mgr)
                                    .font(.system(size: 9))
                                    .foregroundColor(.blue)
                            }

                            Text(entry.timestamp)
                                .font(.system(size: 9))
                                .foregroundColor(.gray.opacity(0.5))
                        }
                    }

                    Spacer()
                }
                .listRowBackground(Color.clear)
                .listRowSeparatorTint(Color.gray.opacity(0.1))
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
        }
    }

    func categoryColor(_ cat: String) -> Color {
        switch cat {
        case "chat": return .purple
        case "delegation", "dispatch": return .blue
        case "tool_call": return .cyan
        case "error", "failure": return .red
        case "startup": return .green
        default: return .gray
        }
    }
}

struct StatPill: View {
    let label: String
    let value: String

    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.system(size: 14, weight: .bold, design: .monospaced))
                .foregroundColor(.white)
            Text(label)
                .font(.system(size: 9))
                .foregroundColor(.gray)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(Color(red: 0.06, green: 0.06, blue: 0.12))
        .cornerRadius(8)
    }
}

// MARK: - Web Dashboard Tab (embeds existing HTML)

struct WebDashboardTab: View {
    @EnvironmentObject var orchestrator: OrchestratorService

    var body: some View {
        WebView(htmlPath: dashboardPath, baseURL: orchestrator.baseURL)
    }

    var dashboardPath: String {
        // Try to find the dashboard HTML relative to the project
        let paths = [
            NSHomeDirectory() + "/openclaw-army/dashboard/index.html",
            Bundle.main.path(forResource: "dashboard", ofType: "html") ?? ""
        ]
        return paths.first(where: { FileManager.default.fileExists(atPath: $0) }) ?? paths[0]
    }
}

struct WebView: NSViewRepresentable {
    let htmlPath: String
    let baseURL: String

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.setValue(false, forKey: "drawsBackground")
        loadContent(webView)
        return webView
    }

    func updateNSView(_ nsView: WKWebView, context: Context) {}

    private func loadContent(_ webView: WKWebView) {
        let fileURL = URL(fileURLWithPath: htmlPath)
        if FileManager.default.fileExists(atPath: htmlPath) {
            webView.loadFileURL(fileURL, allowingReadAccessTo: fileURL.deletingLastPathComponent())
        } else {
            webView.loadHTMLString("<html><body style='background:#000;color:#888;font-family:monospace;padding:40px;'><h2>Dashboard not found</h2><p>Expected at: \(htmlPath)</p></body></html>", baseURL: nil)
        }
    }
}

// MARK: - Settings

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

            Section("Polling") {
                Button("Refresh Now") { orchestrator.fetchAll() }
            }
        }
        .padding(20)
        .frame(width: 400, height: 200)
    }
}
