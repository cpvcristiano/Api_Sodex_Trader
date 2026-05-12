# SDD — Trading Strategy (Scalper)

## 1. Visão Geral
Cérebro do sistema responsável por analisar o mercado e executar trades automáticos de alta frequência (scalping) com o objetivo de gerar volume para airdrops.

## 2. Responsabilidades
- 🟢 **Análise Técnica**: Calcular indicadores EMA 9 e 17 em múltiplos timeframes (1m e 5m).
- 🟢 **Confluência SMC**: Validar se o preço está em zonas de desconto (para Long) ou premium (para Short) dentro do range de 5 minutos.
- 🟢 **Gestão de Ordens**: Orquestrar a abertura de posições (Limit) e o fechamento (TP/SL).
- 🟢 **Proteção de Capital**: Implementar travas de perda diária e ajuste de breakeven automático.

## 3. Regras de Negócio Associadas
- 🟢 **Sizing**: Operar sempre com 25% da margem disponível em cada trade.
- 🟢 **Relação R:R**: Alvos fixos de $2.00 (TP) e $0.50 (SL), resultando em 1:4.
- 🟢 **Ajuste de BE**: Mover o Stop Loss para o preço de entrada assim que o lucro atingir 50% do alvo de TP ($1.00 de lucro latente).
- 🟢 **Interrupção Diária**: Parar o bot se a perda acumulada no dia exceder $3.00.

## 4. Fluxo Principal
1. O bot monitora o mercado via polling.
2. Quando as EMAs de 5m e 1m alinham na mesma direção e o SMC confirma a zona, uma ordem de entrada é enviada.
3. Se preenchida, o bot envia imediatamente ordens de TP (Limit) e SL (Stop Market).
4. O bot monitora a posição a cada 2s para gerir o Breakeven ou fechar por timeout.

## 5. Critérios de Aceitação (Happy Path)
- **Cenário**: Execução de Trade Completo com Lucro
  - **Dado** que a tendência de 5m é de alta e o preço está em zona de desconto.
  - **Quando** a EMA9 cruzar acima da EMA17 no gráfico de 1m.
  - **Então** o bot deve abrir um LONG, colocar as ordens de proteção e fechar a posição ao atingir o alvo de $2.00.
