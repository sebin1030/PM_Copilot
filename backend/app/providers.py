"""Provider adapters. Credentials never enter project data or model prompts."""
import json
import re
import httpx


class ProviderError(Exception):
    pass


BASES = {"openai": "https://api.openai.com/v1", "anthropic": "https://api.anthropic.com/v1", "gemini": "https://generativelanguage.googleapis.com/v1beta"}


def headers(provider, key):
    if provider == "anthropic":
        return {"x-api-key": key, "anthropic-version": "2023-06-01"}
    if provider == "gemini":
        return {"x-goog-api-key": key}
    return {"Authorization": f"Bearer {key}"}


def call(provider, key, path, body=None):
    try:
        with httpx.Client(timeout=90, follow_redirects=False) as client:
            response = client.request("POST" if body is not None else "GET", BASES[provider] + path, headers=headers(provider, key), json=body)
        if response.status_code >= 400:
            messages = {401: "API 키를 확인해 주세요.", 403: "해당 모델에 접근할 권한이 없습니다.", 404: "모델 ID를 확인해 주세요.", 429: "사용 한도 또는 요청 제한을 확인해 주세요."}
            raise ProviderError(messages.get(response.status_code, "제공자가 요청을 처리하지 못했습니다. 모델 지원 기능을 확인해 주세요."))
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise ProviderError("AI 제공자 연결에 실패했습니다. 잠시 후 다시 시도해 주세요.") from None


def check_connection(provider, key, model):
    if provider not in BASES or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", model):
        raise ProviderError("제공자와 모델 ID를 확인해 주세요.")
    data = call(provider, key, f"/models/{model}")
    if provider == "gemini" and "generateContent" not in data.get("supportedGenerationMethods", []):
        raise ProviderError("텍스트 생성 가능한 Gemini 모델을 선택해 주세요.")


def generate(provider, key, model, instructions, prompt, schema=None):
    if provider == "openai":
        body = {"model": model, "instructions": instructions, "input": prompt, "store": False}
        if schema:
            body["text"] = {"format": {"type": "json_schema", "name": "prd", "strict": True, "schema": schema}}
        data = call(provider, key, "/responses", body)
        if data.get("status") == "incomplete":
            raise ProviderError("응답이 중단되었습니다. 범위를 줄여 다시 생성해 주세요.")
        text = "".join(c.get("text", "") for item in data.get("output", []) for c in item.get("content", []) if c.get("type") == "output_text")
    elif provider == "anthropic":
        body = {"model": model, "max_tokens": 8192, "system": instructions, "messages": [{"role": "user", "content": prompt}]}
        if schema:
            body["tools"] = [{"name": "write_prd", "description": "완성된 PRD를 반환합니다.", "input_schema": schema}]
            body["tool_choice"] = {"type": "tool", "name": "write_prd"}
        data = call(provider, key, "/messages", body)
        if data.get("stop_reason") == "max_tokens":
            raise ProviderError("응답이 길어 중단되었습니다. 범위를 줄여 주세요.")
        text = next((json.dumps(c["input"], ensure_ascii=False) for c in data.get("content", []) if c.get("type") == "tool_use" and c.get("name") == "write_prd"), "") if schema else "".join(c.get("text", "") for c in data.get("content", []) if c.get("type") == "text")
    else:
        body = {"systemInstruction": {"parts": [{"text": instructions}]}, "contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if schema:
            body["generationConfig"] = {"responseMimeType": "application/json", "responseJsonSchema": schema}
        data = call(provider, key, f"/models/{model}:generateContent", body)
        candidates = data.get("candidates", [])
        if not candidates or candidates[0].get("finishReason") != "STOP":
            raise ProviderError("응답이 차단되거나 완료되지 않았습니다. 입력과 모델을 확인해 주세요.")
        text = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []) if not p.get("thought"))
    if not text.strip():
        raise ProviderError("모델이 사용 가능한 응답을 반환하지 않았습니다.")
    return text
