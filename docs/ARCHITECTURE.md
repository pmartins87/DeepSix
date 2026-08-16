# DeepSix — Arquitetura canônica

## 1. Princípio

DeepSix separa **verdade matemática**, **treinamento** e **runtime de mesa**.

Nenhum componente de UI deve redefinir regras do jogo. Nenhum trainer deve depender de detalhes de scraping. Nenhum símbolo legado do OpenHoldem deve ser tratado como verdade estratégica sem uma equivalência Short Deck explícita.

## 2. Componentes

### 2.1 DeepSix Core

Fonte autoritativa para:

- deck de 36 cartas;
- ranking de mãos;
- evaluator;
- pot accounting;
- rake model;
- side pots;
- ação legal;
- forced bets;
- posições relativas;
- transições de street;
- canonicalização;
- hashing de estado;
- conversão entre estado concreto e abstração estratégica.

O Core deve ser executável/testável sem OpenHoldem.

### 2.2 Trainer/Solver

Consome somente APIs do DeepSix Core.

Responsável por:

- tree traversal/sampling;
- regrets/values/policies;
- neural encoders quando usados;
- replay/reservoir;
- checkpoints;
- validação fora da amostra;
- exportação de uma política versionada.

O Trainer nunca deve importar código do OpenHoldem.

### 2.3 Policy Runtime

Camada leve para inferência.

Entrada:

- estado canônico validado;
- action mask legal;
- versão das regras/economia.

Saída:

- ação abstrata/concreta;
- distribuição de política quando disponível;
- sizing/raise-to;
- policy version;
- state hash;
- reason/diagnostics.

O runtime deve conseguir reproduzir uma decisão offline a partir de um replay.

### 2.4 OpenHoldem6Plus

Fork exclusivo do OpenHoldem.

Responsabilidades:

- conexão à janela;
- tablemap/scraping;
- cartas/board visíveis;
- seats/dealer;
- balances/current bets/pot;
- reconhecimento do Hero e oponentes;
- construção de `TableObservation`;
- detecção de ações observadas;
- validação do estado real;
- chamada ao Policy Runtime;
- execução física de fold/check/call/raise;
- confirmação/log/replay.

Não é responsabilidade do OpenHoldem6Plus calcular estratégia por heurística própria.

### 2.5 Replay/Validation

Mesmo formato de observação usado pelo runtime.

Serve para:

- reproduzir hands sem mesa aberta;
- comparar OH6+ e simulador;
- fuzzing;
- regression tests;
- invariance tests;
- detectar divergência entre versões.

---

## 3. Duas representações de carta, uma fronteira explícita

### OH boundary card id

Para minimizar alterações no scraper, o OpenHoldem6Plus pode continuar armazenando cartas com o ID tradicional do `StdDeck` 52-card.

Isso é apenas transporte.

### DeepSix card id

O Core usará um espaço compacto de 36 cartas:

- ranks válidos: 6,7,8,9,T,J,Q,K,A;
- 4 suits;
- card IDs `0..35`.

Conversão obrigatória:

```text
legacy OH card id
  -> decode rank/suit
  -> reject rank < 6
  -> compact_rank = rank - 6
  -> core_card = suit * 9 + compact_rank
```

A conversão inversa só existe para UI/debug/testes.

Nenhum loop do Core pode iterar 52 cartas.

---

## 4. Estado de mesa neutro

`TableObservation` representa aquilo que foi observado, sem inferir estratégia.

Campos mínimos conceituais:

- observation schema version;
- hand identity/sequence;
- heartbeat/frame sequence;
- street;
- button seat;
- hero seat;
- seats presentes/dealt/active/folded/all-in;
- hole cards conhecidas;
- board;
- stack por seat;
- contribuição atual da street por seat;
- contribuição total da mão por seat, quando reconstruível;
- pot observado;
- ante;
- button blind;
- botões disponíveis;
- valores visíveis de call/min-raise/max-raise quando existirem;
- confidence/invalid reasons por campo crítico.

`TableObservation` não deve possuir `SB`, `BB`, `prwin`, `handrank1326` ou outras interpretações legadas obrigatórias.

---

## 5. Estado canônico estratégico

O Core transforma `TableObservation` validada em `CanonicalState`.

Características:

- seats rotacionados para posição relativa;
- suits canonicalizados;
- flop sem dependência da ordem de apresentação;
- hole cards ordenadas;
- valores monetários normalizados;
- action history explícito;
- stacks e pot consistentes;
- action mask legal;
- state hash estável.

A mesma situação estratégica deve gerar o mesmo estado canônico no Trainer e no OpenHoldem6Plus.

---

## 6. Forced bets

Ante e button blind são conceitos nativos do Core e do runtime.

Não serão rebatizados como `sblind`/`bblind` para satisfazer APIs legadas.

Se alguma rotina de transporte do OpenHoldem exigir um número de compatibilidade, ele deve ficar dentro de um adaptador claramente nomeado e jamais atravessar a fronteira para o Core.

---

## 7. Ações e sizings

O solver trabalha com ações abstratas/concretas definidas pela versão de abstraction.

O Policy Runtime devolve um alvo em semântica inequívoca:

- `FOLD`;
- `CHECK`;
- `CALL`;
- `RAISE_TO(amount)`;
- `ALL_IN` quando tratado explicitamente.

O OpenHoldem6Plus converte isso para clique/teclado.

Nunca usar como contrato externo expressões ambíguas como "bet 2x" sem registrar a base exata da multiplicação.

Todo raise registra:

- requested_raise_to;
- legal_min_raise_to;
- legal_max_raise_to;
- executed_raise_to;
- clipping reason se houver.

---

## 8. Safety contract

O runtime não age se qualquer uma das seguintes condições ocorrer:

- carta inválida 2–5;
- button/hero seat crítico indefinido;
- street inconsistente;
- pot/stacks/call não reconciliáveis acima da tolerância definida;
- action history incompatível;
- state hash impossível de formar;
- policy version incompatível com rules/abstraction version;
- ação retornada ilegal;
- sizing fora dos limites legais;
- estado mudou entre inferência e clique sem revalidação.

Falha segura é **NO_ACTION**, nunca aproximação silenciosa.

---

## 9. Versionamento obrigatório

Toda decisão/replay deve carregar pelo menos:

- `rules_version`;
- `economy_version`;
- `state_schema_version`;
- `canonicalizer_version`;
- `abstraction_version`;
- `policy_version`;
- `oh6plus_build`.

Isso evita misturar experiência/estados de versões semanticamente diferentes.

---

## 10. Regra para mudanças futuras

Uma mudança no OpenHoldem6Plus que altere apenas scraping/transporte não deve mudar o estado canônico de um replay já válido.

Uma mudança que altere regras, action legality, card encoding, pot accounting ou canonicalização exige versionamento correspondente e regressão completa.
