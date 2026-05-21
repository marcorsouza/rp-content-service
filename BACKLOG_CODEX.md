# Backlog — rp-content-service (Radar de Conteúdo)

> Serviço Python separado para curadoria assistida por IA de corridas e notícias.
> A IA age como "estagiária incansável": encontra, organiza, resume e deixa pronto para aprovação humana.
> **Nada é publicado automaticamente.** Todo resultado passa por revisão no painel do admin.

---

## Decisões de Arquitetura

| Decisão | Escolha | Motivo |
|---------|---------|--------|
| Linguagem | Python 3.12 | Melhor ecossistema para scraping, IA, parsers |
| Framework | FastAPI | Consistente com rp-garmin-service |
| Scheduler | APScheduler (depois Celery+Redis) | Simples no MVP, escalável depois |
| Banco | PostgreSQL compartilhado | Novas tabelas no mesmo DB, Prisma faz as migrations |
| IA | OpenAI SDK | Classificação de tier e geração de resumo |
| Autenticação | X-API-Key | Igual ao Garmin Service |
| Publicação | Nunca automática | Admin revisa no /platform/content-radar |

### Fluxo de comunicação

```
rp-content-service          PostgreSQL           rp-frontend
    (Python)                  (DB)               (Next.js)
       │                        │                     │
       │── busca fontes ──────► │                     │
       │── normaliza ─────────► │                     │
       │── classifica ────────► │                     │
       │── gera rascunho ─────► │                     │
       │── salva como NEW ────► │                     │
       │                        │◄── admin revisa ────│
       │                        │◄── edita/aprova ────│
       │                        │──► publica ─────────│
```

---

## Modelo de Dados (novas tabelas — migrations via Prisma no rp-frontend)

```
ContentSource
  id
  name                  # ex: "Ticket Sports", "Central da Corrida"
  type                  # RACE | NEWS
  baseUrl
  state                 # UF opcional
  city                  # cidade opcional
  isActive              # Bool
  createdAt / updatedAt

ContentDiscoveryRun
  id
  type                  # RACE | NEWS
  state                 # UF processado (ou null para nacional)
  status                # RUNNING | DONE | FAILED
  startedAt
  finishedAt
  itemsFound
  itemsNew
  itemsDuplicate
  errors                # JSON

DiscoveredRace
  id
  title
  state
  city
  eventDate             # DateTime?
  location              # texto livre
  sourceUrl             # link original
  sourceName
  tier                  # 1 | 2 | 3
  confidence            # 0.0-1.0
  status                # NEW | DUPLICATE | APPROVED | REJECTED | PUBLISHED
  aiSummary             # resumo gerado por IA
  rawPayload            # JSON
  discoveryRunId        # FK ContentDiscoveryRun
  publishedRaceId       # FK RaceEvent (quando publicado)
  createdAt / updatedAt

DiscoveredNews
  id
  originalTitle
  suggestedTitle        # gerado por IA
  summary               # resumo original gerado por IA (não cópia da matéria)
  sourceUrl
  sourceName
  category              # RACE | HEALTH | PERFORMANCE | MARKET | GENERAL
  confidence            # 0.0-1.0
  status                # NEW | DUPLICATE | APPROVED | REJECTED | PUBLISHED
  rawPayload            # JSON
  discoveryRunId        # FK ContentDiscoveryRun
  publishedPostId       # FK OrganizationPost ou NewsPost (quando publicado)
  createdAt / updatedAt
```

---

## Fontes Planejadas

### Corridas
| Fonte | Tipo | Cobertura |
|-------|------|-----------|
| Ticket Sports | Scraping/API | Nacional |
| Minhas Inscrições | Scraping | Nacional |
| Central da Corrida | RSS/Scraping | Nacional |
| Ativo.com | Scraping | Nacional |
| Sympla / Eventbrite | API | Nacional |
| Google Search (SerpAPI) | API | Por estado |
| Sites de prefeituras | Scraping seletivo | Por cidade |

### Notícias
| Fonte | Tipo |
|-------|------|
| Google News RSS | RSS |
| Central da Corrida | RSS |
| Runners Brasil | RSS/Scraping |
| Webrun | RSS/Scraping |
| Bing News API | API |
| SerpAPI News | API |

---

## Tiers de Corrida

| Tier | Critério | Exemplos |
|------|---------|---------|
| **Tier 1** | Provas nacionais/internacionais, maratonas, meias famosas, circuitos com alto volume ou marca forte | SP City Marathon, Maratona do Rio, W21K, Track & Field Run Series, Circuito das Estações |
| **Tier 2** | Provas regionais relevantes, recorrência anual, organizadores conhecidos, grupos grandes | Provas estaduais bem organizadas, corridas de assessorias referência |
| **Tier 3** | Corridas locais, eventos municipais, beneficentes, plataformas menores | Corridas de bairro, eventos de prefeitura |

---

## Endpoints

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| `GET` | `/health` | — | Status do serviço |
| `POST` | `/jobs/races/run` | X-API-Key | Dispara descoberta de corridas (estado opcional) |
| `POST` | `/jobs/news/run` | X-API-Key | Dispara descoberta de notícias |
| `GET` | `/sources` | X-API-Key | Lista fontes ativas |
| `POST` | `/sources` | X-API-Key | Cadastra fonte |
| `PATCH` | `/sources/{id}` | X-API-Key | Ativa/desativa fonte |
| `GET` | `/jobs` | X-API-Key | Histórico de execuções |

