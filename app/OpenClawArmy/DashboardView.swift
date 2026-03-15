import SwiftUI
import AppKit

// MARK: - Main Dashboard

struct DashboardView: View {
    @EnvironmentObject var orchestrator: OrchestratorService
    @State private var selectedTab = 0
    @State private var animateGlow = false

    var body: some View {
        ZStack {
            // Deep space background
            SpaceBackground()
                .ignoresSafeArea()

            VStack(spacing: 0) {
                TopBar()
                    .environmentObject(orchestrator)

                // Tab bar
                HStack(spacing: 2) {
                    KingTabButton(title: "Overview", icon: "square.grid.2x2", index: 0, selected: $selectedTab)
                    KingTabButton(title: "Chat", icon: "bubble.left.and.text.bubble.right", index: 1, selected: $selectedTab)
                    KingTabButton(title: "Agents", icon: "person.3.sequence", index: 2, selected: $selectedTab)
                    KingTabButton(title: "Activity", icon: "waveform.path.ecg", index: 3, selected: $selectedTab)
                    KingTabButton(title: "Neural Map", icon: "brain", index: 4, selected: $selectedTab)
                    Spacer()
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 6)
                .background(Color.black.opacity(0.4))

                // Glowing divider
                Rectangle()
                    .fill(
                        LinearGradient(
                            colors: [.clear, Color.cyan.opacity(0.4), Color(red: 0.5, green: 0.5, blue: 0.9).opacity(0.6), Color.cyan.opacity(0.4), .clear],
                            startPoint: .leading, endPoint: .trailing
                        )
                    )
                    .frame(height: 1)

                // Content
                Group {
                    switch selectedTab {
                    case 0: OverviewTab()
                    case 1: ChatTab()
                    case 2: AgentsTab()
                    case 3: ActivityTab()
                    case 4: NeuralMapTab()
                    default: OverviewTab()
                    }
                }
                .environmentObject(orchestrator)
                .transition(.opacity.combined(with: .move(edge: .bottom)))
            }
        }
        .preferredColorScheme(.dark)
    }
}

// MARK: - Space Background

struct SpaceBackground: View {
    @State private var phase: Double = 0

    var body: some View {
        Canvas { context, size in
            // Deep black base
            context.fill(Path(CGRect(origin: .zero, size: size)),
                        with: .color(Color(red: 0.01, green: 0.01, blue: 0.03)))

            // Subtle radial glow
            let center = CGPoint(x: size.width * 0.5, y: size.height * 0.4)
            context.fill(
                Path(ellipseIn: CGRect(x: center.x - 400, y: center.y - 300, width: 800, height: 600)),
                with: .radialGradient(
                    Gradient(colors: [
                        Color(red: 0.05, green: 0.05, blue: 0.15).opacity(0.4),
                        Color.clear
                    ]),
                    center: center,
                    startRadius: 0,
                    endRadius: 400
                )
            )

            // Star dots
            let starSeed: UInt64 = 42
            var rng = SeededRNG(seed: starSeed)
            for _ in 0..<200 {
                let x = CGFloat.random(in: 0...size.width, using: &rng)
                let y = CGFloat.random(in: 0...size.height, using: &rng)
                let r = CGFloat.random(in: 0.3...1.2, using: &rng)
                let brightness = Double.random(in: 0.15...0.6, using: &rng)
                context.fill(
                    Path(ellipseIn: CGRect(x: x - r, y: y - r, width: r * 2, height: r * 2)),
                    with: .color(Color(white: brightness).opacity(0.7))
                )
            }
        }
    }
}

// Simple seeded RNG for deterministic stars
struct SeededRNG: RandomNumberGenerator {
    var state: UInt64
    init(seed: UInt64) { state = seed }
    mutating func next() -> UInt64 {
        state &+= 0x9E3779B97F4A7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }
}

// MARK: - Top Bar

struct TopBar: View {
    @EnvironmentObject var orchestrator: OrchestratorService
    @State private var crownGlow = false

