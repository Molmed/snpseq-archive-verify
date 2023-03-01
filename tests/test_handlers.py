import yaml

from aiohttp.test_utils import AioHTTPTestCase
from aiohttp import web

import archive_verify.app as app_setup
import archive_verify.pdc_client
import mock_redis_client
import unittest.mock as mock


class HandlerTestCase(AioHTTPTestCase): 

    BASE_URL = ""

    def _load_config(self):
        with open("tests/test_config.yaml") as config:
            return yaml.safe_load(config)

    async def get_application(self):
        app = web.Application()
        app["config"] = self._load_config()
        self.BASE_URL = app["config"]["base_url"]
        app_setup.handlers.redis_client = mock_redis_client
        app.cleanup_ctx.append(app_setup.handlers.redis_context)
        app_setup.setup_routes(app)
        return app

    async def post_queued_request(self, endpoint="verify"):
        url = f"{self.BASE_URL}/{endpoint}"
        payload = {
            "host": "testbox",
            "archive": "test_archive",
            "description": "test-description"}
        return await self.client.request("POST", url, json=payload)

    async def test_root(self):
        request = await self.client.request("GET", "/")
        assert request.status == 404
        text = await request.text()
        assert "not found" in text.lower()

    async def test_unknown(self):
        request = await self.client.request("GET", "/unknown_route")
        assert request.status == 404
        text = await request.text()
        assert "not found" in text.lower()

    async def test_basic_verify(self):
        request = await self.post_queued_request()
        assert request.status == 200
        resp = await request.json()
        assert resp["status"] == "pending"
        assert resp["action"] == "verify"
        assert resp["job_id"] != ""

    async def test_basic_download(self):
        request = await self.post_queued_request(endpoint="download")
        assert request.status == 200
        resp = await request.json()
        assert resp["status"] == "pending"
        assert resp["action"] == "download"
        assert resp["job_id"] != ""

    async def test_basic_status_wrong_id(self):
        url = self.BASE_URL + "/status/foobar"
        request = await self.client.request("GET", url)
        assert request.status == 400
        resp = await request.json()
        assert "no such job foobar found" in resp["msg"].lower()

    async def test_basic_status_successful_job(self):
        with mock.patch.object(archive_verify.pdc_client.PdcClient, "download") as download_mock, \
                mock.patch("archive_verify.workers.compare_md5sum") as md5_mock:
            download_mock.return_value = True
            md5_mock.return_value = True

            request = await self.post_queued_request(endpoint="download")

            assert request.status == 200
            resp = await request.json()

            url = self.BASE_URL + "/status/" + resp["job_id"]
            request = await self.client.request("GET", url)
            assert request.status == 200
            resp = await request.json()
            assert resp["state"] == "done"

    async def test_basic_status_failed_job(self):
        with mock.patch.object(archive_verify.pdc_client.PdcClient, "download") as download_mock:
            download_mock.return_value = False

            request = await self.post_queued_request(endpoint="download")
            assert request.status == 200
            resp = await request.json()

            url = self.BASE_URL + "/status/" + resp["job_id"]
            request = await self.client.request("GET", url)
            assert request.status == 500
            resp = await request.json()
            assert resp["state"] == "error"
            assert "failed to properly download archive from pdc" in resp["msg"]
