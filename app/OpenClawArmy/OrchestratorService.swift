import Foundation
import Combine

// MARK: - API Response Models

struct HealthResponse: Codable {
    let status: String
    let service: String
    let activeWorkflows: Int
    let totalWorkflows: Int
    let activeChatSessions: Int

    enum CodingKeys: String, CodingKey {
        case status, service
        case activeWorkflows = "active_workflows"
        case totalWorkflows = "total_workflows"
        case activeChatSessions = "active_chat_sessions"
    }
}

struct ActivityStatsResponse: Codable {
    let totalInMemory: Int
    let eventTypes: [String: Int]
    let uniqueSessions: Int

    enum CodingKeys: String, CodingKey {
        case totalInMemory = "total_in_memory"
        case eventTypes = "event_types"
        case uniqueSessions = "unique_sessions"
    }
}

struct ActivityResponse: Codable {
    let entries: [ActivityEntry]
}

struct ActivityEntry: Codable, Identifiable {
    var id = UUID()
    let ts: String?
    let type: String?
    let content: String?
    let sessionId: String?
    let meta: ActivityMeta?

    enum CodingKeys: String, CodingKey {
        case ts, type, content
        case sessionId = "session_id"
        case meta
    }
}

struct ActivityMeta: Codable {
    let dispatched: Bool?
    let attempt: Int?
    let isRateLimit: Bool?

    enum CodingKeys: String, CodingKey {
        case dispatched, attempt
        case isRateLimit = "is_rate_limit"
    }
}

struct AgentsResponse: Codable {
    let agents: [AgentInfo]
}

struct AgentInfo: Codable, Identifiable {
    var id: String { name }
    let name: String
    let port: Int
    let role: String?
    let manager: String?
}

struct AgentStatusResponse: Codable {
    let agent: String
    let status: String
    let port: Int
}

struct ChatAPIResponse: Codable {
    let response: String
    let sessionId: String?
    let delegations: [Delegation]?

    enum CodingKeys: String, CodingKey {
        case response
        case sessionId = "session_id"
        case delegations
    }
}

struct Delegation: Codable, Identifiable {
    var id: String { "\(manager)-\(task.prefix(20))" }
    let manager: String
    let task: String
    let dispatched: Bool?
}

struct QualityResponse: Codable {
    let degradationAnalysis: DegradationAnalysis?
    let recentScores: [QualityScore]?

    enum CodingKeys: String, CodingKey {
        case degradationAnalysis = "degradation_analysis"
        case recentScores = "recent_scores"
    }
}

struct DegradationAnalysis: Codable {
    let degradationDetected: Bool?
    let detail: String?
    let trend: String?

    enum CodingKeys: String, CodingKey {
        case degradationDetected = "degradation_detected"
        case detail, trend
    }
}

struct QualityScore: Codable {
    let timestamp: String?
    let score: Double?
}

// MARK: - Chat Message

struct ChatMessage: Identifiable, Equatable {
    let id: UUID
    let role: MessageRole
    let text: String
    let timestamp: Date
    var imageData: Data?

    enum MessageRole: String {
        case user, assistant, error, system, thinking
    }

    static func == (lhs: ChatMessage, rhs: ChatMessage) -> Bool { lhs.id == rhs.id }
}

// MARK: - Node for Neural Graph

struct NeuralNode: Identifiable {
    let id: String
    var label: String
    var x: CGFloat
    var y: CGFloat
    var vx: CGFloat = 0
    var vy: CGFloat = 0
    var radius: CGFloat = 6
    var pulsePhase: Double = 0
    var isActive: Bool = false
    var category: NodeCategory = .agent

    enum NodeCategory {
        case king, manager, worker, memory, tool
    }
}

struct NeuralEdge: Identifiable {
    let id: String
    let from: String
    let to: String
    var strength: Double = 0.5
    var isActive: Bool = false
}

// MARK: - Service

class OrchestratorService: ObservableObject {
    static let shared = OrchestratorService()

    @Published var baseURL = "http://localhost:18830"
    @Published var isConnected = false
    @Published var health: HealthResponse?
    @Published var activityStats: ActivityStatsResponse?
    @Published var recentActivity: [ActivityEntry] = []
    @Published var agents: [AgentInfo] = []
    @Published var agentStatuses: [String: String] = [:]
    @Published var quality: QualityResponse?
    @Published var lastError: String?

    // Chat
    @Published var chatMessages: [ChatMessage] = []
    @Published var isSending = false
    var sessionId: String = "kingai-\(UUID().uuidString.prefix(8))"

    // Thinking stream
    @Published var thinkingEntries: [ActivityEntry] = []
    @Published var isThinkingVisible = false