    var body: some View {
        HStack(spacing: 16) {
            // Logo
            HStack(spacing: 10) {
                ZStack {
                    // Glow behind crown
                    Image(systemName: "crown.fill")
                        .font(.system(size: 22))
                        .foregroundColor(.white.opacity(0.3))
                        .blur(radius: 8)
                        .scaleEffect(crownGlow ? 1.2 : 1.0)

                    Image(systemName: "crown.fill")
                        .font(.system(size: 22))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [
                                    Color(red: 0.78, green: 0.78, blue: 0.84),
                                    Color.white,
                                    Color(red: 0.7, green: 0.7, blue: 0.78)
                                ],
                                startPoint: .top, endPoint: .bottom
                            )
                        )
                }

                VStack(alignment: .leading, spacing: 1) {
                    Text("KING AI")
                        .font(.system(size: 16, weight: .black, design: .default))
                        .tracking(3)
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Color.white, Color(red: 0.8, green: 0.8, blue: 0.9)],
                                startPoint: .leading, endPoint: .trailing
                            )
                        )
                    Text("Neural Command Center")
                        .font(.system(size: 9, weight: .medium))
                        .foregroundColor(Color.cyan.opacity(0.5))
                        .tracking(1.5)
                }
            }

            Spacer()

            // Status pills
            if let health = orchestrator.health {
                StatusChip(label: "Core", value: health.status == "healthy" ? "Online" : "Offline",
                          color: health.status == "healthy" ? .green : .red)
            } else {
                StatusChip(label: "Core", value: orchestrator.isConnected ? "Connected" : "Offline",
                          color: orchestrator.isConnected ? .green : .red)
            }

            StatusChip(label: "Agents", value: "\(orchestrator.agents.count)",
                      color: .cyan)

            if let stats = orchestrator.activityStats {
                StatusChip(label: "Events", value: "\(stats.totalInMemory)", color: Color(red: 0.6, green: 0.6, blue: 0.9))
            }

            Button(action: { orchestrator.fetchAll() }) {
                Image(systemName: "arrow.triangle.2.circlepath")
                    .font(.system(size: 12))
                    .foregroundColor(.gray)
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .background(
            LinearGradient(
                colors: [
                    Color(red: 0.03, green: 0.03, blue: 0.08),
                    Color(red: 0.02, green: 0.02, blue: 0.05)
                ],
                startPoint: .leading, endPoint: .trailing
            )
        )
        .onAppear {
            withAnimation(.easeInOut(duration: 2).repeatForever(autoreverses: true)) {
                crownGlow = true
            }
        }
    }
}

struct StatusChip: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        HStack(spacing: 5) {
            Circle()
                .fill(color)
                .frame(width: 5, height: 5)
            Text(label)
                .font(.system(size: 10))
                .foregroundColor(.gray)
            Text(value)
                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                .foregroundColor(color)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(color.opacity(0.08))
        .cornerRadius(10)
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(color.opacity(0.15), lineWidth: 1))
    }
}

struct KingTabButton: View {
    let title: String
    let icon: String
    let index: Int
    @Binding var selected: Int
    @State private var isHovered = false

    var isSelected: Bool { selected == index }

    var body: some View {
        Button(action: { withAnimation(.spring(response: 0.3)) { selected = index } }) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: 11))
                Text(title)
                    .font(.system(size: 12, weight: isSelected ? .semibold : .regular))
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 7)
            .foregroundColor(isSelected ? .white : isHovered ? .white.opacity(0.7) : .gray)
            .background(
                Group {
                    if isSelected {
                        LinearGradient(
                            colors: [Color.cyan.opacity(0.15), Color(red: 0.3, green: 0.3, blue: 0.7).opacity(0.15)],
                            startPoint: .leading, endPoint: .trailing
                        )
                    } else {
                        Color.clear
                    }
                }
            )
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(isSelected ? Color.cyan.opacity(0.3) : Color.clear, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .onHover { isHovered = $0 }
    }
}

// MARK: - Overview Tab

struct OverviewTab: View {
    @EnvironmentObject var orchestrator: OrchestratorService

