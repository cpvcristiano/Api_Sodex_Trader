# Análise Técnica — Api_Sodex_Trader

Este documento resume a análise técnica profunda realizada nos módulos do projeto.

## 1. Módulo: `sodex` (API Client)

Este módulo é responsável por toda a comunicação com a exchange Sodex, incluindo a autenticação via EIP-712.

### Fluxo de Controle
- **`SodexClient`**: Classe principal que gerencia sessões HTTP e roteia para Spot ou Perps.
- **Assinatura**: Cada requisição privada (POST/DELETE) gera um nonce (timestamp ms) e uma assinatura EIP-712 combinando o `ActionPayload` (tipo de ação + parâmetros) e o `domainSeparator`.
- **Tratamento de Erros**: Utiliza `resp.raise_for_status()` e verifica campos de erro customizados da API Sodex (`code != 0`).

### Estruturas de Dados (Enums)
| Nome | Descrição | Valores Principais |
| :--- | :--- | :--- |
| `OrderSide` | Lado da ordem | BUY (1), SELL (2) |
| `OrderType` | Tipo de execução | LIMIT (1), MARKET (2) |
| `TimeInForce` | Validade da ordem | GTC (1), IOC (3), GTX (4) |
| `OrderModifier` | Modificador de ordem | NORMAL (1), STOP (2), BRACKET (3) |

---

## 2. Módulo: `strategy` (Trading Logic)

Implementa a estratégia de scalping de alta frequência para geração de volume.

### Algoritmos e Lógica
- **Estratégia Híbrida**: 
  - **Tendência**: EMA 9/17 no gráfico de 5 minutos.
  - **Momento**: Confirmação de cruzamento ou alinhamento no gráfico de 1 minuto.
  - **SMC (Smart Money Concepts)**: Filtra entradas baseadas em zonas de Premium/Discount no range de 5 minutos e presença de Order Blocks.
- **Gestão de Risco**:
  - **Trailing Stop Manual**: Move o Stop Loss para o Breakeven quando o lucro atinge 50% do Take Profit.
  - **Fixed Targets**: TP fixo de $2.00 e SL de $0.50 por trade.

### Fluxo de Operação (Resumo)
1. O bot aguarda alinhamento das EMAs em 5m e 1m.
2. Verifica se o preço está em zona favorável via SMC.
3. Coloca ordem LIMIT de entrada (1 tick de agressão).
4. Ao ser executado, coloca simultaneamente TP (Limit) e SL (Stop Market).
5. Monitora a posição para ajuste de BE ou fechamento por timeout (5 min).

---

## 3. Módulo: `dashboard` (Monitoring)

Interface de monitoramento em tempo real do desempenho do bot.

### Funcionalidades
- **Log Parsing**: Lê e interpreta o arquivo `bot.log` via regex para extrair o histórico de trades.
- **WebSocket**: Envia atualizações de preço (BTC-USD), PnL, volume acumulado e status do bot a cada 3 segundos.
- **Volume Sync**: Sincroniza o volume local com o volume real reportado pela API da Sodex para precisão no tracking de airdrop.

---

## Dicionário de Dados (Resumo)

| Entidade | Campos Principais | Tipo | Descrição |
| :--- | :--- | :--- | :--- |
| `Trade` | `id`, `symbol`, `side`, `pnl`, `volume` | Objeto | Registro de uma operação finalizada |
| `ScalpConfig` | `margin_pct`, `leverage`, `tp_usd`, `sl_usd` | Config | Parâmetros operacionais do robô |
| `ActionPayload` | `type`, `params` | JSON | Estrutura para assinatura EIP-712 |
| `SodexState` | `am` (margin), `av` (balance), `P` (positions) | API Resp | Estado da conta retornado pela exchange |
