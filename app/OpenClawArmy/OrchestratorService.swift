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
    let event: String?

    enum CodingKeys: String, CodingKey {
        case ts, type, content, meta, event
        case sessionId = "session_id"
        case session = "session"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        ts = try container.decodeIfPresent(String.self, forKey: .ts)
        type = try container.decodeIfPresent(String.self, forKey: .type)
        content = try container.decodeIfPresent(String.self, forKey: .content)
        sessionId = try container.decodeIfPresent(String.self, forKey: .sessionId)
            ?? container.decodeIfPresent(String.self, forKey: .session)
        meta = try container.decodeIfPresent(ActivityMeta.self, forKey: .meta)
        event = try container.decodeIfPresent(String.self, forKey: .event)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encodeIfPresent(ts, forKey: .ts)
        try container.encodeIfPresent(type, forKey: .type)
        try container.encodeIfPresent(content, forKey: .content)
        try container.encodeIfPresent(sessionId, forKey: .sessionId)
        try container.encodeIfPresent(meta, forKey: .meta)
        try container.encodeIfPresent(event, forKey: .event)
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
    let pending: Bool?
    let status: String?

    enum CodingKeys: String, CodingKey {
        case response
        case result
        case sessionId = "session_id"
        case session = "session"
        case delegations
        case pending
        case status
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        response = (try container.decodeIfPresent(String.self, forKey: .response))
            ?? (try container.decodeIfPresent(String.self, forKey: .result))
            ?? ""
        sessionId = try container.decodeIfPresent(String.self, forKey: .sessionId)
            ?? container.decodeIfPresent(String.self, forKey: .session)
        delegations = try? container.decode([Delegation].self, forKey: .delegations)
        pending = try container.decodeIfPresent(Bool.self, forKey: .pending)
        status = try container.decodeIfPresent(String.self, forKey: .status)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(response, forKey: .response)
        try container.encodeIfPresent(sessionId, forKey: .sessionId)
        try container.encodeIfPresent(delegations, forKey: .delegations)
        try container.encodeIfPresent(pending, forKey: .pending)
        try container.encodeIfPresent(status, forKey: .status)
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
    var category: NodeCategory = .worker

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
    @Published var lastUpdated: Date?
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

    var currentSessionThinkingEntries: [ActivityEntry] {
        thinkingEntries.filter { entry in
            let sameSession = entry.sessionId == nil || entry.sessionId == sessionId
            guard sameSession else { return false }
            guard let type = entry.type?.lowercased(), !type.isEmpty else { return false }
            if type == "response" || type == "user_message" { return false }
            let text = entry.content?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            return !text.isEmpty
        }
    }

    private var thinkingEntryKeys: Set<String> = []

    // Neural graph
    @Published var neuralNodes: [NeuralNode] = []
    @Published var neuralEdges: [NeuralEdge] = []

    private var timer: Timer?
    private var wsTask: URLSessionWebSocketTask?
    private let session: URLSession

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 15
        // Keep resource timeout above worst-case orchestrator chat latency.
        config.timeoutIntervalForResource = 720
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
                    self?.lastUpdated = Date()
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
                // Reverse so newest entries appear first
                if case .success(let a) = result { self?.recentActivity = a.entries.reversed() }
            }
        }
    }

    func refreshThinkingFromSessionActivity(limit: Int = 120) {
        let targetSessionId = sessionId
        let safeLimit = max(20, min(limit, 300))
        let encodedSession = targetSessionId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? targetSessionId
        get("/activity/session/\(encodedSession)?limit=\(safeLimit)") { [weak self] (result: Result<ActivityResponse, Error>) in
            if case .success(let activity) = result {
                self?.mergeThinkingEntries(activity.entries, expectedSessionId: targetSessionId)
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
        executeChatRequest(body: body) { [weak self] result in
            self?.handleChatResult(result)
        }
    }

    private func executeChatRequest(
        body: [String: Any],
        didRetry: Bool = false,
        completion: @escaping (Result<ChatAPIResponse, Error>) -> Void
    ) {
        post("/chat", body: body) { [weak self] (result: Result<ChatAPIResponse, Error>) in
            if case .failure(let error) = result,
               !didRetry,
               let urlError = error as? URLError,
               urlError.code == .timedOut {
                self?.executeChatRequest(body: body, didRetry: true, completion: completion)
                return
            }
            completion(result)
        }
    }

    private func handleChatResult(_ result: Result<ChatAPIResponse, Error>) {
        switch result {
        case .success(let response):
            if let returnedSession = response.sessionId, !returnedSession.isEmpty {
                sessionId = returnedSession
            }

            var text = response.response.trimmingCharacters(in: .whitespacesAndNewlines)
            let shouldRecoverFromActivity = response.pending == true || text.isEmpty || looksLikeTimeoutResponse(text)

            if shouldRecoverFromActivity {
                recoverChatResponse(sessionId: sessionId) { [weak self] recovered in
                    guard let self else { return }
                    DispatchQueue.main.async {
                        self.isSending = false

                        if let recovered, !recovered.isEmpty {
                            self.chatMessages.append(ChatMessage(
                                id: UUID(), role: .assistant, text: recovered, timestamp: Date()
                            ))
                            self.pulseNeuralActivity()
                            return
                        }

                        if text.isEmpty {
                            text = "King AI is still processing this request. Please wait a few seconds and retry if needed."
                        }

                        if let delegations = response.delegations, !delegations.isEmpty {
                            text += "\n\n"
                            for d in delegations {
                                let icon = d.dispatched == true ? "✓" : "→"
                                text += "\(icon) \(d.manager): \(d.task)\n"
                            }
                        }

                        self.chatMessages.append(ChatMessage(
                            id: UUID(), role: .assistant, text: text, timestamp: Date()
                        ))
                    }
                }
                return
            }

            DispatchQueue.main.async {
                self.isSending = false

                if let delegations = response.delegations, !delegations.isEmpty {
                    text += "\n\n"
                    for d in delegations {
                        let icon = d.dispatched == true ? "✓" : "→"
                        text += "\(icon) \(d.manager): \(d.task)\n"
                    }
                }

                self.chatMessages.append(ChatMessage(
                    id: UUID(), role: .assistant, text: text, timestamp: Date()
                ))
                self.pulseNeuralActivity()
            }

        case .failure(let error):
            let description = (error as NSError).localizedDescription.lowercased()
            let isTimeoutFailure = (error as? URLError)?.code == .timedOut
                || description.contains("timed out")
                || description.contains("reasoning engine")

            if isTimeoutFailure {
                recoverChatResponse(sessionId: sessionId) { [weak self] recovered in
                    guard let self else { return }
                    DispatchQueue.main.async {
                        self.isSending = false
                        if let recovered, !recovered.isEmpty {
                            self.chatMessages.append(ChatMessage(
                                id: UUID(), role: .assistant, text: recovered, timestamp: Date()
                            ))
                            self.pulseNeuralActivity()
                        } else {
                            self.chatMessages.append(ChatMessage(
                                id: UUID(), role: .error,
                                text: self.userFacingChatError(error), timestamp: Date()
                            ))
                        }
                    }
                }
                return
            }

            DispatchQueue.main.async {
                self.isSending = false
                self.chatMessages.append(ChatMessage(
                    id: UUID(), role: .error,
                    text: self.userFacingChatError(error), timestamp: Date()
                ))
            }
        }

    }

    private func userFacingChatError(_ error: Error) -> String {
        if let urlError = error as? URLError, urlError.code == .timedOut {
            return "Request timed out while waiting for King AI. The response may still appear shortly from activity sync."
        }
        return "Error: \(error.localizedDescription)"
    }

    private func looksLikeTimeoutResponse(_ text: String) -> Bool {
        let normalized = text.lowercased()
        return normalized.contains("timed out")
            || normalized.contains("trouble connecting to my reasoning engine")
    }

    private func recoverChatResponse(
        sessionId: String,
        attemptsRemaining: Int = 90,
        delaySeconds: TimeInterval = 3,
        completion: @escaping (String?) -> Void
    ) {
        guard attemptsRemaining > 0 else {
            completion(nil)
            return
        }

        fetchLatestSessionResponse(sessionId: sessionId) { [weak self] text in
            if let text, !text.isEmpty {
                completion(text)
                return
            }

            guard attemptsRemaining > 1, let self else {
                completion(nil)
                return
            }

            DispatchQueue.global().asyncAfter(deadline: .now() + delaySeconds) {
                self.recoverChatResponse(
                    sessionId: sessionId,
                    attemptsRemaining: attemptsRemaining - 1,
                    delaySeconds: delaySeconds,
                    completion: completion
                )
            }
        }
    }

    private func fetchLatestSessionResponse(sessionId: String, completion: @escaping (String?) -> Void) {
        let encodedSession = sessionId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? sessionId
        get("/activity/session/\(encodedSession)?limit=120") { (result: Result<ActivityResponse, Error>) in
            switch result {
            case .success(let activity):
                self.mergeThinkingEntries(activity.entries, expectedSessionId: sessionId)
                let candidate = activity.entries.reversed().first(where: { entry in
                    let type = entry.type?.lowercased() ?? ""
                    let sameSession = entry.sessionId == nil || entry.sessionId == sessionId
                    let text = entry.content?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                    return type == "response" && sameSession && !text.isEmpty
                })
                completion(candidate?.content?.trimmingCharacters(in: .whitespacesAndNewlines))

            case .failure:
                completion(nil)
            }
        }
    }

    private func mergeThinkingEntries(_ entries: [ActivityEntry], expectedSessionId: String) {
        DispatchQueue.main.async {
            for entry in entries {
                let sameSession = entry.sessionId == nil || entry.sessionId == expectedSessionId
                guard sameSession else { continue }
                guard self.isThinkingEventEntry(entry) else { continue }
                self.appendThinkingEntryIfNeeded(entry)
                if entry.type == "delegation" || entry.type == "llm_tool_calls" {
                    self.pulseNeuralActivity()
                }
            }
        }
    }

    private func isThinkingEventEntry(_ entry: ActivityEntry) -> Bool {
        let type = (entry.type ?? "").lowercased()
        guard !type.isEmpty else { return false }
        if type == "response" || type == "user_message" { return false }
        let text = entry.content?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return !text.isEmpty
    }

    private func appendThinkingEntryIfNeeded(_ entry: ActivityEntry) {
        let key = thinkingEntryKey(for: entry)
        guard !key.isEmpty else { return }
        guard !thinkingEntryKeys.contains(key) else { return }

        thinkingEntryKeys.insert(key)
        thinkingEntries.append(entry)

        if thinkingEntries.count > 700 {
            thinkingEntries.removeFirst(200)
            rebuildThinkingEntryKeyIndex()
        }
    }

    private func thinkingEntryKey(for entry: ActivityEntry) -> String {
        let ts = entry.ts ?? ""
        let type = entry.type ?? ""
        let session = entry.sessionId ?? ""
        let content = entry.content?.prefix(280) ?? ""
        return "\(session)|\(ts)|\(type)|\(content)"
    }

    private func rebuildThinkingEntryKeyIndex() {
        thinkingEntryKeys = Set(thinkingEntries.map { thinkingEntryKey(for: $0) })
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
                                let isActivityEvent = entry.event == nil || entry.event == "activity"
                                let sameSession = entry.sessionId == nil || entry.sessionId == self?.sessionId

                                if isActivityEvent && sameSession {
                                    if let self, self.isThinkingEventEntry(entry) {
                                        self.appendThinkingEntryIfNeeded(entry)
                                    }
                                    if entry.type == "delegation" || entry.type == "llm_tool_calls" {
                                        self?.pulseNeuralActivity()
                                    }
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
        session.dataTask(with: url) { data, response, error in
            if let error { completion(.failure(error)); return }
            if let http = response as? HTTPURLResponse,
               !(200...299).contains(http.statusCode) {
                let body = data.flatMap { String(data: $0, encoding: .utf8) }
                    ?? HTTPURLResponse.localizedString(forStatusCode: http.statusCode)
                completion(.failure(NSError(
                    domain: "OrchestratorService",
                    code: http.statusCode,
                    userInfo: [NSLocalizedDescriptionKey: body]
                )))
                return
            }
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
        // Chat endpoint waits for LLM — override session-level timeout
        if path == "/chat" { request.timeoutInterval = 600 }
        session.dataTask(with: request) { data, response, error in
            if let error { completion(.failure(error)); return }
            if let http = response as? HTTPURLResponse,
               !(200...299).contains(http.statusCode) {
                let body = data.flatMap { String(data: $0, encoding: .utf8) }
                    ?? HTTPURLResponse.localizedString(forStatusCode: http.statusCode)
                completion(.failure(NSError(
                    domain: "OrchestratorService",
                    code: http.statusCode,
                    userInfo: [NSLocalizedDescriptionKey: body]
                )))
                return
            }
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
