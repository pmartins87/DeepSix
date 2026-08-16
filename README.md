# DeepSix

DeepSix é o projeto de estratégia para **Poker Cash Game 6+ / Short Deck**, desenvolvido para obter a melhor força de jogo possível dentro de um orçamento computacional realista.

## Princípio central

O objetivo **não é resolver o 6+ perfeitamente** nem provar equilíbrio exato do jogo completo.

O objetivo é:

> **construir a melhor estratégia que conseguirmos obter, validar e executar com segurança dentro das nossas possibilidades reais de hardware e tempo.**

O orçamento de referência é **um processador Ryzen 9 trabalhando continuamente por semanas ou meses**, com possibilidade de usar armazenamento e pré-computação extensivos, mas sem assumir clusters, GPUs de datacenter ou recursos computacionais irreais para o projeto.

Essa filosofia é diferente da adotada em jogos muito menores, como All-in or Fold, onde uma aproximação extremamente próxima do ótimo pode ser atingível dentro do orçamento disponível. Em DeepSix, por causa da árvore multi-street, sizings, stacks e jogo multiway, aceitaremos abstração e aproximação quando elas produzirem uma estratégia melhor dentro do mesmo orçamento.

## Critério de sucesso

DeepSix será julgado por **força prática e robustez**, não por perfeição teórica.

Isso implica:

- nunca gastar enorme capacidade computacional perseguindo precisão irrelevante enquanto regiões importantes do jogo continuam mal treinadas;
- preferir uma abstração bem escolhida e profundamente treinada a uma árvore quase completa e superficial;
- usar invariâncias matemáticas e canonicalização para que capacidade de treino não seja desperdiçada aprendendo equivalências triviais;
- concentrar amostras e refinamento onde o erro estratégico ou o impacto em EV é maior;
- validar regras, evaluator, pot accounting e transições de estado antes de aumentar a complexidade da rede/solver;
- manter versões simples como baselines e só aceitar arquiteturas mais pesadas quando houver ganho medido;
- usar dados, testes adversariais e benchmarks para decidir entre alternativas, sem assumir que a arquitetura mais sofisticada necessariamente será melhor.

## Arquitetura do projeto

DeepSix terá quatro blocos deliberadamente separados:

1. **DeepSix Core** — regras, deck, evaluator, pot accounting, ação legal, canonicalização e estado estratégico. É a fonte matemática de verdade.
2. **Trainer/Solver** — geração de experiência, CFR/regret/value/policy e demais técnicas que forem vencendo os benchmarks no Ryzen 9.
3. **OpenHoldem6Plus** — fork exclusivo do OpenHoldem para 6+. Não precisa preservar compatibilidade estratégica com Hold'em 52-card, AoF ou OFC. Sua função principal será observar a mesa, formar um estado confiável, consultar o DeepSix e executar a ação correta.
4. **Validation/Replay** — testes, replays, fuzzing, auditoria de invariâncias e comparação runtime ↔ engine.

### Decisão estrutural: OpenHoldem exclusivo para 6+

Não vamos acrescentar o 6+ como mais um conjunto de exceções dentro do OpenHoldem usado pelos outros projetos. O DeepSix terá uma **versão própria do OpenHoldem**, com nome/build/runtime próprios.

Isso permite:

- remover ou desabilitar premissas de Hold'em 52-card que seriam perigosas no Short Deck;
- substituir evaluator/equity/handrank sem medo de quebrar DeepKK, SpinCore ou outros runtimes;
- tratar ante e button blind como conceitos nativos, em vez de fingir que são SB/BB;
- criar símbolos e logs específicos de Short Deck;
- evoluir a máquina de estados e o autoplayer de acordo com as necessidades reais do DeepSix;
- manter testes de regressão independentes.

O fork do OpenHoldem começa **em paralelo** ao núcleo matemático. A integração da política treinada ocorre mais tarde, mas não deixaremos para descobrir problemas de scraping, posições, forced bets ou bet sizing somente no fim do projeto.

## Escopo inicial

1. Formalizar exatamente as regras do 6+ alvo.
2. Implementar e testar um motor Short Deck de 36 cartas.
3. Implementar evaluator correto, incluindo a ordenação de mãos da variante e a sequência A-6-7-8-9 quando aplicável.
4. Criar representação canônica de cartas, boards, suits, posições, stacks, potes e histórico de ações.
5. Iniciar o fork **OpenHoldem6Plus**, preservando o que é útil do scraper/autoplayer e isolando tudo que assume 52 cartas, SB/BB ou rankings tradicionais.
6. Construir um ambiente de jogo determinístico e auditável.
7. Definir uma abstração de ações compatível com o orçamento computacional.
8. Produzir uma estratégia-base treinável em um Ryzen 9.
9. Medir estabilidade, qualidade e ganho marginal por custo de treino.
10. Refinar adaptativamente regiões de maior impacto e integrar somente políticas validadas ao runtime.

## Filosofia de engenharia

### Correção antes de escala

Uma run de meses sobre uma representação errada é pior que uma run curta sobre um modelo correto. Deck, ranking, payouts, rake, stacks, ação legal, terminalidade e canonicalização devem possuir testes independentes antes de treino pesado.

### Eficiência representa força

Eliminar redundâncias não serve apenas para acelerar o mesmo treino. Toda capacidade liberada deve, quando útil, ser convertida em **mais conhecimento estratégico real**: mais estados, melhores abstrações, maior capacidade do modelo, mais iterações ou refinamento dirigido.

### Melhor possível, não perfeito

O projeto não terá um gate artificial de “GTO completo”. O roadmap deverá evoluir enquanto houver uma forma mensurável de converter o orçamento disponível em uma estratégia melhor.

### Evidência acima de intuição

Toda mudança relevante de encoder, arquitetura, loss, sampling, abstraction ou política deverá ser comparada contra baselines em testes reproduzíveis. Uma V2 conceitualmente mais elegante não será promovida apenas por parecer superior; ao mesmo tempo, resultados surpreendentes serão auditados para descartar viés de teste, bug ou desperdício de capacidade.

### Sem compatibilidade falsa

Quando um conceito legado do OpenHoldem não possuir a mesma semântica em 6+, ele não será reaproveitado apenas para evitar mudanças. Compatibilidade aparente é mais perigosa do que uma quebra explícita. Símbolos inválidos devem ser substituídos, desabilitados ou marcados como incompatíveis.

## Estado atual

**Fase 0 — fundação do projeto.**

- repositório criado;
- princípio de otimização definido;
- decisão por um fork exclusivo **OpenHoldem6Plus** registrada;
- auditoria inicial do código-fonte legado identificou os principais pontos 52-card/SB-BB que precisam ser isolados.

Próximo gate: congelar as regras do jogo e construir, em paralelo, o primeiro núcleo matemático Short Deck e o esqueleto seguro do OpenHoldem6Plus.
