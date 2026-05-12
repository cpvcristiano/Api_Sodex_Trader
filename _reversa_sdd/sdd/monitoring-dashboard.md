# SDD — Monitoring Dashboard

## 1. Visão Geral
Interface web em tempo real para monitoramento do desempenho do robô, acompanhamento do PnL, volume acumulado e status da estratégia.

## 2. Responsabilidades
- 🟢 **Streaming**: Enviar dados atualizados a cada 3 segundos via WebSocket.
- 🟢 **Análise de Logs**: Interpretar o arquivo `bot.log` para reconstruir o histórico de operações.
- 🟢 **Consolidação**: Somar volumes e taxas para reportar o progresso semanal em direção à meta.
- 🟢 **Interface**: Prover uma visão visual (HTML/JS) com gráficos de preço e histórico de trades.

## 3. Regras de Negócio Associadas
- 🟢 **Cálculo de Volume**: O volume total é a soma do notional de cada entrada e saída (2x por trade completo).
- 🟢 **Sync de Volume**: Permitir a sincronização manual/automática com o volume real reportado pela API Sodex para evitar divergências.
- 🟡 **Insights**: Gerar alertas visuais (Success/Warning/Danger) baseados no win rate recente do robô.

## 4. Fluxo Principal
1. O servidor FastAPI inicia e abre um endpoint WebSocket em `/ws`.
2. Ao conectar, o cliente recebe um snapshot do estado atual.
3. O servidor entra em um loop infinito lendo os logs e consultando o saldo na API Sodex.
4. Os dados são enviados serializados em JSON para o frontend.

## 5. Critérios de Aceitação (Happy Path)
- **Cenário**: Atualização em tempo real do PnL
  - **Dado** que o dashboard está aberto no navegador.
  - **Quando** o robô fecha um trade com lucro de $2.00 e registra no log.
  - **Então** o dashboard deve refletir o novo trade no histórico e atualizar o PnL total em até 5 segundos.