---

## Regras de Produto (inegociáveis)

- **Nunca publicar automaticamente.** Qualquer item descoberto entra como `status: NEW`.
- **Sempre preservar link da fonte** em `sourceUrl`.
- **Notícias**: gerar resumo original — nunca copiar matéria na íntegra.
- **Corridas**: validar data, cidade e link antes de aprovar.
- **Deduplicação forte**: por `title + eventDate + city + state + sourceName` para corridas; `sourceUrl` para notícias.
- **Rate limit** nas requisições externas — não virar scraping agressivo.
- **Começar pequeno**: 2-3 estados e 2-3 fontes no MVP, expandir depois.

---

## Roadmap MVP

### MVP 1 — Radar de Corridas (foco atual)
> Descoberta manual por demanda, approval humano, sem IA de tier.

- [ ] Schema Prisma: `ContentSource`, `ContentDiscoveryRun`, `DiscoveredRace`
- [ ] Migration no rp-frontend
- [ ] Endpoint `POST /jobs/races/run?state=SP`
- [ ] Integração com Ticket Sports (parser básico)
- [ ] Integração com Minhas Inscrições (parser básico)
- [ ] Deduplicação por `title + eventDate + city`
- [ ] Salvar como `status: NEW` no banco
- [ ] Tela `/platform/content-radar` no rp-frontend (tab Corridas)
  - Lista de corridas descobertas com status
  - Ações: Aprovar → cria RaceEvent | Rejeitar | Marcar duplicado | Editar antes de publicar

### MVP 2 — Classificação por Tier + Fontes configuráveis
> IA classifica tier, admin configura fontes pela UI.

- [ ] Integração OpenAI: classificar tier 1/2/3 com base em nome + localidade + data
- [ ] `confidence` score retornado pela IA
- [ ] CRUD de fontes na tela `/platform/content-radar/sources`
- [ ] Mais fontes: Central da Corrida, Ativo.com
- [ ] APScheduler: job diário automático às 05:00
- [ ] Cron VPS: `POST /jobs/races/run` diário

### MVP 3 — Radar de Notícias
> IA gera rascunho de notícia a partir de matéria externa.

- [ ] Schema Prisma: `DiscoveredNews`
- [ ] Endpoint `POST /jobs/news/run`
- [ ] Integração RSS: Google News, Central da Corrida, Runners Brasil
- [ ] IA: gerar `suggestedTitle` + `summary` original
- [ ] Deduplicação por `sourceUrl`
- [ ] Tab "Notícias descobertas" no `/platform/content-radar`
  - Ações: Aprovar → cria NewsPost como DRAFT | Rejeitar | Editar antes de publicar

### MVP 4 — Agenda Editorial + Alertas
> Admin recebe alerta de novos itens pendentes.

- [ ] Badge/contador de pendentes no sidebar do platform
- [ ] Notificação in-app para admin ao final de cada job (N corridas, M notícias novas)
- [ ] Filtros por tier, estado, fonte, data na tela de revisão
- [ ] Export CSV das descobertas

---

## Fila de Implementação

| # | Item | MVP | Status |
|---|------|-----|--------|
| 1 | Scaffold FastAPI + health ✅ | — | ✅ |
| 2 | Schema Prisma: ContentSource + DiscoveryRun + DiscoveredRace | 1 | 📋 |
| 3 | Parser Ticket Sports | 1 | 📋 |
| 4 | Parser Minhas Inscrições | 1 | 📋 |
| 5 | Deduplicação + save como NEW | 1 | 📋 |
| 6 | Endpoint POST /jobs/races/run | 1 | 📋 |
| 7 | Tela /platform/content-radar (corridas) no rp-frontend | 1 | 📋 |
| 8 | Ação "Aprovar → criar RaceEvent" | 1 | 📋 |
| 9 | Classificação tier por IA (OpenAI) | 2 | 📋 |
| 10 | CRUD de fontes pela UI | 2 | 📋 |
| 11 | APScheduler diário | 2 | 📋 |
| 12 | Schema Prisma: DiscoveredNews | 3 | 📋 |
| 13 | Parser RSS notícias | 3 | 📋 |
| 14 | IA gera resumo de notícia | 3 | 📋 |
| 15 | Tela /platform/content-radar (notícias) | 3 | 📋 |
| 16 | Badge de pendentes + alertas admin | 4 | 📋 |

---

## Dependências entre Repos

- **rp-content-service** descobre e salva no banco.
- **rp-frontend** (Prisma) gerencia as migrations dos novos modelos.
- **rp-frontend** (`/platform/content-radar`) é a interface de revisão e publicação.
- Aprovação de corrida → cria `RaceEvent` via Prisma no mesmo banco.
- Aprovação de notícia → cria `NewsPost`/`OrganizationPost` global.

---

## Cuidados de Segurança / Operação

- Rate limit por fonte: máx 1 req/s, delay aleatório entre páginas.
- Timeout por job: máx 10 min, registrar erro parcial.
- Rodar primeiros jobs manualmente via endpoint antes de ativar o scheduler.
- Não logar conteúdo completo de scraping (payload grande → banco, não log).
- Monitorar `ContentDiscoveryRun.errors` na tela de histórico.
