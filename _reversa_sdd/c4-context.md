# C4 Contexto — Api_Sodex_Trader

Diagrama de contexto de nível 1 mostrando as interações externas do sistema.

```mermaid
graph TB
    subgraph "Ambiente Local"
        User((Trader))
        System[Api_Sodex_Trader]
        Logs[(Arquivos de Log / JSON)]
    end

    subgraph "Sistemas Externos"
        Sodex[Sodex API\nTrading & Accounts]
        Binance[Binance API\nMarket Intel]
    end

    User -->|Analisa Performance| System
    System -->|Lê/Escreve Status| Logs
    System -->|Assina e Envia Ordens| Sodex
    System -->|Consulta Preço e Sinais| Binance
    System -->|Streaming de Dados| User
```

## Relacionamentos

| De | Para | Protocolo | Descrição |
| :--- | :--- | :--- | :--- |
| `System` | `Sodex` | HTTPS / EIP-712 | Execução de trades e consulta de saldo |
| `System` | `Binance` | HTTPS | Coleta de CVD, Funding e EMAs de referência |
| `User` | `System` | WebSocket | Monitoramento em tempo real via Browser |
| `System` | `Logs` | File System | Persistência de histórico de trades e SOPoints |
