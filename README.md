# PM Copilot MVP

대화로 프로젝트 정보를 정리하고, Project JSON을 기준으로 PRD를 생성·승인·다운로드하는 로컬 웹앱이다.

## 실행

### Backend

터미널 1에서 프로젝트 루트로 이동한 뒤 실행한다.

```bash
python3 -m venv .venv  # 최초 1회만
.venv/bin/python -m pip install -r backend/requirements.txt  # 최초 1회 또는 의존성 변경 시
.venv/bin/uvicorn backend.app.main:app --reload --port 8000
```

현재 프로젝트에는 `.env`가 있으므로 별도 복사 없이 사용한다. `.env`의 `OPENAI_API_KEY`에 개인 API 키를 입력한다. 키는 브라우저나 프로젝트 JSON에 저장되지 않는다.

8000 포트가 이미 사용 중이면 기존 백엔드를 종료한다.

```bash
lsof -ti :8000 | xargs kill
```

### Frontend

터미널 2에서 실행한다.

```bash
cd frontend
npm install  # 최초 1회 또는 의존성 변경 시
npm run dev
```

브라우저에서 `http://localhost:5173`을 연다.

## MVP 범위

- 프로젝트 생성 및 JSON 저장
- 프로젝트별 대화 기록
- 모델 선택
- PRD JSON 생성
- PRD 승인
- Markdown 다운로드
- PDF 업로드 및 텍스트 추출

자료 조사·데이터 분석, IA, 화면정의서, API, WBS, 일정표는 후속 모듈이다.
