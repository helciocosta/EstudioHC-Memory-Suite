import subprocess
import pytest
from unittest.mock import patch

from src.routers import hermes

MASTER = {"X-API-Key": "test-key"}


def _fake_popen_factory(chamadas):
    """Cria um FakeProc que captura o comando e retorna saída JSON-lines de opencode."""
    class FakeProc:
        def __init__(self, cmd, *a, **k):
            chamadas.append(cmd)
            self.pid = 9999
        def communicate(self, timeout=None):
            return ('{"type":"text","part":{"text":"oi"}}\n', "")
        def wait(self):
            pass
    return FakeProc


@pytest.mark.asyncio
async def test_sandbox_usa_docker_com_flags_restritivas(client, tmp_path):
    await client.post("/api/estacoes/registrar",
                      json={"hostname": "est-sb1", "chave": "chave-sb1"}, headers=MASTER)
    hermes._sandbox_ok = None
    chamadas = []
    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("subprocess.Popen", side_effect=_fake_popen_factory(chamadas)):
        r = await client.post("/api/hermes", json={"mensagem": "teste"}, headers=MASTER)
    assert r.status_code == 200
    assert chamadas, "Popen não chamado"
    cmd = chamadas[0]
    assert "--network" in cmd and "none" in cmd
    assert "--read-only" in cmd
    assert "--tmpfs" in cmd and "/tmp" in cmd
    assert "--tmpfs" in cmd and "/home/sandbox" in cmd
    assert "--workdir" in cmd and "/work" in cmd
    assert "--rm" in cmd
    assert "hermes-sandbox:latest" in cmd


@pytest.mark.asyncio
async def test_sandbox_sem_docker_usa_fallback_com_tools(client):
    await client.post("/api/estacoes/registrar",
                      json={"hostname": "est-sb2", "chave": "chave-sb2"}, headers=MASTER)
    hermes._sandbox_ok = None
    chamadas = []
    with patch("shutil.which", return_value=None), \
         patch("subprocess.Popen", side_effect=_fake_popen_factory(chamadas)), \
         patch("src.routers.hermes._env_filtrado", return_value={}):
        r = await client.post("/api/hermes", json={"mensagem": "x"}, headers=MASTER)
    assert chamadas, "fallback deveria chamar Popen"
    assert "--tools" in chamadas[0] or "read,write" in chamadas[0]