const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API ${res.status}: ${error}`);
  }
  return res.json();
}

// Projects
export async function getProjects() {
  return fetchAPI<any[]>("/api/projects");
}

export async function getProject(id: string) {
  return fetchAPI<any>(`/api/projects/${id}`);
}

// Tasks
export async function createTask(description: string, sopId: string, projectId: string) {
  return fetchAPI<any>("/api/tasks", {
    method: "POST",
    body: JSON.stringify({ description, sop_id: sopId, project_id: projectId }),
  });
}

export async function getTasks(limit = 20) {
  return fetchAPI<any[]>(`/api/tasks?limit=${limit}`);
}

export async function getTaskStages(taskId: string) {
  return fetchAPI<any[]>(`/api/tasks/${taskId}/stages`);
}

// Costs
export async function getCosts() {
  return fetchAPI<any>("/api/costs");
}

// Agents
export async function getAgents() {
  return fetchAPI<any[]>("/api/agents");
}

// Chat
export async function sendChat(message: string) {
  return fetchAPI<any>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

// Skills
export async function getSkills() {
  return fetchAPI<any[]>("/api/skills");
}

// Schedule
export async function getSchedules() {
  return fetchAPI<any[]>("/api/schedule");
}

export async function createSchedule(data: {
  title: string;
  start_time: string;
  end_time: string;
  description?: string;
}) {
  return fetchAPI<any>("/api/schedule", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Panels (V5.0) ──────────────────────────────
export async function fetchPanel(taskId: string, sopId?: string) {
  return fetchAPI<any>("/api/panels/generate", {
    method: "POST",
    body: JSON.stringify({ task_id: taskId, sop_id: sopId }),
  });
}

export async function submitDecision(data: {
  decision_id: string;
  decision: string;
  reason?: string;
  human_agent_id?: string;
}) {
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
