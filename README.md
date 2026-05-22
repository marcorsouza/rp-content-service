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
| `SCHEDULER_ENABLED` | Liga o APScheduler interno. Padrao: `false`. |
| `SCHEDULER_RACES_HOUR` / `SCHEDULER_RACES_MINUTE` | Horario diario do radar de corridas no fuso de Sao Paulo. Padrao: `05:00`. |
| `SCHEDULER_RACES_STATES` | UFs processadas pelo job diario, separadas por virgula. Padrao: `SP,RJ,MG`. |
| `NEWS_MAX_AGE_HOURS` | Janela maxima para aceitar noticias novas. Padrao: `72`. |
| `NEWS_MAX_ITEMS_PER_RUN` | Limite de noticias ranqueadas por execucao. Padrao: `12`. |
| `NEWS_MIN_SCORE` | Pontuacao minima para gravar uma noticia. Padrao: `35`. |
| `NEWS_REQUIRE_PUBLISHED_AT` | Exige data de publicacao no feed para aceitar a noticia. Padrao: `true`. |
| `NEWS_REQUIRED_TERMS` | Termos que precisam aparecer no titulo/resumo para a noticia ser candidata. |
| `NEWS_BLOCKED_TERMS` | Termos que removem noticias fora do foco editorial. |
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
| `POST` | `/jobs/races/run` | Executa descoberta de corridas sob demanda. |
| `POST` | `/jobs/news/run` | Executa descoberta de noticias sob demanda. |

Endpoints planejados:

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/sources` | Lista fontes monitoradas. |
| `POST` | `/sources` | Cadastra fonte monitorada. |

## Regras de Produto

- O servico nao deve publicar corrida ou noticia automaticamente.
- Todo resultado descoberto deve entrar como pendente de revisao.
- Todo conteudo gerado por IA deve preservar link da fonte.
- Sem `OPENAI_API_KEY`, o servico usa classificacao heuristica para nao bloquear demo/dev.
- Noticias devem ser resumidas em texto original, sem copiar materia integral.
- Noticias precisam passar por filtro de novidade e ranking editorial antes de entrar na fila.
- O ranking de noticias prioriza recencia, fonte, termos fortes e ganchos de engajamento como inscricoes, calendario, recordes e volume de participantes.
- Corridas devem ser deduplicadas por nome, data, cidade/estado e fonte.

## Tiers de Corrida

| Tier | Uso |
| --- | --- |
| `tier 1` | Grandes provas nacionais, maratonas, meias famosas e circuitos de alta relevancia. |
| `tier 2` | Provas regionais relevantes, eventos recorrentes e organizadores conhecidos. |
| `tier 3` | Corridas locais, eventos municipais, beneficentes ou de menor alcance. |

## Branches

- `main`: branch unica de deploy; atualiza demo e producao quando este servico entrar no auto-deploy.
- `develop`: branch historica/legada, sem deploy automatico.
- `feature/*`: desenvolvimento de funcionalidades.
- `release/*`: estabilizacao de release, se o fluxo formal de release for reativado.