    var body: some View {
        ScrollView {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 300), spacing: 16)], spacing: 16) {
                // System Status
                GlassCard(title: "System Status", icon: "heart.fill", accentColor: .green) {
                    if let health = orchestrator.health {
                        InfoRow(label: "Core Status", value: health.status.capitalized, color: health.status == "healthy" ? .green : .red)
                        InfoRow(label: "Active Workflows", value: "\(health.activeWorkflows)", color: .cyan)
                        InfoRow(label: "Chat Sessions", value: "\(health.activeChatSessions)", color: Color(red: 0.6, green: 0.6, blue: 0.9))
                        InfoRow(label: "Total Workflows", value: "\(health.totalWorkflows)", color: .gray)
                    } else {
                        HStack {
                            ProgressView().scaleEffect(0.7)
                            Text(orchestrator.isConnected ? "Loading..." : "Offline")
                                .foregroundColor(.gray).font(.system(size: 13))
                        }
                    }
                }

                // Agent Network
                GlassCard(title: "Agent Network (\(orchestrator.agents.count))", icon: "person.3.sequence.fill", accentColor: .cyan) {
                    let managers = orchestrator.agents.filter { $0.role == "manager" || $0.role == "king" }
                    let workers = orchestrator.agents.filter { $0.role == "worker" }

                    InfoRow(label: "King + Managers", value: "\(managers.count)", color: .cyan)
                    InfoRow(label: "Workers", value: "\(workers.count)", color: Color(red: 0.5, green: 0.5, blue: 0.8))

                    let alive = orchestrator.agentStatuses.values.filter { $0 == "alive" }.count
                    let total = orchestrator.agents.count
                    InfoRow(label: "Online", value: "\(alive)/\(total)",
                           color: alive == total ? .green : .yellow)
                }

                // Activity Summary
                GlassCard(title: "Activity", icon: "waveform.path.ecg", accentColor: Color(red: 0.6, green: 0.5, blue: 0.9)) {
                    if let stats = orchestrator.activityStats {
                        InfoRow(label: "Total Events", value: "\(stats.totalInMemory)", color: .white)
                        InfoRow(label: "Sessions", value: "\(stats.uniqueSessions)", color: .cyan)

                        let topTypes = stats.eventTypes.sorted { $0.value > $1.value }.prefix(5)
                        ForEach(Array(topTypes), id: \.key) { key, value in
                            InfoRow(label: key.replacingOccurrences(of: "_", with: " "),
                                   value: "\(value)", color: .gray)
                        }
                    } else {
                        Text("Loading...").foregroundColor(.gray).font(.system(size: 13))
                    }
                }

                // Quality
                GlassCard(title: "Intelligence Health", icon: "brain.head.profile", accentColor: .orange) {
                    if let q = orchestrator.quality {
                        if let analysis = q.degradationAnalysis {
                            InfoRow(label: "Degradation",
                                   value: (analysis.degradationDetected == true) ? "Detected" : "None",
                                   color: (analysis.degradationDetected == true) ? .red : .green)
                            if let trend = analysis.trend {
                                InfoRow(label: "Trend", value: trend, color: .gray)
                            }
                        }
                    } else {
                        Text("Analyzing...").foregroundColor(.gray).font(.system(size: 13))
                    }
                }

                // Connection
                GlassCard(title: "Connection", icon: "antenna.radiowaves.left.and.right", accentColor: .blue) {
                    InfoRow(label: "Endpoint", value: orchestrator.baseURL, color: .white)
                    InfoRow(label: "Connected", value: orchestrator.isConnected ? "Yes" : "No",
                           color: orchestrator.isConnected ? .green : .red)
                    if let updated = orchestrator.lastUpdated {
                        InfoRow(label: "Last Sync", value: formatDate(updated), color: .gray)
                    }
                    if let error = orchestrator.lastError {
                        Text(error)
                            .font(.system(size: 10))
                            .foregroundColor(.red.opacity(0.7))
                            .lineLimit(2)
                    }
                }

                // Recent Activity
                GlassCard(title: "Recent Events", icon: "clock.fill", accentColor: .orange) {
                    if orchestrator.recentActivity.isEmpty {
                        Text("No recent activity").foregroundColor(.gray).font(.system(size: 13))
                    } else {
                        ForEach(orchestrator.recentActivity.prefix(6)) { entry in
                            HStack(spacing: 8) {
                                Circle()
                                    .fill(activityColor(entry.type ?? ""))
                                    .frame(width: 5, height: 5)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(entry.content ?? "")
                                        .font(.system(size: 11))
                                        .foregroundColor(.white.opacity(0.7))
                                        .lineLimit(1)
                                    if let ts = entry.ts {
                                        Text(formatTimestamp(ts))
                                            .font(.system(size: 9, design: .monospaced))
                                            .foregroundColor(.gray.opacity(0.4))
                                    }
                                }
                                Spacer()
                                Text(entry.type ?? "")
                                    .font(.system(size: 9))
                                    .foregroundColor(.gray)
                                    .padding(.horizontal, 5)
                                    .padding(.vertical, 2)
                                    .background(Color.gray.opacity(0.1))
                                    .cornerRadius(3)
                            }
                        }
                    }
                }
            }
            .padding(20)
        }
    }

    func activityColor(_ type: String) -> Color {
        switch type {
        case "delegation": return .cyan
        case "error", "error_response": return .red
        case "llm_thinking": return Color(red: 0.6, green: 0.5, blue: 0.9)
        case "llm_tool_calls": return .blue
        case "response": return .green
        default: return .gray
        }
    }
}

// MARK: - Glass Card

struct GlassCard<Content: View>: View {
    let title: String
    let icon: String
    let accentColor: Color
    @ViewBuilder let content: () -> Content
    @State private var isHovered = false

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

            Rectangle()
                .fill(
                    LinearGradient(colors: [accentColor.opacity(0.3), .clear],
                                   startPoint: .leading, endPoint: .trailing)
                )
                .frame(height: 1)

