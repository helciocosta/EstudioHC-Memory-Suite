### Task 3: Corrigir caminho do DB no `backup.sh`

**Files:**
- Modify: `scripts/backup.sh` (a linha que define `DB=...`)

**Contexto:** o backup diario (timer systemd 03:00) nunca copiava o DB real porque apontava para `server/estudiohc_memory.db` que nao existe. O DB real fica em `data/estudiohc.db`.

- [ ] **Step 1: Trocar o path errado**

No arquivo `scripts/backup.sh`, substituir:

```bash
DB="$REPO_DIR/server/estudiohc_memory.db"
```

por:

```bash
DB="$REPO_DIR/data/estudiohc.db"
```

NAO altere mais nada no arquivo.

- [ ] **Step 2: Validar dry-run (verificacao de sintaxe)**

Nao ha como rodar o dry-run contra o servidor a partir desta maquina Windows de forma confiavel nesta task (a validacao real no servidor e a Task 7 de deploy). Em vez disso, valide que o shell script continua sintaticamente valido e que a variavel DB aponta para o caminho correto:

```bash
grep -n '^DB=' scripts/backup.sh
```

Esperado: `DB="$REPO_DIR/data/estudiohc.db"`

- [ ] **Step 3: Commit**

```bash
git add scripts/backup.sh
git commit -m "fix(scripts): correct DB path in backup.sh"
```
