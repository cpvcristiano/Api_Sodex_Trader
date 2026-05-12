# Defaults de `--auto`

Quando o usuário invoca `/reversa-migrate --auto`, o orquestrador pula pausas humanas e aplica estes defaults. Antes de iniciar, o aviso ao usuário lista cada um deles. Cada item auto-aplicado é registrado em `ambiguity_log.md` com tag `auto-decidido` para revisão posterior.

## Paradigm Advisor
- Escolha **opção 1: adotar paradigma natural da stack alvo**.
- `derived_appetite` = `transformational`.

## Curator
- Itens DECISÃO HUMANA são marcados como pendentes em `ambiguity_log.md` e não bloqueiam o pipeline.
- Itens 🟡 INFERIDOS → MIGRAR (com nota "validar no agente de codificação").
- Itens 🔴 LACUNA e ⚠️ AMBÍGUOS → DESCARTAR com nota explícita "auto-descartado, requer revisão".

## Strategist
- Adota a estratégia marcada como **recomendada**.
- Riscos `crítico` que dependeriam de owner humano ficam com `owner = "a definir"` em `risk_register.md`.

## Designer
- Aprova a primeira proposta de arquitetura, sem iteração.
- Bounded contexts, eventos e ADRs são aceitos como propostos.

## Inspector
- Usa critérios de paridade derivados diretamente do paradigma escolhido (ver `parity-coverage-matrix.md` no agente).
- Não negocia critério "paridade aceita" com o usuário.

## Modificações manuais detectadas
- Adota **opção (a)**: preservar a versão modificada manualmente e abortar regeneração desse artefato. Nunca destrói trabalho humano.

## Aviso obrigatório

Sempre antes de iniciar `--auto`, apresentar:

> "⚠️ Modo `--auto` ativado. Os defaults abaixo serão aplicados sem pausa para confirmação:
> - Paradigm Advisor: adotar paradigma natural da stack (transformacional).
> - Curator: itens ⚠️/🔴 serão DESCARTADOS com nota; 🟡 serão MIGRADOS com nota.
> - Strategist: estratégia recomendada será adotada.
> - Designer: primeira proposta de arquitetura será aceita.
> - Inspector: critérios de paridade derivados do paradigma sem ajuste interativo.
>
> O `handoff.md` final destacará todos os itens auto-decididos para revisão posterior.
> Confirma? (s/N)"