            content()
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 14)
                .fill(Color(red: 0.04, green: 0.04, blue: 0.09).opacity(0.85))
                .overlay(
                    RoundedRectangle(cornerRadius: 14)
                        .fill(
                            LinearGradient(
                                colors: [Color.white.opacity(isHovered ? 0.04 : 0.02), Color.clear],
                                startPoint: .topLeading, endPoint: .bottomTrailing
                            )
                        )
                )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(
                    LinearGradient(
                        colors: [accentColor.opacity(0.2), Color.gray.opacity(0.1)],
                        startPoint: .topLeading, endPoint: .bottomTrailing
                    ),
                    lineWidth: 1
                )
        )
        .shadow(color: accentColor.opacity(isHovered ? 0.1 : 0), radius: 12)
        .onHover { isHovered = $0 }
        .animation(.easeOut(duration: 0.2), value: isHovered)
    }
}

struct InfoRow: View {
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
                .lineLimit(1)
        }
    }
}

// MARK: - Chat Tab

struct ChatTab: View {
    @EnvironmentObject var orchestrator: OrchestratorService
    @State private var chatInput = ""
    @State private var showFilePicker = false

    var body: some View {
        HStack(spacing: 0) {
            // Main chat area
            VStack(spacing: 0) {
                // Messages
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(orchestrator.chatMessages) { msg in
                                ChatBubble(message: msg)
                                    .id(msg.id)
                            }

                            // Thinking entries inline when visible
                            if orchestrator.isThinkingVisible && orchestrator.isSending {
                                ForEach(orchestrator.thinkingEntries.suffix(10)) { entry in
                                    ThinkingBubble(entry: entry)
                                }
                            }

                            if orchestrator.isSending && !orchestrator.isThinkingVisible {
                                ThinkingIndicator()
                            }
                        }
                        .padding(20)
                    }
                    .onChange(of: orchestrator.chatMessages.count) {
                        withAnimation(.spring(response: 0.3)) {
                            proxy.scrollTo(orchestrator.chatMessages.last?.id, anchor: .bottom)
                        }
                    }
                    .onChange(of: orchestrator.thinkingEntries.count) {
                        if orchestrator.isThinkingVisible {
                            withAnimation {
                                proxy.scrollTo(orchestrator.chatMessages.last?.id, anchor: .bottom)
                            }
                        }
                    }
                }

                // Glowing divider
                Rectangle()
                    .fill(LinearGradient(
                        colors: [.clear, Color.cyan.opacity(0.2), .clear],
                        startPoint: .leading, endPoint: .trailing
                    ))
                    .frame(height: 1)

                // Input area
                HStack(spacing: 10) {
                    // File upload button
                    Button(action: { showFilePicker = true }) {
                        Image(systemName: "paperclip")
                            .font(.system(size: 14))
                            .foregroundColor(.gray)
                    }
                    .buttonStyle(.plain)
                    .help("Attach file or image")

                    // Thinking toggle
                    Button(action: {
                        withAnimation(.spring(response: 0.3)) {
                            orchestrator.isThinkingVisible.toggle()
                        }
                    }) {
                        Image(systemName: orchestrator.isThinkingVisible ? "brain.fill" : "brain")
                            .font(.system(size: 14))
                            .foregroundColor(orchestrator.isThinkingVisible ? .cyan : .gray)
                    }
                    .buttonStyle(.plain)
                    .help("Toggle thinking view")

                    TextField("Talk to King AI...", text: $chatInput)
                        .textFieldStyle(.plain)
                        .font(.system(size: 14))
                        .foregroundColor(.white)
                        .padding(10)
                        .background(Color(red: 0.03, green: 0.03, blue: 0.08))
                        .cornerRadius(10)
                        .overlay(
                            RoundedRectangle(cornerRadius: 10)
                                .stroke(Color.cyan.opacity(0.15), lineWidth: 1)
                        )
                        .onSubmit { sendMessage() }

                    Button(action: sendMessage) {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 24))
                            .foregroundStyle(
                                chatInput.isEmpty ?
                                AnyShapeStyle(Color.gray.opacity(0.3)) :
                                AnyShapeStyle(LinearGradient(colors: [.cyan, Color(red: 0.5, green: 0.5, blue: 0.9)],
                                               startPoint: .topLeading, endPoint: .bottomTrailing))
                            )
                    }
                    .buttonStyle(.plain)
                    .disabled(chatInput.isEmpty || orchestrator.isSending)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .background(Color(red: 0.02, green: 0.02, blue: 0.05).opacity(0.9))
            }
        }
        .fileImporter(isPresented: $showFilePicker, allowedContentTypes: [.image, .pdf, .plainText, .data]) { result in
            if case .success(let url) = result {
                let fileName = url.lastPathComponent
                if url.startAccessingSecurityScopedResource() {
                    defer { url.stopAccessingSecurityScopedResource() }
                    orchestrator.sendChat(message: "📎 Uploaded: \(fileName)")
                }
            }
        }
    }

    func sendMessage() {
        let text = chatInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        chatInput = ""
        orchestrator.sendChat(message: text)
    }
}

