from datetime import datetime
import os
import subprocess
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.projetos import Projeto
from ..schemas import ProjetoEntry, ProjetosSyncPayload, ProjetoRelatorioPayload
from ..config import settings

router = APIRouter(prefix="/api/projetos", tags=["Projetos"])


@router.get("")
async def get_projetos(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Projeto).order_by(Projeto.nome.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "nome": r.nome,
            "local": r.local_caminho,
            "preview": r.readme_preview,
            "status": r.status,
            "tags": r.tags,
            "estacao": r.estacao,
        }
        for r in rows
    ]


@router.post("/sync")
async def sync_projetos(payload: ProjetosSyncPayload, db: AsyncSession = Depends(get_db)):
    count = 0
    for p in payload.projetos:
        existing = await db.execute(
            select(Projeto).where(
                Projeto.nome == p.nome,
                Projeto.estacao == p.estacao,
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            row.local_caminho = p.local_caminho
            row.readme_preview = p.readme_preview
            row.status = p.status
            row.tags = p.tags
            row.ultima_atualizacao = datetime.now().isoformat()
        else:
            db.add(
                Projeto(
                    nome=p.nome,
                    local_caminho=p.local_caminho,
                    status=p.status,
                    tags=p.tags,
                    readme_preview=p.readme_preview,
                    estacao=p.estacao,
                    ultima_atualizacao=datetime.now().isoformat(),
                )
            )
        count += 1
    await db.commit()
    return {"ok": True, "count": count}


@router.get("/relatorio")
async def gerar_relatorio_get(nome: str):
    payload = ProjetoRelatorioPayload(nome=nome)
    return await gerar_relatorio(payload)


@router.post("/gerar-relatorio")
async def gerar_relatorio(payload: ProjetoRelatorioPayload):
    nome = payload.nome
    estacao = payload.estacao
    readme = payload.readme or ""
    git_status = payload.git_status or ""
    git_log = payload.git_log or ""
    tasks_content = payload.tasks_content or ""

    # Enrich with local data if from central server
    if estacao in ("central", "vmi2968998") or "EstudioHC-Memory-Suite" in nome:
        servidor_path = os.path.expanduser("~/Apps/EstudioHC-Memory-Suite")
        if os.path.exists(servidor_path):
            if not readme:
                readme_path = os.path.join(servidor_path, "README.md")
                if os.path.exists(readme_path):
                    try:
                        with open(readme_path, "r", encoding="utf-8") as f:
                            readme = f.read(4000)
                    except Exception:
                        pass
            if not git_status:
                try:
                    res = subprocess.run(
                        ["git", "status", "--porcelain"],
                        cwd=servidor_path,
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    git_status = res.stdout.strip()
                except Exception:
                    pass
            if not git_log:
                try:
                    res = subprocess.run(
                        ["git", "log", "-n", "5", "--oneline"],
                        cwd=servidor_path,
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    git_log = res.stdout.strip()
                except Exception:
                    pass

    prompt = f"""Você é o analista de sistemas sênior do ecossistema EstudioHC.
Com base nas informações técnicas brutas fornecidas do projeto, gere um relatório de estado atual impecável, profissional, estruturado em markdown e estritamente em Português do Brasil.

[Informações Técnicas do Projeto]
Nome do Projeto: {nome}
Estação de Trabalho: {estacao}
Git Status (Arquivos modificados ou pendentes):
{git_status or 'Nenhuma modificação pendente.'}

Últimos Commits (Git Log):
{git_log or 'Nenhum histórico recente.'}

Conteúdo do README / Preview:
{readme or 'Nenhuma descrição técnica disponível.'}

Conteúdo do Arquivo de Tarefas (task.md/todo.md):
{tasks_content or 'Nenhuma lista de tarefas formal encontrada.'}

Por favor, gere duas informações:
1. Um resumo curto e cativante sobre o projeto, traduzido e adaptado para o Português do Brasil (máximo de 200 caracteres), focado em qual o objetivo do projeto.
2. Um relatório técnico completo e aprofundado estruturado em Markdown, contendo:
   - 📊 **Estado Geral:** (Se está "Ativo (Em Desenvolvimento)" ou "Parado / Estável") em destaque, justificando com base no git status e commits recentes.
   - 🚀 **Fase de Implementação:** Defina uma fase realista (ex: Fase 1: Planejamento, Fase 2: Estruturação, Fase 3: Polimento/Finalização, ou Estável).
   - 📋 **Tarefas Pendentes:** Liste tarefas recomendadas para continuidade (extraídas do task.md ou propostas de forma realista por você).
   - 🔄 **Últimas Tarefas Executadas:** Liste as últimas 5 ações/commits do projeto formatados como uma linha do tempo/histórico.
   - ⚠️ **Erros e Alertas:** Destaque quaisquer arquivos modificados sem commit, commits não enviados ou possíveis problemas encontrados nos metadados.

Você DEVE retornar sua resposta ESTRETAMENTE em formato JSON com a seguinte estrutura de chaves (não inclua nenhuma explicação extra antes ou depois do JSON):
{{
  "preview_pt": "Descrição traduzida curta de 200 caracteres em português",
  "relatorio_md": "Conteúdo completo do relatório formatado em Markdown premium"
}}
"""
    try:
        resultado = subprocess.run(
            [settings.HERMES_CLI, "-z", prompt, "chat"],
            capture_output=True,
            text=True,
            timeout=settings.HERMES_TIMEOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        saida = resultado.stdout.strip()

        preview_pt = ""
        relatorio_md = ""

        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', saida, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                preview_pt = data.get("preview_pt", "")
                relatorio_md = data.get("relatorio_md", "")
            except Exception:
                pass

        if not relatorio_md:
            json_match = re.search(r'(\{.*\})', saida, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    preview_pt = data.get("preview_pt", "")
                    relatorio_md = data.get("relatorio_md", "")
                except Exception:
                    pass

        if not relatorio_md:
            preview_pt = saida[:200]
            relatorio_md = saida

        return {
            "ok": True,
            "preview": preview_pt,
            "relatorio": relatorio_md,
        }
    except Exception as e:
        rel_erro = f"""# ⚠️ Falha na Geração do Relatório por IA

> **Aviso do Sistema:** Ocorreu um erro técnico inesperado ao acionar a inteligência artificial central (**Hermes**) no servidor central Contabo.

---

### 📊 Estado de Fallback Técnico

Para garantir que você não fique sem informações sobre o seu projeto, abaixo estão listados os detalhes técnicos brutos do erro para auditoria e depuração rápida.

#### 🔍 Diagnóstico do Erro:
```text
{e}
```

---
*💡 **Dica:** Certifique-se de que a internet está funcional no servidor Contabo e que a chave de API do OpenRouter não esteja esgotada. Você pode tentar gerar novamente o relatório a qualquer momento clicando no botão de reanálise abaixo.*"""
        return {
            "ok": False,
            "erro": str(e),
            "relatorio": rel_erro,
        }