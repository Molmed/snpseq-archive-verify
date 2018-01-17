import yaml

from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web

from archive_verify.app import setup_routes

class HandlerTestCase(AioHTTPTestCase): 

    BASE_URL = ""

    def _load_config(self):
        with open("tests/test_config.yaml") as config:
            return yaml.load(config)

    async def get_application(self):
        app = web.Application()
        app["config"] = self._load_config()
        self.BASE_URL = app["config"]["base_url"]
        setup_routes(app)
        return app

    @unittest_run_loop
    async def test_root(self): 
        request = await self.client.request("GET", "/")
        assert request.status == 404
        text = await request.text()
        assert "not found"  in text.lower()

    @unittest_run_loop
    async def test_basic_verify(self): 
        url = self.BASE_URL + "/verify"
        payload = {"host": "testbox", "archive": "test_archive", "description": "test-description"}
        request = await self.client.request("POST", url, json=payload)
        assert request.status == 200
        resp = await request.json()
        assert resp["status"] == "pending"
        assert resp["job_id"] != ""

    @unittest_run_loop
    async def test_basic_status_wrong_id(self):
        url = self.BASE_URL + "/status/foobar"
        request = await self.client.request("GET", url)
        assert request.status == 400
        resp = await request.json()
        assert "no such job foobar found" in resp["msg"].lower()


