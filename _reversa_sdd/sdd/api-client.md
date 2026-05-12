# SDD — API Client (Sodex)

## 1. Visão Geral
Componente de baixo nível responsável pela comunicação segura com a exchange Sodex, implementando o protocolo de autenticação EIP-712 e abstraindo os endpoints de Spot e Perps.

## 2. Responsabilidades
- 🟢 **Autenticação**: Gerar assinaturas EIP-712 válidas para requisições privadas usando chaves ECDSA.
- 🟢 **Gestão de Sessão**: Manter conexões HTTP persistentes via `requests.Session`.
- 🟢 **Normalização**: Converter tipos de domínio (Enums) para formatos aceitos pela API (inteiros/strings).
- 🟢 **Market Data**: Prover métodos para consulta de preços, orderbook e tickers.

## 3. Regras de Negócio Associadas
- 🟢 **Nonce**: Cada requisição privada deve incluir um `X-API-Nonce` baseado no timestamp Unix em milissegundos.
- 🟢 **Headers**: Toda requisição autenticada deve enviar `X-API-Key` (nome da chave), `X-API-Sign` (assinatura hex) e `X-API-Nonce`.
- 🟢 **Chain ID**: Deve alternar entre Mainnet (286623) e Testnet (138565) conforme configuração.

## 4. Fluxo Principal
1. O cliente recebe uma solicitação de ação (ex: `place_order`).
2. Constrói o payload JSON da ação.
3. Computa o `domainSeparator` e o `structHash` conforme EIP-712.
4. Assina o digest final com a chave privada.
5. Envia a requisição POST com os headers de autenticação.

## 5. Critérios de Aceitação (Happy Path)
- **Cenário**: Consulta de Saldo Privado
  - **Dado** que possuo chaves de API válidas e saldo na exchange.
  - **Quando** eu invocar o método `spot_balances`.
  - **Então** o sistema deve gerar uma assinatura válida, enviá-la nos headers e retornar um objeto contendo os saldos por moeda.