struct ChatBubble: View {
    let message: ChatMessage
    @State private var appeared = false

    var isUser: Bool { message.role == .user }
    var isError: Bool { message.role == .error }
    var isSystem: Bool { message.role == .system }

    var bubbleColor: Color {
        if isUser { return Color(red: 0.06, green: 0.06, blue: 0.18) }
        if isError { return Color(red: 0.15, green: 0.03, blue: 0.03) }
        if isSystem { return Color(red: 0.04, green: 0.06, blue: 0.08) }
        return Color(red: 0.04, green: 0.04, blue: 0.08)
    }

    var borderColor: Color {
        if isUser { return Color.cyan.opacity(0.2) }
        if isError { return Color.red.opacity(0.2) }
        if isSystem { return Color(red: 0.5, green: 0.5, blue: 0.8).opacity(0.15) }
        return Color.gray.opacity(0.1)
    }

    var roleLabel: String {
        switch message.role {
        case .user: return "YOU"
        case .assistant: return "KING AI"
        case .error: return "ERROR"
        case .system: return "SYSTEM"
        case .thinking: return "THINKING"
        }
    }

    var roleLabelColor: Color {
        switch message.role {
        case .user: return .cyan.opacity(0.6)
        case .assistant: return Color(red: 0.7, green: 0.7, blue: 0.85)
        case .error: return .red.opacity(0.6)
        case .system: return Color(red: 0.5, green: 0.5, blue: 0.7)
        case .thinking: return Color(red: 0.6, green: 0.5, blue: 0.9)
        }
    }

    var body: some View {
        HStack {
            if isUser { Spacer(minLength: 80) }

            VStack(alignment: isUser ? .trailing : .leading, spacing: 4) {
                HStack(spacing: 6) {
                    if !isUser {
                        Image(systemName: message.role == .assistant ? "crown.fill" : "circle.fill")
                            .font(.system(size: 8))
                            .foregroundColor(roleLabelColor)
                    }
                    Text(roleLabel)
                        .font(.system(size: 9, weight: .bold))
                        .foregroundColor(roleLabelColor)
                        .tracking(1.5)
                    if isUser {
                        Image(systemName: "person.fill")
                            .font(.system(size: 8))
                            .foregroundColor(roleLabelColor)
                    }
                }

                Text(message.text)
                    .font(.system(size: 13))
                    .foregroundColor(isError ? .red.opacity(0.8) : .white.opacity(0.9))
                    .textSelection(.enabled)
                    .lineSpacing(3)

                Text(formatDate(message.timestamp))
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(roleLabelColor.opacity(0.35))
            }
            .padding(14)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(bubbleColor)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(borderColor, lineWidth: 1)
            )
            .contextMenu {
                Button("Copy Message") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(message.text, forType: .string)
                }
            }
            .opacity(appeared ? 1 : 0)
            .offset(y: appeared ? 0 : 8)

            if !isUser { Spacer(minLength: 80) }
        }
        .onAppear {
            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                appeared = true
            }
        }
    }
}

struct ThinkingIndicator: View {
    @State private var dotPhase = 0

    var body: some View {
        HStack {
            HStack(spacing: 4) {
                Image(systemName: "brain")
                    .font(.system(size: 11))
                    .foregroundColor(Color(red: 0.6, green: 0.5, blue: 0.9))

                Text("Thinking")
                    .font(.system(size: 12))
                    .foregroundColor(.gray)

                HStack(spacing: 3) {
                    ForEach(0..<3) { i in
                        Circle()
                            .fill(Color.cyan.opacity(0.6))
                            .frame(width: 4, height: 4)
                            .scaleEffect(dotPhase == i ? 1.3 : 0.7)
                    }
                }
            }
            .padding(10)
            .background(Color(red: 0.03, green: 0.03, blue: 0.08).opacity(0.8))
            .cornerRadius(8)

            Spacer()
        }
        .onAppear {
            Timer.scheduledTimer(withTimeInterval: 0.4, repeats: true) { _ in
                withAnimation(.easeInOut(duration: 0.3)) {
                    dotPhase = (dotPhase + 1) % 3
                }
            }
        }
    }
}

struct ThinkingBubble: View {
    let entry: ActivityEntry

