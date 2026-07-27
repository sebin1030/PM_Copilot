const API = "http://localhost:8000/api";

async function request(path: string, options?: RequestInit) {
  const response = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json", ...(options?.headers || {}) }, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "요청에 실패했습니다.");
  return data;
}

export const api = {
  health: () => request("/health"),
  models: () => request("/models"),
  projects: () => request("/projects"),
  project: (id: string) => request(`/projects/${id}`),
  createProject: (body: object) => request("/projects", { method: "POST", body: JSON.stringify(body) }),
  chat: (id: string, message: string, model: string) => request(`/projects/${id}/chat`, { method: "POST", body: JSON.stringify({ message, model }) }),
  generatePrd: (id: string, model: string) => request(`/projects/${id}/documents/prd/generate`, { method: "POST", body: JSON.stringify({ model }) }),
  approvePrd: (id: string, status: string) => request(`/projects/${id}/documents/prd/approval`, { method: "POST", body: JSON.stringify({ status }) }),
  downloadUrl: (id: string) => `${API}/projects/${id}/documents/prd/download`,
};
