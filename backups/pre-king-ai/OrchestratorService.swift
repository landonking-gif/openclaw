import Foundation
import Combine

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

struct ActivityStats: Codable {
    let total: Int
    let byCategory: [String: Int]
    let recentErrors: Int

    enum CodingKeys: String, CodingKey {
        case total
        case byCategory = "by_category"
        case recentErrors = "recent_errors"
    }
}

struct ActivityEntry: Codable, Identifiable {
    var id: String { "\(timestamp)-\(category)" }
    let timestamp: String
    let category: String
    let summary: String
    let manager: String?
    let error: String?
}

struct AgentInfo: Codable, Identifiable {
    var id: String { name }
    let name: String
    let port: Int
    let role: String?
    let model: String?
}

struct AgentStatus: Codable {
    let agent: String
    let status: String
    let port: Int
    let responseTimeMs: Double?

    enum CodingKeys: String, CodingKey {
        case agent, status, port
        case responseTimeMs = "response_time_ms"
    }
}

struct ChatResponse: Codable {
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

struct QualityReport: Codable {
    let compileOk: Bool
    let lineCount: Int
    let toolCount: Int
    let timestamp: String

    enum CodingKeys: String, CodingKey {
        case compileOk = "compile_ok"
        case lineCount = "line_count"
        case toolCount = "tool_count"
        case timestamp
    }
}

struct ScreenFrame: Codable {
    let timestamp: String?
    let ocrText: String?
    let changed: Bool?
    let resolution: String?
    let mousePosition: [Int]?

    enum CodingKeys: String, CodingKey {
        case timestamp
        case ocrText = "ocr_text"
        case changed
        case resolution
        case mousePosition = "mouse_position"
    }
}

class OrchestratorService: ObservableObject {
    static let shared = OrchestratorService()

    @Published var baseURL = "http://127.0.0.1:18830"
    @Published var isConnected = false
    @Published var health: HealthResponse?
    @Published var activityStats: ActivityStats?
    @Published var recentActivity: [ActivityEntry] = []
    @Published var agents: [AgentInfo] = []
    @Published var agentStatuses: [String: String] = [:]
    @Published var quality: QualityReport?
    @Published var lastError: String?

    private var timer: Timer?
    private let session: URLSession

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10
        config.timeoutIntervalForResource = 30
        self.session = URLSession(configuration: config)
    }

    func startPolling() {
        fetchAll()
        timer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            self?.fetchAll()
        }
    }

    func stopPolling() {
        timer?.invalidate()
        timer = nil
    }

    func fetchAll() {
        fetchHealth()
        fetchActivityStats()
        fetchRecentActivity()
        fetchAgents()
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
        get("/activity/stats") { [weak self] (result: Result<ActivityStats, Error>) in
            DispatchQueue.main.async {
                if case .success(let s) = result { self?.activityStats = s }
            }
        }
    }

    func fetchRecentActivity() {
        get("/activity?limit=30") { [weak self] (result: Result<[ActivityEntry], Error>) in
            DispatchQueue.main.async {
                if case .success(let a) = result { self?.recentActivity = a }
            }
        }
    }

    // MARK: - Agents

    func fetchAgents() {
        get("/agents") { [weak self] (result: Result<[AgentInfo], Error>) in
            DispatchQueue.main.async {
                if case .success(let a) = result { self?.agents = a }
            }
        }
    }

    func checkAgentStatus(_ name: String) {
        get("/agents/\(name)/status") { [weak self] (result: Result<AgentStatus, Error>) in
            DispatchQueue.main.async {
                if case .success(let s) = result {
                    self?.agentStatuses[name] = s.status
                }
            }
        }
    }

    // MARK: - Quality

    func fetchQuality() {
        get("/quality") { [weak self] (result: Result<QualityReport, Error>) in
            DispatchQueue.main.async {
                if case .success(let q) = result { self?.quality = q }
            }
        }
    }

    // MARK: - Chat

    func sendChat(message: String, sessionId: String = "dashboard", completion: @escaping (Result<ChatResponse, Error>) -> Void) {
        let body: [String: Any] = ["message": message, "session_id": sessionId]
        post("/chat", body: body, completion: completion)
    }

    // MARK: - Screen

    func getScreenFrame(completion: @escaping (Result<ScreenFrame, Error>) -> Void) {
        get("/screen/frame", completion: completion)
    }

    // MARK: - Networking

    private func get<T: Codable>(_ path: String, completion: @escaping (Result<T, Error>) -> Void) {
        guard let url = URL(string: baseURL + path) else { return }
        session.dataTask(with: url) { data, response, error in
            if let error = error { completion(.failure(error)); return }
            guard let data = data else { completion(.failure(URLError(.badServerResponse))); return }
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
        session.dataTask(with: request) { data, response, error in
            if let error = error { completion(.failure(error)); return }
            guard let data = data else { completion(.failure(URLError(.badServerResponse))); return }
            do {
                let decoded = try JSONDecoder().decode(T.self, from: data)
                completion(.success(decoded))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }
}
