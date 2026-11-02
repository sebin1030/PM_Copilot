import { FormEvent, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { api, Connection } from "./api";
import { authEnabled, supabase } from "./supabase";

const names: Record<string, string> = { openai: "GPT · OpenAI", anthropic: "Claude · Anthropic", gemini: "Gemini · Google" };
function DocumentView({ content: p }: { content: any }) {
  return <article className="prd"><h2>{p.title}</h2><p>{p.summary}</p><h3>문제 정의</h3><p>{p.problem}</p>
    {[["목표 사용자", p.targetUsers], ["목표", p.goals]].map(([title, items]) => <section key={title}><h3>{title}</h3><ul>{items.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></section>)}
    <h3>핵심 기능</h3>{p.features.map((f: any) => <section key={f.id}><h4>{f.id} · {f.name} <small>{f.priority}</small></h4><p>{f.description}</p></section>)}
    <h3>요구사항</h3>{p.requirements.map((r: any) => <section key={r.id}><h4>{r.id} · {r.title}</h4><p>{r.description}</p><strong>수용 기준</strong><ul>{r.acceptanceCriteria.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></section>)}
    {[["성공 지표", p.successMetrics], ["제외 범위와 이유", p.outOfScope], ["미검증 가정", p.assumptions], ["확인할 사항", p.questions]].map(([title, items]) => <section key={title}><h3>{title}</h3><ul>{items.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>{!items.length && <p className="muted">등록된 항목 없음</p>}</section>)}
  </article>;
}
function Login({ onSession }: { onSession: (session: Session) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!supabase) return;
    setBusy(true); setMessage("");
    const result = mode === "signin"
      ? await supabase.auth.signInWithPassword({ email, password })
      : await supabase.auth.signUp({ email, password });
    setBusy(false);
    if (result.error) { setMessage(result.error.message); return; }
    if (result.data.session) onSession(result.data.session);
    else setMessage("확인 이메일을 보냈습니다. 메일의 링크를 열어 계정을 활성화해 주세요.");
  }
  return <main className="login"><section><strong>PM Copilot</strong><h1>{mode === "signin" ? "로그인" : "계정 만들기"}</h1><p>프로젝트와 승인 결과는 계정별로 저장됩니다.</p><form className="stack" onSubmit={submit}><input value={email} onChange={e => setEmail(e.target.value)} type="email" autoComplete="email" placeholder="이메일" required /><input value={password} onChange={e => setPassword(e.target.value)} type="password" autoComplete={mode === "signin" ? "current-password" : "new-password"} minLength={6} placeholder="비밀번호 (6자 이상)" required /><button disabled={busy}>{busy ? "처리 중…" : mode === "signin" ? "로그인" : "계정 만들기"}</button></form>{message && <p className="notice">{message}</p>}<button className="link" onClick={() => setMode(mode === "signin" ? "signup" : "signin")}>{mode === "signin" ? "처음이신가요? 계정 만들기" : "이미 계정이 있나요? 로그인"}</button></section></main>;
}
export default function App() {
  const [projects, setProjects] = useState<any[]>([]);
  const [project, setProject] = useState<any>(null);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selected, setSelected] = useState("");
  const [settings, setSettings] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showApproved, setShowApproved] = useState(false);
  const [userSession, setUserSession] = useState<Session | null>(null);
  const connection = connections.find(c => c.provider === selected);
  const refreshProjects = () => api.projects().then(d => setProjects(d.projects));
  function updateConnections(data: any) {
    setConnections(data.connections);
    setSelected(current => data.connections.some((c: Connection) => c.provider === current) ? current : data.connections[0]?.provider || "");
  }
  useEffect(() => {
    if (authEnabled && supabase) {
      supabase.auth.getSession().then(({ data }) => setUserSession(data.session));
      const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => setUserSession(session));
      return () => listener.subscription.unsubscribe();
    }
  }, []);
  useEffect(() => {
    if (authEnabled && !userSession) return;
    Promise.all([api.connections(), api.projects()]).then(([c, p]) => { updateConnections(c); setProjects(p.projects); setSettings(!c.connections.length); }).catch(e => setError(e.message));
  }, [userSession]);
  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  }
  function createProject(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const form = new FormData(e.currentTarget);
    run(async () => { const d = await api.createProject({ name: form.get("name"), description: form.get("description"), problem: form.get("problem"), target_users: String(form.get("targetUsers") || "").split(",").map(x => x.trim()).filter(Boolean), platform: "Web" }); setProject(d.project); setShowApproved(false); await refreshProjects(); });
  }
  function connect(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const form = e.currentTarget; const values = new FormData(form);
    const body = { provider: values.get("provider"), model: String(values.get("model")).trim(), api_key: String(values.get("api_key")).trim() };
    (form.elements.namedItem("api_key") as HTMLInputElement).value = "";
    run(async () => { updateConnections(await api.connect(body)); setNotice("인증 및 모델 조회 완료. 문서 생성 지원 여부는 실제 생성 시 확인됩니다."); });
  }
  const draft = project?.drafts?.prd;
  const approved = project?.documents?.prd;
  const prd = showApproved ? approved : draft || approved;
  if (authEnabled && !userSession) return <Login onSession={setUserSession} />;
  return <main>
    <header><div><strong>PM Copilot</strong><span>근거에서 기획으로</span></div><div className="header-actions">{userSession && <><span className="signed-in">{userSession.user.email}</span><button className="secondary" onClick={() => supabase?.auth.signOut()} disabled={busy}>로그아웃</button></>}<button className="secondary" onClick={() => setSettings(!settings)} disabled={busy}>AI 연결 설정 · {connections.length}</button></div></header>
    {error && <div role="alert" className="error">{error}</div>}{notice && <div role="status" className="notice">{notice}</div>}
    {settings && <section className="settings"><h2>내 API 연결</h2><p>키는 서버 메모리에만 보관하며 8시간 후 또는 서버 재시작 시 삭제됩니다. 프로젝트 자료는 선택한 제공자로 전송됩니다.</p>
      <form onSubmit={connect} className="connection-form"><label>제공자<select name="provider">{Object.entries(names).map(([id, name]) => <option value={id} key={id}>{name}</option>)}</select></label><label>모델 ID<input name="model" required placeholder="제공자 콘솔의 정확한 모델 ID" pattern="[A-Za-z0-9_.:\-]+" /></label><label>API 키<input name="api_key" type="password" autoComplete="off" required placeholder="API 키 입력" /></label><button disabled={busy}>연결 확인</button></form>
      <div className="connection-list">{connections.map(c => <div key={c.provider}><strong>{names[c.provider]}</strong> · {c.model} <button disabled={busy} className="secondary" onClick={() => run(async () => updateConnections(await api.disconnect(c.provider)))}>연결 해제</button></div>)}</div>
      <p className="muted">연결 확인은 모델 조회만 수행합니다. 대화·문서 생성에는 제공자의 API 이용 요금이 발생할 수 있습니다.</p>
    </section>}
    <div className="layout"><aside><h2>프로젝트</h2>{projects.map(item => <button disabled={busy} className="project" key={item.projectId} onClick={() => run(async () => { setProject((await api.project(item.projectId)).project); setShowApproved(false); })}><b>{item.name}</b><small>{item.prdStatus || "시작 전"}</small></button>)}
      <details open={!project}><summary>새 프로젝트</summary><form onSubmit={createProject} className="stack"><input aria-label="프로젝트명" name="name" placeholder="프로젝트명" required /><textarea aria-label="서비스 설명" name="description" placeholder="서비스 설명" /><textarea aria-label="해결하려는 문제" name="problem" placeholder="해결하려는 문제" /><input aria-label="대상 사용자" name="targetUsers" placeholder="대상 사용자, 쉼표로 구분" /><button disabled={busy}>생성</button></form></details>
    </aside><section className="workspace">{!project ? <div className="empty"><h1>아이디어를 검토 가능한 기획으로</h1><p>AI를 연결하고 프로젝트를 만들어 시작하세요.</p></div> : <>
      <div className="title"><div><h1>{project.projectInfo.name}</h1><p>{project.projectInfo.description}</p></div><div className="stack"><select aria-label="사용할 AI" disabled={busy} value={selected} onChange={e => setSelected(e.target.value)}><option value="" disabled>AI 연결 필요</option>{connections.map(c => <option key={c.provider} value={c.provider}>{names[c.provider]} · {c.model}</option>)}</select><button disabled={busy || !connection} onClick={() => run(async () => { setProject((await api.generatePrd(project.projectId, connection!)).project); setShowApproved(false); })}>{busy ? "처리 중…" : "PRD 초안 생성"}</button></div></div>
      <div className="panels"><div className="chat"><div className="toolbar"><h2>기획 대화</h2></div><div className="messages">{!project.conversations.length && <p className="muted">문제, 대상 사용자, 필요한 기능을 이야기해 주세요.</p>}{project.conversations.map((x: any, i: number) => <div key={i} className={`message ${x.role}`}>{x.content}</div>)}</div><form className="composer" onSubmit={e => { e.preventDefault(); if (connection && message.trim()) run(async () => { setProject((await api.chat(project.projectId, message, connection)).project); setMessage(""); }); }}><textarea aria-label="대화 입력" value={message} onChange={e => setMessage(e.target.value)} placeholder="서비스 아이디어를 입력하세요" /><button disabled={busy || !connection || !message.trim()}>전송</button></form></div>
      <div className="document"><div className="toolbar"><h2>PRD 검토</h2>{draft && approved && <button className="secondary" onClick={() => setShowApproved(!showApproved)}>{showApproved ? "새 초안 보기" : "기존 확정본 보기"}</button>}</div>{!prd ? <p className="muted">대화를 진행한 뒤 초안을 생성하세요.</p> : <><div className="badge">{prd.status === "APPROVED" ? "승인된 문서" : prd.status === "REJECTED" ? "반려된 초안" : "검토가 필요한 초안"}</div><DocumentView content={prd.content} />{prd.review && <div className="review"><strong>구조 점검</strong><ul>{prd.review.warnings.map((w: string, i: number) => <li key={i}>{w}</li>)}</ul><small>{prd.review.note}</small></div>}<div className="actions">{prd.status === "NEEDS_APPROVAL" && ["APPROVED", "REJECTED"].map(status => <button key={status} className={status === "REJECTED" ? "secondary" : ""} disabled={busy} onClick={() => run(async () => { setProject((await api.approvePrd(project.projectId, status, prd.documentId)).project); await refreshProjects(); })}>{status === "APPROVED" ? "승인·확정" : "반려"}</button>)}<a href={api.downloadUrl(project.projectId, prd === draft)}>Markdown 다운로드</a></div></>}</div></div>
    </>}</section></div>
  </main>;
}
