### Task 6: Infra de testes (dev deps + cleanup) e CI

**Files:**
- Modify: `apps/api/tests/conftest.py` (cleanup do temp dir)
- Modify: `apps/api/pyproject.toml` (dev deps + pytest config)
- Create: `.github/workflows/ci.yml`

NOTE: o conftest.py JA EXISTE e funciona (criado na Task 1, extendido na Task 5 com API_KEY). NAO reescreva do zero — apenas adicione o cleanup do temp dir, mantendo a estrutura atual (pytest_asyncio.fixture, fixtures _setup_db e client).

**Interfaces:**
- Consumes: fixtures `_setup_db` e `client` ja existentes em `apps/api/tests/conftest.py`.
- Produces: dev-deps `dev` em pyproject + config pytest; workflow CI que roda `pip install -e ".[dev]"` e `python -m pytest -v` em apps/api.

- [ ] **Step 1: cleanup no conftest**

O arquivo atual (`apps/api/tests/conftest.py`) usa `_tmp = tempfile.mkdtemp(prefix="estudiohc_test_")` na linha 5 e nunca limpa o diretorio. Adicione cleanup no teardown da fixture `_setup_db` (que tem scope=session). Apos `yield`, remova `_tmp` recursivamente:

```python
import shutil

# ... no final da fixture _setup_db, apos yield:
    shutil.rmtree(_tmp, ignore_errors=True)
```

Mantenha todo o resto do arquivo como esta (imports, os.environ, pytest_asyncio, ASGITransport). Apenas acrescente `import shutil` no topo e a linha de cleanup na fixture.

- [ ] **Step 2: dev deps + pytest config no pyproject**

Em `apps/api/pyproject.toml`, adicionar (ja existe a secao `[tool.pytest.ini_options]` com `asyncio_mode = "auto"` — mantenha; adicione `testpaths` se nao estiver):

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: CI workflow**

Criar `.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push:
    branches: [master]
  pull_request:

jobs:
  test-api:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install deps
        working-directory: apps/api
        run: pip install -e ".[dev]"
      - name: Run tests
        working-directory: apps/api
        run: python -m pytest -v
```

- [ ] **Step 4: Rodar testes localmente**

Run (na pasta `apps/api`):
```
..\..\.venv\Scripts\python.exe -m pytest -v
```
Expected: todos PASS (4 testes: 2 de test_memory.py + 2 de test_security.py). Nao precisa rodar `pip install -e ".[dev]"` — o venv ja tem as deps; a instalacao ficara para o CI.

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/conftest.py apps/api/pyproject.toml .github/workflows/ci.yml
git commit -m "test(api): pytest harness + CI workflow"
```

---
