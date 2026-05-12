---
schemaVersion: 1
generatedAt: <ISO-8601>
reversa:
  version: "x.y.z"
kind: handoff
producedBy: orchestrator
hash: "sha256:<hash do corpo abaixo do front-matter>"
---

# Handoff para o Agente de Codificação

> Este documento é a porta de entrada para o agente de codificação (Claude Code, Codex, Cursor, Antigravity, etc.) que vai escrever o sistema novo a partir das specs.

## ⚠️ Leitura obrigatória primeiro

1. **`paradigm_decision.md`**, leitura inegociável. O paradigma alvo molda como toda a codificação deve acontecer.

## Ordem de leitura recomendada

1. `paradigm_decision.md` (obrigatório, primeiro)
2. `migration_brief.md`
3. `target_business_rules.md`
4. `migration_strategy.md`
5. `target_architecture.md`
6. `target_domain_model.md`
7. `target_data_model.md`
8. `data_migration_plan.md`
9. `parity_specs.md` + `parity_tests/`
10. `risk_register.md` + `cutover_plan.md`
11. `discard_log.md` (consultivo)
12. `ambiguity_log.md` (consultivo)

## Lista de artefatos produzidos

| Artefato | Produzido por | Status |
|---|---|---|
| migration_brief.md | orchestrator | criado |
| paradigm_decision.md | paradigm_advisor | criado |
| target_business_rules.md | curator | criado |
| discard_log.md | curator | criado |
| migration_strategy.md | strategist | criado |
| risk_register.md | strategist | criado |
| cutover_plan.md | strategist | criado |
| target_architecture.md | designer | criado |
| target_domain_model.md | designer | criado |
| target_data_model.md | designer | criado |
| data_migration_plan.md | designer | criado |
| parity_specs.md | inspector | criado |
| parity_tests/*.feature | inspector | <N> arquivos |
| ambiguity_log.md | orchestrator | consolidado |

## Bloqueadores para começar a implementação
> Itens que precisam de decisão humana antes do agente de codificação começar.

- <AMB-XXX: descrição curta + onde decidir>
- <ou: nenhum bloqueador, prosseguir>

## Próximos passos para o agente de codificação

1. **Ler `paradigm_decision.md` e internalizar**: o paradigma alvo é <do paradigm_decision>. Toda escolha de código deve honrar esse paradigma.
2. **Configurar o repositório novo** com a stack declarada em `migration_brief.md`.
3. **Implementar bottom-up** seguindo `target_architecture.md` e `target_domain_model.md`:
   - infraestrutura → dados → domínio → aplicação → bordas.
4. **Escrever os testes** a partir de `parity_specs.md` e `parity_tests/*.feature` desde o início.
5. **Para cada componente**, validar que respeita o paradigma escolhido (sinais explícitos em `target_architecture.md § Honra ao paradigma escolhido`).
6. **Para a migração de dados**, seguir `data_migration_plan.md`.
7. **Para o cutover**, seguir `cutover_plan.md` e os critérios go/no-go.

## Itens auto-decididos (apenas se executado em --auto)
> Listar aqui itens cujo default foi aplicado sem confirmação humana. Recomenda-se revisar antes do cutover.

- <ou: pipeline executado em modo interativo, nenhum item auto-decidido>

## Notas finais
<Observações do orquestrador para o agente de codificação.>