    // Neural graph
    @Published var neuralNodes: [NeuralNode] = []
    @Published var neuralEdges: [NeuralEdge] = []

    private var timer: Timer?
    private var wsTask: URLSessionWebSocketTask?
    private let session: URLSession

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 180
        self.session = URLSession(configuration: config)

        chatMessages.append(ChatMessage(
            id: UUID(), role: .system,
            text: "Welcome to King AI. I'm your neural command center — ask me anything or assign a task.",
            timestamp: Date()
        ))
    }

    func startPolling() {
        fetchAll()
        connectWebSocket()
        timer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            self?.fetchAll()
        }
    }

    func stopPolling() {
        timer?.invalidate()
        timer = nil
        wsTask?.cancel(with: .goingAway, reason: nil)
    }

    func fetchAll() {
        fetchHealth()
        fetchAgents()
        fetchActivityStats()
        fetchRecentActivity()
        fetchQuality()
    }

    // MARK: - Health

    func fetchHealth() {
        get("/health") { [weak self] (result: Result<HealthResponse, Error>) in
            DispatchQueue.main.async {
                switch result {
                case .success(let h):
                    self?.health = h
                    self?.isConnected = true
                    self?.lastError = nil
                case .failure(let e):
                    self?.isConnected = false
                    self?.lastError = e.localizedDescription
                }
            }
        }
    }

    // MARK: - Activity

    func fetchActivityStats() {
        get("/activity/stats") { [weak self] (result: Result<ActivityStatsResponse, Error>) in
            DispatchQueue.main.async {
                if case .success(let s) = result { self?.activityStats = s }
            }
        }
    }

    func fetchRecentActivity() {
        get("/activity?limit=100") { [weak self] (result: Result<ActivityResponse, Error>) in
            DispatchQueue.main.async {
                if case .success(let a) = result { self?.recentActivity = a.entries }
            }
        }
    }

    // MARK: - Agents

    func fetchAgents() {
        get("/agents") { [weak self] (result: Result<AgentsResponse, Error>) in
            DispatchQueue.main.async {
                if case .success(let a) = result {
                    self?.agents = a.agents
                    self?.buildNeuralGraph()
                    for agent in a.agents {
                        self?.checkAgentStatus(agent.name)
                    }
                }
            }
        }
    }

    func checkAgentStatus(_ name: String) {
        get("/agents/\(name)/status") { [weak self] (result: Result<AgentStatusResponse, Error>) in
            DispatchQueue.main.async {
                if case .success(let s) = result {
                    self?.agentStatuses[name] = s.status
                    if let idx = self?.neuralNodes.firstIndex(where: { $0.id == name }) {
                        self?.neuralNodes[idx].isActive = (s.status == "alive")
                    }
                }
            }
        }
    }

    // MARK: - Quality

    func fetchQuality() {
        get("/quality") { [weak self] (result: Result<QualityResponse, Error>) in
            DispatchQueue.main.async {
                if case .success(let q) = result { self?.quality = q }
            }
        }
    }

    // MARK: - Chat

    func sendChat(message: String) {
        let userMsg = ChatMessage(id: UUID(), role: .user, text: message, timestamp: Date())
        DispatchQueue.main.async {
            self.chatMessages.append(userMsg)
            self.isSending = true
        }

        let body: [String: Any] = ["message": message, "session_id": sessionId]
        post("/chat", body: body) { [weak self] (result: Result<ChatAPIResponse, Error>) in
            DispatchQueue.main.async {
                self?.isSending = false
                switch result {
                case .success(let response):
                    var text = response.response
                    if let delegations = response.delegations, !delegations.isEmpty {
                        text += "\n\n"
                        for d in delegations {
                            let icon = d.dispatched == true ? "✓" : "→"
                            text += "\(icon) \(d.manager): \(d.task)\n"
                        }
                    }
                    self?.chatMessages.append(ChatMessage(
                        id: UUID(), role: .assistant, text: text, timestamp: Date()
                    ))
                    // Pulse neural graph
                    self?.pulseNeuralActivity()
                case .failure(let error):
                    self?.chatMessages.append(ChatMessage(
                        id: UUID(), role: .error,
                        text: "Error: \(error.localizedDescription)", timestamp: Date()
                    ))
                }
            }
        }
    }

    // MARK: - Neural Graph

    func buildNeuralGraph() {
        guard !agents.isEmpty else { return }
        var nodes: [NeuralNode] = []
        var edges: [NeuralEdge] = []

        let cx: CGFloat = 200
        let cy: CGFloat = 200

        // King node at center
        nodes.append(NeuralNode(
            id: "king-ai", label: "King AI",
            x: cx, y: cy, radius: 14,
            category: .king
        ))

        // Memory node
        nodes.append(NeuralNode(
            id: "memory", label: "Memory",
            x: cx + 120, y: cy - 100, radius: 8,
            category: .memory
        ))
        edges.append(NeuralEdge(id: "king-memory", from: "king-ai", to: "memory", strength: 0.8))

        let managers = agents.filter { $0.role == "manager" }
        let workers = agents.filter { $0.role == "worker" }

        let managerAngleStep = managers.isEmpty ? 0 : (2.0 * .pi / CGFloat(managers.count))
        let managerRadius: CGFloat = 100

        for (i, mgr) in managers.enumerated() {
            let angle = CGFloat(i) * managerAngleStep - .pi / 2
            let mx = cx + cos(angle) * managerRadius
            let my = cy + sin(angle) * managerRadius

            nodes.append(NeuralNode(
                id: mgr.name, label: mgr.name.replacingOccurrences(of: "-manager", with: ""),
                x: mx, y: my, radius: 10, category: .manager
            ))
            edges.append(NeuralEdge(id: "king-\(mgr.name)", from: "king-ai", to: mgr.name, strength: 0.7))

            // Workers under this manager
            let myWorkers = workers.filter { $0.manager == mgr.name }
            let workerRadius: CGFloat = 55
            let workerAngleStep = myWorkers.isEmpty ? 0 : (.pi * 0.8 / max(CGFloat(myWorkers.count - 1), 1))
            let baseAngle = angle - .pi * 0.4

            for (j, worker) in myWorkers.enumerated() {
                let wa = baseAngle + CGFloat(j) * workerAngleStep
                let wx = mx + cos(wa) * workerRadius
                let wy = my + sin(wa) * workerRadius

                nodes.append(NeuralNode(
                    id: worker.name, label: worker.name,
                    x: wx, y: wy, radius: 5, category: .worker
                ))
                edges.append(NeuralEdge(id: "\(mgr.name)-\(worker.name)", from: mgr.name, to: worker.name, strength: 0.4))
            }
        }

        neuralNodes = nodes
        neuralEdges = edges
    }

    func pulseNeuralActivity() {
        // Briefly activate random edges to show neural activity
        for i in neuralEdges.indices {
            if Double.random(in: 0...1) > 0.5 {
                neuralEdges[i].isActive = true
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in
            for i in (self?.neuralEdges.indices ?? 0..<0) {
                self?.neuralEdges[i].isActive = false
            }
        }
    }

    // MARK: - WebSocket

    func connectWebSocket() {
        guard let url = URL(string: baseURL.replacingOccurrences(of: "http", with: "ws") + "/ws") else { return }
        wsTask = URLSession.shared.webSocketTask(with: url)
        wsTask?.resume()
        receiveWSMessage()
    }

    private func receiveWSMessage() {
        wsTask?.receive { [weak self] result in
            switch result {
            case .success(let message):
                if case .string(let text) = message, text != "pong" {
                    if let data = text.data(using: .utf8) {
                        if let entry = try? JSONDecoder().decode(ActivityEntry.self, from: data) {
                            DispatchQueue.main.async {
                                self?.thinkingEntries.append(entry)
                                if (self?.thinkingEntries.count ?? 0) > 500 {
                                    self?.thinkingEntries.removeFirst(100)
                                }
                                // Pulse neural graph on delegation events
                                if entry.type == "delegation" || entry.type == "llm_tool_calls" {
                                    self?.pulseNeuralActivity()
                                }
                            }
                        }
                    }
                }
                self?.receiveWSMessage()
            case .failure:
                DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                    self?.connectWebSocket()
                }
            }
        }
    }

    // MARK: - Networking

    private func get<T: Codable>(_ path: String, completion: @escaping (Result<T, Error>) -> Void) {
        guard let url = URL(string: baseURL + path) else { return }
        session.dataTask(with: url) { data, _, error in
            if let error { completion(.failure(error)); return }
            guard let data else { completion(.failure(URLError(.badServerResponse))); return }
            do {
                let decoded = try JSONDecoder().decode(T.self, from: data)
                completion(.success(decoded))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }

    private func post<T: Codable>(_ path: String, body: [String: Any], completion: @escaping (Result<T, Error>) -> Void) {
        guard let url = URL(string: baseURL + path) else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        session.dataTask(with: request) { data, _, error in
            if let error { completion(.failure(error)); return }
            guard let data else { completion(.failure(URLError(.badServerResponse))); return }
            do {
                let decoded = try JSONDecoder().decode(T.self, from: data)
                completion(.success(decoded))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }
}
