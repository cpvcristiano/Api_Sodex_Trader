# Perguntas para Validação — Api_Sodex_Trader

Cristiano, encontrei um ponto crítico que precisa da sua confirmação para garantir que o sistema possa ser reimplementado corretamente.

---

### Q1. Rigidez da Ordem dos Campos no EIP-712
No arquivo `sodex/client.py` (linha 276 e 538), há comentários reforçando que a ordem dos campos no dicionário de ordens deve seguir exatamente a definição da struct em Go do SDK original.

**Pergunta:** Essa restrição de ordem é imposta pelo backend da Sodex para o cálculo do hash do payload? Se sim, precisamos documentar a ordem exata para cada tipo de ação (Spot vs Perps) na especificação.

**Sua Resposta:** 
[ ] Sim, a ordem é obrigatória.
[ ] Não, o dicionário pode ser em qualquer ordem (o client cuida disso).

---

### Q2. Fonte de Verdade do Volume
O dashboard utiliza tanto o `bot.log` quanto a API `perps_trade_history` para calcular o volume.

**Pergunta:** Em caso de divergência prolongada (ex: log corrompido), a API deve ser considerada a única fonte de verdade absoluta para o progresso do airdrop?

**Sua Resposta:** 
[ ] Sim, API é a verdade absoluta.
[ ] Não, o log é mais detalhado para o dashboard.
