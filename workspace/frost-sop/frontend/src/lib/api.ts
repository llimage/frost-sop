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
