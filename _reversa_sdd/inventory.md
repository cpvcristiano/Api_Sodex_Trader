# Inventário de Arquivos — Api_Sodex_Trader

## Estrutura de Pastas

```text
/ (Root)
├── dashboard/           # Interface web e visualização
│   ├── __init__.py
│   ├── index.html
│   └── server.py
├── sodex/               # Cliente principal da API Sodex
│   ├── __init__.py
│   ├── client.py
│   ├── models.py
│   └── signing.py
├── strategy/            # Estratégias de trading
│   ├── __init__.py
│   ├── scalper.py
│   └── tracker.py
├── .env                 # Credenciais locais (ignorado pelo git)
├── .gitignore           # Configuração de exclusão do git
├── config.py            # Configurações globais e carregamento de env
├── main.py              # Ponto de entrada principal do robô
├── README.md            # Documentação inicial
├── requirements.txt     # Dependências Python
├── run_bot.py           # Script de execução do bot
├── run_dashboard.py     # Script de execução do dashboard
└── sopoints.json        # Armazenamento de dados/pontos (cache local)
```

## Resumo por Tipo de Arquivo

- **Python (.py):** 13 arquivos (Core logic)
- **HTML (.html):** 1 arquivo (Frontend dashboard)
- **JSON (.json):** 1 arquivo (Data storage)
- **Markdown (.md):** 1 arquivo (Documentation)

## Entry Points

- `main.py`: Orquestrador principal.
- `run_bot.py`: Wrapper para execução do robô.
- `run_dashboard.py`: Inicia o servidor do dashboard.
- `dashboard/server.py`: Servidor backend para o dashboard.
