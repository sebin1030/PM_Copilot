import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app import auth, storage, providers
from backend.app.connections import SESSIONS
from backend.app.openai_service import PRD_SCHEMA, validate_output


def prd(title="초안"):
    result = {key: [] if value["type"] == "array" else title for key, value in PRD_SCHEMA["properties"].items()}
    result["features"] = [{"id": "FEAT-001", "name": title, "description": "기능 상세", "priority": "P0"}]
    result["requirements"] = [{"id": "REQ-001", "title": title, "description": "요구사항", "acceptanceCriteria": ["저장 후 목록에 표시된다"]}]
    return result


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patch = patch.object(storage, "PROJECTS_DIR", Path(self.temp.name))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        SESSIONS.clear()
        self.client = TestClient(app)
        self.project = self.client.post("/api/projects", json={"name": "테스트"}).json()["project"]
        self.root = f"/api/projects/{self.project['projectId']}"
        self.client.get("/api/connections")
        with patch("backend.app.main.check_connection"):
            response = self.client.post("/api/connections", json={"provider": "openai", "model": "test-model", "api_key": "secret-test-key"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("secret-test-key", response.text)

    def generate(self, title):
        with patch("backend.app.main.generate_prd", return_value=(prd(title), "test-model")):
            response = self.client.post(self.root + "/documents/prd/generate", json={"model": "test-model"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["document"]

    def approve(self, document, status="APPROVED"):
        return self.client.post(self.root + "/documents/prd/approval", json={"status": status, "document_id": document["documentId"]})

    def test_draft_reject_and_approval_preserve_official(self):
        first = self.generate("첫 번째")
        current = self.client.get(self.root).json()["project"]
        self.assertEqual(current["requirements"], [])
        self.assertNotIn("prd", current["documents"])
        self.assertEqual(self.client.get(self.root + "/documents/prd/download").status_code, 404)
        self.assertIn("미확정 초안", self.client.get(self.root + "/documents/prd/download?draft=true").text)
        self.assertEqual(self.approve(first).status_code, 200)
        second = self.generate("두 번째")
        self.assertEqual(second["version"], 2)
        self.assertEqual(self.approve(second, "REJECTED").status_code, 200)
        current = self.client.get(self.root).json()["project"]
        self.assertEqual(current["documents"]["prd"]["content"]["title"], "첫 번째")
        self.assertEqual(current["requirements"][0]["title"], "첫 번째")
        self.assertEqual(self.approve(second).status_code, 409)
        self.assertNotIn("secret-test-key", json.dumps(current))

    def test_stale_draft_cannot_be_approved(self):
        first = self.generate("첫 번째")
        self.generate("두 번째")
        self.assertEqual(self.approve(first).status_code, 409)

    def test_connections_are_isolated_and_revoked(self):
        other = TestClient(app)
        self.assertEqual(other.get("/api/connections").json()["connections"], [])
        self.assertEqual(other.post(self.root + "/documents/prd/generate", json={"model": "test-model"}).status_code, 400)
        self.client.delete("/api/connections/openai")
        self.assertEqual(self.client.post(self.root + "/documents/prd/generate", json={"model": "test-model"}).status_code, 400)

    def test_expired_connection_is_unusable(self):
        for state in SESSIONS.values():
            state["expires"] = 0
        self.assertEqual(self.client.post(self.root + "/documents/prd/generate", json={"model": "test-model"}).status_code, 400)

    def test_lost_update_is_rejected(self):
        a = storage.get_project(self.project["projectId"])
        b = storage.get_project(self.project["projectId"])
        storage.save_project(a, expected_version=a["metadata"]["updatedAt"])
        with self.assertRaises(storage.StorageConflict):
            storage.save_project(b, expected_version=b["metadata"]["updatedAt"])

    def test_invalid_schema_and_legacy_migration(self):
        with self.assertRaises(ValueError):
            validate_output({"title": "불완전"}, PRD_SCHEMA)
        p = storage.get_project(self.project["projectId"])
        p["documents"]["prd"] = {"documentId": "old", "status": "NEEDS_APPROVAL", "content": prd()}
        p["requirements"] = prd()["requirements"]
        storage.save_project(p)
        updated = storage.get_project(p["projectId"])
        self.assertEqual(updated["drafts"]["prd"]["documentId"], "old")
        self.assertEqual(updated["requirements"], [])


class ProviderTests(unittest.TestCase):
    def test_three_adapters_generate_and_validate(self):
        fixtures = {
            "openai": {"output": [{"content": [{"type": "output_text", "text": json.dumps(prd())}]}]},
            "anthropic": {"content": [{"type": "tool_use", "name": "write_prd", "input": prd()}]},
            "gemini": {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(prd())}]}}]},
        }
        for provider, data in fixtures.items():
            with self.subTest(provider=provider), patch.object(providers, "call", return_value=data) as call:
                output = providers.generate(provider, "secret", "test", "instructions", "prompt", PRD_SCHEMA)
                validate_output(json.loads(output), PRD_SCHEMA)
                self.assertNotIn("secret", json.dumps(call.call_args.args[3]))

    def test_provider_errors_do_not_expose_key_or_body(self):
        import httpx
        response = httpx.Response(401, text="secret-test-key")
        with patch.object(httpx.Client, "request", return_value=response):
            with self.assertRaises(providers.ProviderError) as error:
                providers.call("openai", "secret-test-key", "/models/test")
        self.assertNotIn("secret-test-key", str(error.exception))

    def test_truncated_responses_fail(self):
        with patch.object(providers, "call", return_value={"stop_reason": "max_tokens", "content": []}):
            with self.assertRaises(providers.ProviderError):
                providers.generate("anthropic", "secret", "test", "instructions", "prompt", PRD_SCHEMA)


class AuthTests(unittest.TestCase):
    def test_api_rejects_anonymous_project_requests_when_supabase_is_enabled(self):
        client = TestClient(app)
        with patch.object(auth, "supabase_enabled", return_value=True):
            response = client.get("/api/projects")
        self.assertEqual(response.status_code, 401)

    def test_local_development_remains_usable_without_supabase_configuration(self):
        client = TestClient(app)
        with patch.object(auth, "supabase_enabled", return_value=False):
            response = client.get("/api/projects")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
