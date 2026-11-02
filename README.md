# PM Copilot MVP

대화로 프로젝트 정보를 정리하고 PRD 초안을 생성·검토·승인·다운로드하는 웹앱이다. Supabase를 설정하면 이메일 로그인과 사용자별 프로젝트 저장을 사용한다. 설정하지 않으면 기존 로컬 단일 사용자 모드로 실행된다.

## 실행

프로젝트 루트에서:

```bash
python3 -m venv .venv  # 최초 1회
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

별도 터미널에서:

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

[로컬 앱](http://127.0.0.1:5173)을 열고 ‘AI 연결 설정’에서 제공자, 정확한 모델 ID, API 키를 입력한다. GPT(OpenAI), Claude(Anthropic), Gemini(Google) 중 하나만 연결해도 된다. 모델 조회로 인증·접근 가능 여부를 확인하며 실제 문서 생성 지원 여부는 생성 요청에서 확인한다. API 키와 모델 ID는 각 제공자 콘솔에서 확인한다.

키는 브라우저 저장소나 프로젝트 파일에 저장하지 않고 브라우저별 세션에 연결된 서버 메모리에만 보관한다. 최초 세션 생성 후 8시간 또는 서버 재시작 시 만료된다. 연결 해제 시 해당 키를 제거한다. 기존 `.env` 키는 자동으로 사용하지 않으며 설정 화면에서 연결해야 한다. 단일 서버 프로세스로 실행한다.

## Supabase 로그인·저장 설정

1. Supabase에서 새 프로젝트를 만들고 **Authentication > Providers > Email**을 활성화한다.
2. SQL Editor에서 [초기 스키마](supabase/migrations/20261102_projects.sql)를 실행한다. 이 스키마는 RLS를 켜고, 로그인한 사용자가 자신의 프로젝트 행만 읽고 쓰게 한다.
3. [`.env.example`](.env.example)을 복사해 `.env`에 넣고 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`를 채운다. `VITE_` 값은 프런트엔드에 노출되므로 **Publishable key만** 사용한다. secret/service-role key는 입력하거나 배포하지 않는다.
4. 개발 서버를 다시 시작한다. 로그인 화면이 보이면 계정을 만든 뒤 확인 이메일을 열어 활성화한다.
5. 배포 주소를 `PM_COPILOT_ALLOWED_ORIGINS`와 Supabase Authentication의 Redirect URLs에 등록한다.

백엔드는 요청의 Bearer 토큰을 Supabase Auth에 확인하고, 프로젝트 저장 요청은 그 토큰으로 Supabase REST API에 전달한다. 따라서 서버가 service-role 키를 보관하거나 RLS를 우회하지 않는다.

프런트엔드는 같은 출처의 `/api`를 사용하고 개발 서버가 8000 포트로 전달한다. 공개 배포 전 사용자별 AI 키 암호화 저장, HTTPS, 비밀번호 재설정·이메일 템플릿, 비용 제한, 공유 세션 저장소를 구현해야 한다.

## 이번 구현 범위

- 프로젝트 생성·JSON 저장·대화 맥락 유지
- Supabase 이메일 로그인, 사용자별 프로젝트 저장 및 RLS 소유권 분리
- 세 제공자 연결 확인·선택·연결 해제, 명시적 모델 ID 입력
- 제공자별 대화·구조화 PRD 생성 어댑터, 응답 형식 검증
- PRD 문서형 미리보기 및 필수 목록·수용 기준의 기본 구조 점검
- 초안과 확정본 분리, 승인 시에만 기능·요구사항 확정
- 재생성·반려 시 기존 승인본 보존, 이전 초안·승인본 이력 저장
- 오래된 초안 승인 및 동시 수정의 덮어쓰기 방지(단일 프로세스)
- 초안·확정본 Markdown 다운로드
- 기존 PDF 업로드 API·텍스트 추출 유지; 추출 자료를 생성 맥락에 전달

구조 점검은 AI 내용의 사실성이나 예외 완전성을 보장하지 않는다. 미결정 사항은 사용자가 검토해야 한다. 사용한 제공자와 모델은 문서·대화에 기록하며 자동 제공자 전환은 아직 하지 않는다.

## 남은 기획 범위

웹 검색·근거 검토 및 PRD 연결, Decision Log UI, 정교한 문서 품질 검수, 사용량·예산 제한, 작업별 모델 선택·자동 전환, PDF 업로드 UI, 배포용 AI 키 암호화 관리가 남아 있다. Figma 와이어프레임과 추가 문서 유형은 P1 단계다. 상세 내용은 `docs`의 프로젝트 기획서를 따른다.

## 검증

```bash
.venv/bin/python -m unittest discover -s backend/tests -v
cd frontend
npm run typecheck
npm run build
```

자동 테스트는 외부 제공자 응답을 대체하여 초안·승인·반려·세션 격리·만료·동시 수정·이전 저장 형식·응답 변환·오류의 키 노출 방지를 확인한다. 실제 유료 API 호출은 수행하지 않았으므로 세 제공자의 실제 계정·모델을 이용한 종단 검증은 남아 있다.

## API 구현 참고

- [OpenAI 구조화 출력](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
- [Claude Messages API](https://platform.claude.com/docs/en/api/messages/create)
- [Gemini generateContent](https://ai.google.dev/api/generate-content)
