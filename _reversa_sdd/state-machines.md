# Máquinas de Estado — Api_Sodex_Trader

Este documento descreve o ciclo de vida das operações e estados do robô.

## Ciclo de Vida do Trade

O robô segue uma sequência rigorosa para cada operação, garantindo que o risco seja controlado e o volume seja contabilizado.

```mermaid
state_diagram
    [*] --> SCANNING : Início do Bot
    
    state SCANNING {
        [*] --> ANALYZING_5M
        ANALYZING_5M --> ANALYZING_1M : Tendência Confirmada
        ANALYZING_1M --> ANALYZING_SMC : Momento Confirmado
        ANALYZING_SMC --> SCANNING : Fora da Zona
    }
    
    SCANNING --> ENTERING : Confluência Total
    
    state ENTERING {
        [*] --> SEND_LIMIT_ORDER
        SEND_LIMIT_ORDER --> WAITING_FILL
        WAITING_FILL --> CANCEL_ORDER : Timeout de Entrada
    }
    
    ENTERING --> IN_POSITION : Ordem Executada (Fill)
    CANCEL_ORDER --> SCANNING
    
    state IN_POSITION {
        [*] --> SET_TP_SL
        SET_TP_SL --> MONITORING
        MONITORING --> ADJUST_BE : Lucro > 50% TP
        MONITORING --> EXITING : Preço atingiu TP/SL
        MONITORING --> EXITING : Timeout de Posição (5m)
        MONITORING --> EXITING : PnL Negativo por 90s
        ADJUST_BE --> MONITORING
    }
    
    EXITING --> COOLDOWN
    COOLDOWN --> SCANNING : Aguarda Poll Delay
```

## Estados de Ordem (Sodex API)

Mapeamento baseado no enum `OrderStatus` em `sodex/models.py`.

| Estado | Significado | Próximos Estados Possíveis |
| :--- | :--- | :--- |
| `NEW` | Ordem enviada e aceita pelo livro | `PARTIALLY_FILLED`, `FILLED`, `CANCELED` |
| `PARTIALLY_FILLED` | Execução parcial iniciada | `FILLED`, `CANCELED` |
| `FILLED` | Ordem totalmente executada | Final |
| `CANCELED` | Cancelada pelo usuário ou sistema | Final |
| `TRIGGERED` | Condição de Stop/Trigger atingida | `NEW` (em ordens Stop Market) |

## Regras de Transição (Posição)

1.  **Breakeven**: A transição para o estado de Breakeven (`ADJUST_BE`) é irreversível para o trade atual; o Stop Loss nunca é movido para trás.
2.  **Timeout**: Se a posição durar mais de 300 segundos (5 minutos), o bot força a saída a mercado, independentemente do PnL atual, para garantir liquidez para o próximo trade.