    var typeColor: Color {
        switch entry.type {
        case "llm_thinking": return Color(red: 0.6, green: 0.5, blue: 0.9)
        case "llm_tool_calls": return .cyan
        case "delegation": return .green
        case "error": return .red
        default: return .gray
        }
    }

    var typeIcon: String {
        switch entry.type {
        case "llm_thinking": return "brain"
        case "llm_tool_calls": return "wrench.and.screwdriver"
        case "delegation": return "arrow.triangle.branch"
        case "error": return "exclamationmark.triangle"
        default: return "circle"
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: typeIcon)
                .font(.system(size: 10))
                .foregroundColor(typeColor)
                .frame(width: 14)

            VStack(alignment: .leading, spacing: 2) {
                Text(entry.type?.uppercased().replacingOccurrences(of: "_", with: " ") ?? "")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(typeColor.opacity(0.7))
                    .tracking(1)

                Text(entry.content ?? "")
                    .font(.system(size: 11))
                    .foregroundColor(.gray)
                    .textSelection(.enabled)
                    .lineLimit(3)
            }

            Spacer()
        }
        .padding(8)
        .background(
            RoundedRectangle(cornerRadius: 6)
                .fill(typeColor.opacity(0.05))
                .overlay(
                    RoundedRectangle(cornerRadius: 6)
                        .stroke(typeColor.opacity(0.1), lineWidth: 1)
                )
        )
        .contextMenu {
            Button("Copy Thinking Entry") {
                let line = entry.content ?? ""
                NSPasteboard.general.clearContents()
                NSPasteboard.general.setString(line, forType: .string)
            }
        }
    }
}

// MARK: - Agents Tab

struct AgentsTab: View {
    @EnvironmentObject var orchestrator: OrchestratorService

    var king: [AgentInfo] { orchestrator.agents.filter { $0.role == "king" } }
    var managers: [AgentInfo] { orchestrator.agents.filter { $0.role == "manager" } }
    var workers: [AgentInfo] { orchestrator.agents.filter { $0.role == "worker" } }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("NEURAL NETWORK HIERARCHY")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(.gray)
                    .tracking(2)
                    .padding(.horizontal, 20)
                    .padding(.top, 16)

                // King
                ForEach(king) { agent in
                    AgentCard(agent: agent, status: orchestrator.agentStatuses[agent.name], isKing: true)
                        .padding(.horizontal, 20)
                }

                // Managers + Workers
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 260), spacing: 16)], spacing: 16) {
                    ForEach(managers) { manager in
                        VStack(spacing: 8) {
                            AgentCard(agent: manager, status: orchestrator.agentStatuses[manager.name], isKing: false)

                            let myWorkers = workers.filter { $0.manager == manager.name }
                            ForEach(myWorkers) { worker in
                                AgentCard(agent: worker, status: orchestrator.agentStatuses[worker.name], isKing: false)
                                    .padding(.leading, 16)
                            }
                        }
                    }
                }
                .padding(.horizontal, 20)

                Spacer(minLength: 20)
            }
        }
    }
}

struct AgentCard: View {
    let agent: AgentInfo
    let status: String?
    let isKing: Bool
    @State private var isHovered = false

    var statusColor: Color {
        switch status {
        case "alive": return .green
        case "unreachable": return .red
        default: return .yellow
        }
    }

    var statusLabel: String {
        switch status {
        case "alive": return "Online"
        case "unreachable": return "Offline"
        default: return "Checking..."
        }
    }

    var roleIcon: String {
        if isKing || agent.role == "king" { return "crown.fill" }
        if agent.role == "manager" { return "person.3.fill" }
        if agent.name.contains("coding") { return "chevron.left.forwardslash.chevron.right" }
        if agent.name.contains("agentic") { return "magnifyingglass" }
        return "person.fill"
    }

