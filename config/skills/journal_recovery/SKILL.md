---
name: journal_recovery
description: Recupera contexto de sessões anteriores do journal .matrixx/ no CWD. Complementa o MCP Memory Server da Suite com WAL textual de sobrevivência pós-queda.
---

# Journal Recovery Protocol

Sempre que uma **nova sessão iniciar** (ou ao receber um comando de continuação), você DEVE:

## 1. Verificar existência do journal

```typescript
// Tentar CWD primeiro, depois /tmp/.matrixx/ como fallback
const paths = [".matrixx/journal.md", "/tmp/.matrixx/journal.md"]
for (const p of paths) {
  if (await exists(p)) { read(p); break }
}
```

Se nenhum existir → não há contexto anterior.

## 2. Extrair contexto de continuidade

Das últimas 15 entradas, extraia:
- **Último user prompt**
- **Última resposta do assistente**
- **Decisões pendentes** — não resolvidas
- **TODOs** — tarefas em andamento

## 3. Injetar como contexto

```markdown
> **Journal Recovery:** Sessão anterior detectada.
> Último contexto: [resumo 1-2 linhas]
> Decisões pendentes: [se houver]
> TODOs abertos: [se houver]
```

## 4. Append a cada turno

Ao final de cada resposta sua:

```bash
cat >> .matrixx/journal.md << 'ENTRY'

## <ISO_TIMESTAMP>

**user:** > <o que o usuário disse>

**assistant:** > <resumo 2-3 linhas>

**todos:** <status>

**decisions:**
- <decisões>
ENTRY
```

Se `.matrixx/` não existir no CWD, usar `/tmp/.matrixx/journal.md`.

## 5. Integração com EstudioHC-Memory-Suite

Em servidores com a Suite instalada:

1. O journal local é o **WAL de sobrevivência** (pós-queda)
2. O MCP Memory Server da Suite (`/remember`, `/recall`) é a **persistência remota compartilhada**
3. O `memory-auto` skill (Qdrant) é a **busca semântica entre sessões**

Os três são complementares. Nenhum substitui o outro.

## 6. Bootstrap em máquinas novas

O script `scripts/bootstrap-memory-stack.sh` da Suite instala este skill
automaticamente em `~/.agents/skills/journal_recovery/`.

## Notas

- Append via `>>` é atômico — linha atual se perde em queda, todo o resto persiste.
- Este skill não depende do servidor Contabo. Funca 100% offline.
- Se o servidor Contabo estiver acessível, o MCP Memory Server da Suite deve ser usado para memória compartilhada entre estações.
