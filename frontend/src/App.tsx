import { FormEvent, useEffect, useState } from "react";
import { api } from "./api";

type ProjectSummary = { projectId: string; name: string; prdStatus?: string };
type Model = { id: string; label: string; use: string };

export default function App() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [project, setProject] = useState<any>(null);
  const [models, setModels] = useState<Model[]>([]);
  const [chatModel, setChatModel] = useState("gpt-5.6-luna");
  const [documentModel, setDocumentModel] = useState("gpt-5.6-terra");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [apiReady, setApiReady] = useState(false);

  const refreshProjects = () => api.projects().then((data) => setProjects(data.projects));

  useEffect(() => {
    Promise.all([api.health(), api.models(), api.projects()]).then(([health, modelData, projectData]) => {
      setApiReady(health.apiKeyConfigured);
      setModels(modelData.models);
      setChatModel(modelData.defaults.chat);
      setDocumentModel(modelData.defaults.document);
      setProjects(projectData.projects);
    }).catch((e) => setError(e.message));
  }, []);

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      const data = await api.createProject({ name: form.get("name"), description: form.get("description"), problem: form.get("problem"), target_users: String(form.get("targetUsers") || "").split(",").map((v) => v.trim()).filter(Boolean), platform: "Web", purpose: form.get("purpose") });
      setProject(data.project); await refreshProjects();
    } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault(); if (!message.trim() || !project) return;
    setBusy(true); setError("");
    try { const data = await api.chat(project.projectId, message, chatModel); setProject(data.project); setMessage(""); }
    catch (e: any) { setError(e.message); } finally { setBusy(false); }
  }

  async function generatePrd() {
    setBusy(true); setError("");
    try { const data = await api.generatePrd(project.projectId, documentModel); setProject(data.project); }
    catch (e: any) { setError(e.message); } finally { setBusy(false); }
  }

  async function approve(status: string) {
    setBusy(true); setError("");
    try { const data = await api.approvePrd(project.projectId, status); setProject(data.project); await refreshProjects(); }
    catch (e: any) { setError(e.message); } finally { setBusy(false); }
  }

  const prd = project?.documents?.prd;
  return <main>
    <header><div><strong>PM Copilot</strong><span>Local MVP</span></div><div className={apiReady ? "status ok" : "status"}>{apiReady ? "API 연결 준비됨" : "API 키 필요"}</div></header>
    {error && <div className="error">{error}</div>}
    <div className="layout">
      <aside>
        <h2>프로젝트</h2>
        {projects.map((item) => <button className="project" key={item.projectId} onClick={() => api.project(item.projectId).then((data) => setProject(data.project))}><b>{item.name}</b><small>{item.prdStatus || "PRD 없음"}</small></button>)}
        <details open={!project}><summary>새 프로젝트</summary><form onSubmit={createProject} className="stack"><input name="name" placeholder="프로젝트명" required /><textarea name="description" placeholder="서비스 설명" /><textarea name="problem" placeholder="해결하려는 문제" /><input name="targetUsers" placeholder="대상 사용자, 쉼표로 구분" /><textarea name="purpose" placeholder="프로젝트 목적" /><button disabled={busy}>생성</button></form></details>
      </aside>
      <section className="workspace">
        {!project ? <div className="empty"><h1>프로젝트를 선택하거나 생성하세요.</h1><p>아이디어를 대화로 정리하고 PRD로 만들 수 있습니다.</p></div> : <>
          <div className="title"><div><h1>{project.projectInfo.name}</h1><p>{project.projectInfo.description || "설명이 없습니다."}</p></div><button onClick={generatePrd} disabled={busy || !apiReady}>PRD 생성</button></div>
          <div className="panels">
            <div className="chat">
              <div className="toolbar"><h2>기획 대화</h2><select value={chatModel} onChange={(e) => setChatModel(e.target.value)}>{models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}</select></div>
              <div className="messages">{project.conversations.length === 0 && <p className="muted">서비스 아이디어와 필요한 기능을 입력하세요.</p>}{project.conversations.map((item: any, index: number) => <div key={index} className={`message ${item.role}`}>{item.content}</div>)}</div>
              <form onSubmit={sendMessage} className="composer"><textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="예: 취준생을 위한 프로젝트 관리 서비스를 만들고 싶어" /><button disabled={busy || !apiReady}>전송</button></form>
            </div>
            <div className="document">
              <div className="toolbar"><h2>PRD</h2><select value={documentModel} onChange={(e) => setDocumentModel(e.target.value)}>{models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}</select></div>
              {!prd ? <p className="muted">대화를 충분히 진행한 뒤 PRD를 생성하세요.</p> : <><div className="badge">{prd.status}</div><pre>{JSON.stringify(prd.content, null, 2)}</pre><div className="actions"><button onClick={() => approve("APPROVED")} disabled={busy}>승인</button><button className="secondary" onClick={() => approve("REJECTED")} disabled={busy}>반려</button><a href={api.downloadUrl(project.projectId)}>Markdown 다운로드</a></div></>}
            </div>
          </div>
        </>}
      </section>
    </div>
  </main>;
}