    var accentColor: Color {
        if isKing { return Color(red: 0.78, green: 0.78, blue: 0.84) }
        if agent.role == "manager" { return .cyan }
        return Color(red: 0.5, green: 0.5, blue: 0.8)
    }

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: roleIcon)
                .font(.system(size: isKing ? 18 : 13))
                .foregroundColor(accentColor)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 2) {
                Text(agent.name)
                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                    .foregroundColor(.white)
                HStack(spacing: 8) {
                    Text(":\(agent.port)")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.gray.opacity(0.6))
                    if let role = agent.role {
                        Text(role.uppercased())
                            .font(.system(size: 8, weight: .bold))
                            .foregroundColor(accentColor.opacity(0.7))
                            .tracking(1)
                            .padding(.horizontal, 5)
                            .padding(.vertical, 1)
                            .background(accentColor.opacity(0.1))
                            .cornerRadius(3)
                    }
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 2) {
                Circle()
                    .fill(statusColor)
                    .frame(width: 8, height: 8)
                Text(statusLabel)
                    .font(.system(size: 9))
                    .foregroundColor(statusColor.opacity(0.7))
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(isKing ?
                      Color(red: 0.06, green: 0.06, blue: 0.1) :
                      Color(red: 0.04, green: 0.04, blue: 0.08))
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .fill(Color.white.opacity(isHovered ? 0.03 : 0))
                )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(
                    isKing ?
                    LinearGradient(colors: [Color(red: 0.78, green: 0.78, blue: 0.84).opacity(0.3), Color.clear],
                                   startPoint: .topLeading, endPoint: .bottomTrailing) :
                    LinearGradient(colors: [accentColor.opacity(0.15), Color.clear],
                                   startPoint: .topLeading, endPoint: .bottomTrailing),
                    lineWidth: 1
                )
        )
        .onHover { isHovered = $0 }
        .animation(.easeOut(duration: 0.15), value: isHovered)
    }
}

// MARK: - Activity Tab

struct ActivityTab: View {
    @EnvironmentObject var orchestrator: OrchestratorService

    var body: some View {
        VStack(spacing: 0) {
            // Stats header
            if let stats = orchestrator.activityStats {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 12) {
                        ActivityPill(label: "Total", value: "\(stats.totalInMemory)", color: .white)
                        ActivityPill(label: "Sessions", value: "\(stats.uniqueSessions)", color: .cyan)

                        ForEach(Array(stats.eventTypes.sorted { $0.value > $1.value }.prefix(6)), id: \.key) { key, value in
                            ActivityPill(label: key.replacingOccurrences(of: "_", with: " "), value: "\(value)",
                                       color: activityTypeColor(key))
                        }
                    }
                    .padding(14)
                }
                .background(Color.black.opacity(0.3))

                Rectangle()
                    .fill(LinearGradient(colors: [.clear, Color.cyan.opacity(0.15), .clear],
                                         startPoint: .leading, endPoint: .trailing))
                    .frame(height: 1)
            }

            // Activity list
            if orchestrator.recentActivity.isEmpty {
                Spacer()
                VStack(spacing: 8) {
                    Image(systemName: "waveform.path.ecg")
                        .font(.system(size: 30))
                        .foregroundColor(.gray.opacity(0.3))
                    Text("No activity recorded")
                        .foregroundColor(.gray)
                        .font(.system(size: 13))
                }
                Spacer()
            } else {
                List(orchestrator.recentActivity) { entry in
                    HStack(spacing: 10) {
                        Rectangle()
                            .fill(activityTypeColor(entry.type ?? ""))
                            .frame(width: 3)
                            .cornerRadius(1.5)

                        VStack(alignment: .leading, spacing: 3) {
                            Text(entry.content ?? "")
                                .font(.system(size: 12))
                                .foregroundColor(.white.opacity(0.85))
                                .lineLimit(2)

                            HStack(spacing: 8) {
                                if let type = entry.type {
                                    Text(type.replacingOccurrences(of: "_", with: " "))
                                        .font(.system(size: 9, weight: .medium))
                                        .foregroundColor(activityTypeColor(type))
                                        .padding(.horizontal, 5)
                                        .padding(.vertical, 1)
                                        .background(activityTypeColor(type).opacity(0.1))
                                        .cornerRadius(3)
                                }

                                if let ts = entry.ts {
                                    Text(formatTimestamp(ts))
                                        .font(.system(size: 9, design: .monospaced))
                                        .foregroundColor(.gray.opacity(0.4))
                                }
                            }
                        }
                    }
                    .listRowBackground(Color.clear)
                    .listRowSeparatorTint(Color.gray.opacity(0.08))
                }
                .listStyle(.plain)
                .scrollContentBackground(.hidden)
            }
        }
    }

    func activityTypeColor(_ type: String) -> Color {
        switch type {
        case "delegation", "dispatch": return .cyan
        case "llm_thinking": return Color(red: 0.6, green: 0.5, blue: 0.9)
        case "llm_tool_calls": return .blue
        case "llm_call": return Color(red: 0.5, green: 0.5, blue: 0.7)
        case "error", "error_response": return .red
        case "response": return .green
        case "user_message": return Color(red: 0.4, green: 0.6, blue: 0.9)
        default: return .gray
        }
    }
}

struct ActivityPill: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.system(size: 14, weight: .bold, design: .monospaced))
                .foregroundColor(color)
            Text(label)
                .font(.system(size: 9))
                .foregroundColor(.gray)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(color.opacity(0.06))
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(color.opacity(0.1), lineWidth: 1))
    }
}

// MARK: - Neural Map Tab

