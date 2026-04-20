import re

from httpx import ASGITransport
from httpx import AsyncClient

from reporting.app import create_app


async def test_healthcheck(mocker):
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/healthcheck")
    assert ret.status_code == 200
    assert ret.json() == {"success": True}


async def test_index(mocker, tmp_path):
    # Create a minimal build fixture so the test doesn't rely on a built frontend.
    (tmp_path / "index.html").write_text(
        "<!DOCTYPE html><html><head>"
        '<meta property="csp-nonce" content="{{ csp_nonce() }}" />'
        '</head><body><div id="root"></div></body></html>'
    )
    (tmp_path / "favicon.png").write_bytes(b"")
    static_dir = tmp_path / "static"
    static_dir.mkdir(parents=True)
    (static_dir / "app.js").write_text("// app")

    mocker.patch("reporting.settings.STATIC_FOLDER", str(tmp_path))

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # SPA fallback serves index.html for unknown paths
        ret = await client.get("/")
        assert ret.status_code == 200
        csp = ret.headers["content-security-policy"]
        nonce_match = re.search(r"style-src 'self' 'nonce-([^']+)'", csp)
        assert nonce_match is not None
        nonce = nonce_match.group(1)
        assert f'<meta property="csp-nonce" content="{nonce}" />' in ret.text

        # Known root-level static file
        ret = await client.get("/favicon.png")
        assert ret.status_code == 200

        # Static JS file
        ret = await client.get("/static/app.js")
        assert ret.status_code == 200
