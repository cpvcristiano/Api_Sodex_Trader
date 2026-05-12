# Domínio de Negócio — Api_Sodex_Trader

Este documento descreve o vocabulário, as regras e as intenções de negócio do projeto.

## Glossário de Domínio

- **Scalping**: Estratégia de trading de alta frequência que busca lucros pequenos em movimentos rápidos de preço.
- **Notional**: O valor total de uma posição em dólares (quantidade * preço).
- **Margem**: O capital utilizado como garantia para abrir uma posição alavancada.
- **SMC (Smart Money Concepts)**: Metodologia de análise técnica que tenta identificar onde grandes instituições estão operando (Order Blocks, FVG).
- **Order Block (OB)**: Uma zona de preço onde houve uma forte reação do mercado, indicando presença de oferta ou demanda institucional.
- **FVG (Fair Value Gap)**: Desequilíbrio de preço que tende a ser preenchido pelo mercado.
- **Breakeven (BE)**: Ajustar o Stop Loss para o preço de entrada para garantir que o trade não resulte em perda.
- **Airdrop SOSO**: O objetivo primário deste bot é gerar volume de negociação na exchange Sodex para qualificação em campanhas de airdrop do token SOSO.

## Regras de Negócio Centrais

### 1. Seleção de Ativos e Alavancagem
- 🟢 **CONFIRMADO**: O bot opera exclusivamente o par **BTC-USD** (Perpetuals).
- 🟢 **CONFIRMADO**: Utiliza a alavancagem máxima permitida para o ativo na exchange (**25x**).

### 2. Gestão de Risco e Dimensionamento
- 🟢 **CONFIRMADO**: Cada operação utiliza **25% da margem disponível**.
- 🟢 **CONFIRMADO**: Somente **uma posição aberta por vez**.
- 🟢 **CONFIRMADO**: **Take Profit (TP)** alvo fixo de **$2.00**.
- 🟢 **CONFIRMADO**: **Stop Loss (SL)** alvo fixo de **$0.50**.
- 🟢 **CONFIRMADO**: Proporção Risco:Retorno de **1:4**.

### 3. Dinâmica de Execução
- 🟢 **CONFIRMADO**: Entradas são feitas via ordens **LIMIT** para reduzir o pagamento de taxas (Maker).
- 🟢 **CONFIRMADO**: Saídas de emergência ou timeout são feitas via ordens **MARKET** (Taker).
- 🟡 **INFERIDO**: O bot prioriza a geração de volume sobre o lucro nominal, aceitando um win rate ligeiramente inferior desde que o volume acumulado cresça.

### 4. Metas e Limites
- 🟢 **CONFIRMADO**: Meta semanal de volume: **$100.000,00**.
- 🟢 **CONFIRMADO**: Limite de perda diária: **$3,00**. Se atingido, o bot interrompe as operações até o próximo dia.
- 🟡 **INFERIDO**: O bot opera 24/7, exceto se houver uma configuração específica de `stop_hour_utc`.

## Intenções Técnicas (Implícitas)
- **Latência**: O bot realiza polling a cada 2-3 segundos, indicando uma necessidade de reação rápida, mas limitada pela natureza da API REST.
- **Autonomia**: O sistema foi desenhado para rodar sem supervisão humana, com mecanismos de failsafe (timeouts) para evitar posições presas em caso de falha de conexão.
