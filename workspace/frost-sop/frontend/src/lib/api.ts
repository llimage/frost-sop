const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * FROST-SOP V9.1: 标准化 API 错误
 * 
 * 错误码格式: { error_code, error_id, message, path }
 */
export class APIError extends Error {
  status: number;
  errorCode: string;
  errorId: string | null;
  path: string;

  constructor(
    message: string,
    status: number,
    errorCode: string = "UNKNOWN_ERROR",
    errorId: string | null = null,
    path: string = ""
  ) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.errorCode = errorCode;
    this.errorId = errorId;
    this.path = path;
  }

  toString() {
    return `[APIError ${this.status}] ${this.errorCode}: ${this.message}`;
  }
}

/**
 * 全局 API 请求拦截器
 * 统一处理: 超时、错误解析、日志记录
 */
async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  
  // 默认超时 30s
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  try {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...options,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      // 解析结构化错误响应
      let errorData: any = {};
      try {
        errorData = await res.json();
      } catch {
        errorData = { message: await res.text() };
      }

      throw new APIError(
        errorData.message || `HTTP ${res.status}`,
        res.status,
        errorData.error_code || `HTTP_${res.status}`,
        errorData.error_id || null,
        errorData.path || path
      );
    }

    return res.json();
  } catch (e) {
    clearTimeout(timeoutId);

    if (e instanceof APIError) {
      throw e;
    }

    // 网络错误 / 超时
    if (e instanceof Error) {
      if (e.name === "AbortError") {
        throw new APIError(
          "请求超时，请检查网络连接",
          0,
          "REQUEST_TIMEOUT",
          null,
          path
        );
      }
      throw new APIError(
        `网络错误: ${e.message}`,
        0,
        "NETWORK_ERROR",
        null,
        path
      );
    }

    throw e;
  }
}

// ── Projects ──
export async function getProjects() {
  return fetchAPI<any[]>("/api/projects");
}

export async function getProject(id: string) {
  if (!id || id === "undefined") {
    throw new APIError("项目ID无效", 400, "PROJECT_ID_INVALID");
  }
  return fetchAPI<any>(`/api/projects/${id}`);
}

// ── Tasks ──
export async function createTask(description: string, sopId: string, projectId: string) {
  if (!description.trim()) {
    throw new APIError("任务描述不能为空", 400, "TASK_DESCRIPTION_EMPTY");
  }
  return fetchAPI<any>("/api/tasks", {
    method: "POST",
    body: JSON.stringify({ description, sop_id: sopId, project_id: projectId }),
  });
}

export async function getTasks(limit = 20) {
  return fetchAPI<any[]>(`/api/tasks?limit=${limit}`);
}

export async function getTaskStages(taskId: string) {
  if (!taskId || taskId === "undefined") {
    throw new APIError("任务ID无效", 400, "TASK_ID_INVALID");
  }
  return fetchAPI<any[]>(`/api/tasks/${taskId}/stages`);
}

// ── Costs ──
export async function getCosts() {
  return fetchAPI<any>("/api/costs");
}

// ── Agents ──
export async function getAgents() {
  return fetchAPI<any[]>("/api/agents");
}

// ── Chat ──
export async function sendChat(message: string) {
  if (!message.trim()) {
    throw new APIError("消息不能为空", 400, "CHAT_MESSAGE_EMPTY");
  }
  return fetchAPI<any>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

// ── Skills ──
export async function getSkills() {
  return fetchAPI<any[]>("/api/skills");
}

// ── Schedule ──
export async function getSchedules() {
  return fetchAPI<any[]>("/api/schedule");
}

export async function createSchedule(data: {
  title: string;
  start_time: string;
  end_time: string;
  description?: string;
}) {
  if (!data.title.trim()) {
    throw new APIError("日程标题不能为空", 400, "SCHEDULE_TITLE_EMPTY");
  }
  return fetchAPI<any>("/api/schedule", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Panels (V5.0) ──
export async function fetchPanel(taskId: string, sopId?: string) {
  if (!taskId) {
    throw new APIError("任务ID不能为空", 400, "PANEL_TASK_ID_EMPTY");
  }
  return fetchAPI<any>("/api/panels/generate", {
    method: "POST",
    body: JSON.stringify({ task_id: taskId, sop_id: sopId }),
  });
}

// ── Decisions ──
export async function submitDecision(data: {
  decision_id: string;
  decision: string;
  reason?: string;
  human_agent_id?: string;
}) {
  if (!data.decision_id) {
    throw new APIError("决策ID不能为空", 400, "DECISION_ID_EMPTY");
  }
  return fetchAPI<any>("/api/decisions/submit", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getDecision(decisionId: string) {
  return fetchAPI<any>(`/api/decisions/${decisionId}`);
}

export async function getPendingDecisions(taskId?: string) {
  const query = taskId ? `?task_id=${taskId}` : "";
  return fetchAPI<any[]>(`/api/decisions${query}`);
}

// ── V9.1: 超时检查 ──
export async function checkDecisionTimeout() {
  return fetchAPI<any>("/api/decisions/check-timeout", {
    method: "POST",
  });
}

// 导出错误类供外部使用
export { APIError };
