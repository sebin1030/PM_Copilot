import { supabase } from "./supabase";

const API = "/api";

async function request(path: string, options?: RequestInit) {
  const token = supabase ? (await supabase.auth.getSession()).data.session?.access_token : undefined;
  const response = await fetch(`${API}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(options?.headers || {}) } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "입력값을 확인해 주세요.");
  return data;
}
export type Connection = { provider: string; model: string };
export const api = {
  connections: () => request("/connections"),
  connect: (body: object) => request("/connections", { method: "POST", body: JSON.stringify(body) }),
  disconnect: (provider: string) => request(`/connections/${provider}`, { method: "DELETE" }),
  projects: () => request("/projects"),
  project: (id: string) => request(`/projects/${id}`),
  createProject: (body: object) => request("/projects", { method: "POST", body: JSON.stringify(body) }),
  chat: (id: string, message: string, connection: Connection) => request(`/projects/${id}/chat`, { method: "POST", body: JSON.stringify({ message, ...connection }) }),
  generatePrd: (id: string, connection: Connection) => request(`/projects/${id}/documents/prd/generate`, { method: "POST", body: JSON.stringify(connection) }),
  approvePrd: (id: string, status: string, document_id: string) => request(`/projects/${id}/documents/prd/approval`, { method: "POST", body: JSON.stringify({ status, document_id }) }),
  downloadUrl: (id: string, draft = false) => `${API}/projects/${id}/documents/prd/download?draft=${draft}`,
};
