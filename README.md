# Run Personal Content Service

Servico interno em Python para descoberta assistida de corridas e noticias do Run Personal.

O objetivo deste servico e atuar como um radar de conteudo: consultar fontes externas, normalizar resultados, deduplicar, classificar relevancia e preparar sugestoes para revisao no painel da plataforma. A publicacao final deve continuar passando por revisao humana no `rp-frontend`.

## Escopo Inicial

- Descobrir corridas por estado/cidade.
- Classificar corridas por relevancia: `tier 1`, `tier 2`, `tier 3`.
- Preparar rascunhos de noticias com resumo original e link da fonte.
- Salvar descobertas no banco para revisao posterior.
- Expor endpoints internos protegidos por API key.

## Stack

- Python 3.12
- FastAPI
- Pydantic Settings
- HTTPX
- SQLAlchemy
- APScheduler
- OpenAI SDK
- Pytest
- Ruff

## Estrutura

```text
rp-content-service/
+-- app/
|   +-- main.py        # FastAPI app e health check
|   +-- config.py      # Configuracao por ambiente
|   +-- __init__.py
+-- tests/
|   +-- test_health.py
+-- .github/workflows/
|   +-- ci.yml
+-- Dockerfile
+-- pyproject.toml
+-- README.md
```

## Variaveis de Ambiente

| Variavel | Descricao |
| --- | --- |
| `APP_ENV` | `development`, `demo`, `staging` ou `production`. |
| `DATABASE_URL` | URL do PostgreSQL compartilhado com o frontend. |
| `API_KEY` | Chave exigida em endpoints internos. |
| `OPENAI_API_KEY` | Chave para classificacao e resumo via IA. Opcional no MVP. |
| `OPENAI_MODEL` | Modelo usado para classificacao e resumos. Padrao: `gpt-4o-mini`. |
| `LOG_LEVEL` | Nivel de log. Padrao: `INFO`. |

## Desenvolvimento

```powershell
poetry install
poetry run uvicorn app.main:app --reload --port 8002
```

Health check:

```text
http://localhost:8002/health
```

## Testes e Lint

```powershell
poetry run ruff check .
poetry run pytest
```

## Endpoints Iniciais

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/health` | Status do servico. |

Endpoints planejados:

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `POST` | `/jobs/races/run` | Executa descoberta de corridas sob demanda. |
| `POST` | `/jobs/news/run` | Executa descoberta de noticias sob demanda. |
| `GET` | `/sources` | Lista fontes monitoradas. |
| `POST` | `/sources` | Cadastra fonte monitorada. |

## Regras de Produto

- O servico nao deve publicar corrida ou noticia automaticamente.
- Todo resultado descoberto deve entrar como pendente de revisao.
- Todo conteudo gerado por IA deve preservar link da fonte.
- Sem `OPENAI_API_KEY`, o servico usa classificacao heuristica para nao bloquear demo/dev.
- Noticias devem ser resumidas em texto original, sem copiar materia integral.
- Corridas devem ser deduplicadas por nome, data, cidade/estado e fonte.

## Tiers de Corrida

| Tier | Uso |
| --- | --- |
| `tier 1` | Grandes provas nacionais, maratonas, meias famosas e circuitos de alta relevancia. |
| `tier 2` | Provas regionais relevantes, eventos recorrentes e organizadores conhecidos. |
| `tier 3` | Corridas locais, eventos municipais, beneficentes ou de menor alcance. |

## Branches

- `main`: producao estavel.
- `develop`: integracao e demo.
- `feature/*`: desenvolvimento de funcionalidades.
- `release/*`: estabilizacao de release.
