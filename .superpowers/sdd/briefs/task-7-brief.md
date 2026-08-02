### Task 7: Deploy e verificacao em producao

PREREQUISITO: este branch ja foi mergeado em master (via finishing-a-development-branch) e master foi pushed para origin. O servidor puxa o branch master. Se o merge/push ainda nao aconteceu, faca-o antes deste passo.

- [ ] **Step 1: Push (se ainda nao feito)**

```bash
git checkout master
git merge fix/memory-stack
git push origin master
```

- [ ] **Step 2: Pull + restart no servidor**

```bash
ssh deploy@100.64.117.78 "cd ~/Apps/EstudioHC-Memory-Suite && git pull && sudo systemctl restart estudiohc-api.service"
```

- [ ] **Step 3: Verificar API + /remember retorna id**

```bash
curl -s -X POST http://localhost:5050/remember -H 'Content-Type: application/json' \
  -d '{"agent_name":"teste","project":"opencode","category":"context","content":"{\"s\":\"verificacao deploy\",\"r\":null,\"c\":true}"}'
```
Expected: `{"status":"success","id":<int>}`

- [ ] **Step 4: Verificar get_status legivel**

```bash
curl -s http://localhost:5050/status/opencode
```
Expected: textos legiveis (sem `{"s":` bruto).

- [ ] **Step 5: Verificar backup.sh**

```bash
cd ~/Apps/EstudioHC-Memory-Suite && bash scripts/backup.sh --dry-run
```
Expected: `OK memory-db`.

- [ ] **Step 6: (Opcional) Ativar auth**

Criar `~/Apps/EstudioHC-Memory-Suite/.env` com `API_KEY=<chave>` e `MEMORY_API_KEY=<chave>` no comando do MCP no `opencode.json`. Reiniciar API e testar 401 sem chave. SE optar por ativar auth: gere uma chave forte (ex: `python3 -c "import secrets; print(secrets.token_hex(32))"`), crie o .env, reinicie a API, teste 401 sem chave e 200 com chave, e atualize o comando MCP `estudiohc-memory` no `C:\Users\helci\.config\opencode\opencode.json` para incluir `MEMORY_API_KEY=<chave>` (ex: prefixo `MEMORY_API_KEY=... &&` no comando ssh). NAO commitar a chave no repo.

- [ ] **Step 7: Registrar memoria de conclusao**

Via MCP `add_memory` no opencode (projeto opencode, category task_completed), documentando a correcao dos 4 bugs + auth + testes.

---