struct NeuralMapTab: View {
    @EnvironmentObject var orchestrator: OrchestratorService
    @State private var animationPhase: Double = 0

    var body: some View {
        GeometryReader { geo in
            let cx = geo.size.width / 2
            let cy = geo.size.height / 2
            let scale = min(geo.size.width, geo.size.height) / 480

            ZStack {
                // Draw edges
                ForEach(orchestrator.neuralEdges) { edge in
                    if let fromNode = orchestrator.neuralNodes.first(where: { $0.id == edge.from }),
                       let toNode = orchestrator.neuralNodes.first(where: { $0.id == edge.to }) {
                        let fromX = cx + (fromNode.x - 200) * scale
                        let fromY = cy + (fromNode.y - 200) * scale
                        let toX = cx + (toNode.x - 200) * scale
                        let toY = cy + (toNode.y - 200) * scale

                        Path { path in
                            path.move(to: CGPoint(x: fromX, y: fromY))
                            path.addLine(to: CGPoint(x: toX, y: toY))
                        }
                        .stroke(
                            edge.isActive ?
                            Color.cyan.opacity(0.8) :
                            Color.gray.opacity(0.15),
                            lineWidth: edge.isActive ? 2 : 0.8
                        )
                        .shadow(color: edge.isActive ? .cyan.opacity(0.5) : .clear, radius: 4)
                        .animation(.easeInOut(duration: 0.5), value: edge.isActive)
                    }
                }

                // Draw nodes
                ForEach(orchestrator.neuralNodes) { node in
                    let nx = cx + (node.x - 200) * scale
                    let ny = cy + (node.y - 200) * scale

                    NeuralNodeView(node: node, scale: scale, phase: animationPhase)
                        .position(x: nx, y: ny)
                }
            }
        }
        .onAppear {
            Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { _ in
                animationPhase += 0.02
            }
            // Periodic neural pulses
            Timer.scheduledTimer(withTimeInterval: 4, repeats: true) { _ in
                orchestrator.pulseNeuralActivity()
            }
        }
    }
}

// MARK: - Timestamp Helpers

private let _chicagoTZ = TimeZone(identifier: "America/Chicago") ?? .current

private let _utcParseFmt: DateFormatter = {
    let f = DateFormatter()
    f.locale = Locale(identifier: "en_US_POSIX")
    f.timeZone = TimeZone(identifier: "UTC")
    f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
    return f
}()

private let _tsDisplayFmt: DateFormatter = {
    let f = DateFormatter()
    f.locale = Locale(identifier: "en_US_POSIX")
    f.timeZone = _chicagoTZ
    f.dateFormat = "HH:mm:ss"
    return f
}()

func formatDate(_ d: Date) -> String {
    _tsDisplayFmt.string(from: d)
}

func formatTimestamp(_ ts: String) -> String {
    // Strip fractional seconds if present: "2026-03-11T07:36:00.123456" → "2026-03-11T07:36:00"
    let stripped = String(ts.prefix(19))
    if let date = _utcParseFmt.date(from: stripped) {
        return _tsDisplayFmt.string(from: date)
    }
    // Fallback: just take the time portion as-is
    let parts = ts.split(separator: "T")
    guard parts.count >= 2 else { return ts }
    return String(parts[1].prefix(8))
}

struct NeuralNodeView: View {
    let node: NeuralNode
    let scale: CGFloat
    let phase: Double

    var nodeColor: Color {
        switch node.category {
        case .king: return Color(red: 0.85, green: 0.85, blue: 0.92)
        case .manager: return .cyan
        case .worker: return Color(red: 0.5, green: 0.5, blue: 0.8)
        case .memory: return .orange
        case .tool: return .green
        }
    }

    var body: some View {
        let radius = node.radius * scale
        let pulse = sin(phase * 2 + Double(node.x)) * 0.15 + 1.0

        ZStack {
            // Outer glow
            Circle()
                .fill(nodeColor.opacity(node.isActive ? 0.3 : 0.1))
                .frame(width: radius * 4, height: radius * 4)
                .blur(radius: radius)
                .scaleEffect(CGFloat(pulse))

            // Core
            Circle()
                .fill(
                    RadialGradient(
                        colors: [nodeColor, nodeColor.opacity(0.3)],
                        center: .center, startRadius: 0, endRadius: radius
                    )
                )
                .frame(width: radius * 2, height: radius * 2)

            // Label
            if node.category == .king || node.category == .manager || node.category == .memory {
                Text(node.label)
                    .font(.system(size: max(8, 10 * scale), weight: .medium))
                    .foregroundColor(.white.opacity(0.8))
                    .offset(y: radius + 10)
            }
        }
    }
}
