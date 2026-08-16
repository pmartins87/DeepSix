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

## Escopo inicial

1. Formalizar exatamente as regras do 6+ alvo.
2. Implementar e testar um motor Short Deck de 36 cartas.
3. Implementar evaluator correto, incluindo a ordenação de mãos da variante e a sequência A-6-7-8-9 quando aplicável.
4. Criar representação canônica de cartas, boards, suits, posições, stacks, potes e histórico de ações.
5. Construir um ambiente de jogo determinístico e auditável.
6. Definir uma abstração de ações compatível com o orçamento computacional.
7. Produzir uma estratégia-base treinável em um Ryzen 9.
8. Medir estabilidade, qualidade e ganho marginal por custo de treino.
9. Refinar adaptativamente regiões de maior impacto.
10. Somente depois integrar a estratégia ao restante da infraestrutura do projeto.

## Filosofia de engenharia

### Correção antes de escala

Uma run de meses sobre uma representação errada é pior que uma run curta sobre um modelo correto. Deck, ranking, payouts, rake, stacks, ação legal, terminalidade e canonicalização devem possuir testes independentes antes de treino pesado.

### Eficiência representa força

Eliminar redundâncias não serve apenas para acelerar o mesmo treino. Toda capacidade liberada deve, quando útil, ser convertida em **mais conhecimento estratégico real**: mais estados, melhores abstrações, maior capacidade do modelo, mais iterações ou refinamento dirigido.

### Melhor possível, não perfeito

O projeto não terá um gate artificial de “GTO completo”. O roadmap deverá evoluir enquanto houver uma forma mensurável de converter o orçamento disponível em uma estratégia melhor.

### Evidência acima de intuição

Toda mudança relevante de encoder, arquitetura, loss, sampling, abstraction ou política deverá ser comparada contra baselines em testes reproduzíveis. Uma V2 conceitualmente mais elegante não será promovida apenas por parecer superior; ao mesmo tempo, resultados surpreendentes serão auditados para descartar viés de teste, bug ou desperdício de capacidade.

## Estado atual

**Fase 0 — fundação do projeto.**

Repositório criado e princípio de otimização definido. O próximo gate é congelar as regras do jogo e construir o primeiro núcleo matemático Short Deck com testes de referência.
