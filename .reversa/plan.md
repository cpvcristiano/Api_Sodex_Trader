# Plano de Exploração — Api_Sodex_Trader

> Criado pelo Reversa em 2026-05-03
> Marque cada tarefa com ✅ quando concluída.
> Você pode editar este plano antes de iniciar: adicione, remova ou reordene tarefas conforme necessário.

---

## Fase 1: Reconhecimento 🔍

- [ ] **Scout** — Mapeamento de estrutura de pastas e tecnologias
- [ ] **Scout** — Análise de dependências e gerenciadores de pacotes
- [ ] **Scout** — Identificação de entry points, CI/CD e configurações

## Fase 2: Escavação 🏗️

- [ ] **Archaeologist** — Análise do módulo `sodex`
- [ ] **Archaeologist** — Análise do módulo `strategy`
- [ ] **Archaeologist** — Análise do módulo `dashboard`

## Fase 3: Interpretação 🧠

- [ ] **Detetive** — Arqueologia Git e ADRs retroativos
- [ ] **Detetive** — Regras de negócio implícitas e máquinas de estado
- [ ] **Detetive** — Matriz de permissões (RBAC/ACL)
- [ ] **Arquiteto** — Diagramas C4 (Contexto, Containers, Componentes)
- [ ] **Arquiteto** — ERD completo e integrações externas
- [ ] **Arquiteto** — Spec Impact Matrix

## Fase 4: Geração 📝

- [ ] **Redator** — Specs SDD por componente
- [ ] **Redator** — OpenAPI (se aplicável)
- [ ] **Redator** — User Stories (se aplicável)
- [ ] **Redator** — Code/Spec Matrix

## Fase 5: Revisão ✅

- [ ] **Revisor** — Revisão cruzada de specs
- [ ] **Revisor** — Resolução de lacunas com o usuário
- [ ] **Revisor** — Relatório de confiança final

---

## Agentes Independentes

> Execute estes agentes quando os recursos estiverem disponíveis — podem rodar em qualquer fase.

- [ ] **Visor** — Análise de interface via screenshots
- [ ] **Data Master** — Análise completa do banco de dados
- [ ] **Design System** — Extração de tokens de design
- [ ] **Tracer** — Análise dinâmica (requer sistema acessível)

---

## Próximo passo

Após o Time de Descoberta concluir e o `_reversa_sdd/` estar populado, você pode disparar um dos fluxos seguintes:

- `/reversa-migrate`: orquestrador do **Time de Migração** (Paradigm Advisor → Curator → Strategist → Designer → Inspector). Gera as specs do sistema novo. Saída em `_reversa_sdd/migration/`.
- `/reversa-reconstructor`: gera plano bottom-up para reimplementar o software a partir das specs do legado (uma tarefa por sessão).
