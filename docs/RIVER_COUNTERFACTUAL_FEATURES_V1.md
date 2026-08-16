# DeepSix — River Counterfactual-Value Features v1

## Objetivo

As primeiras abstrações privadas do DeepSix descrevem a mão por propriedades de showdown:

- equity contra o range configurado;
- equity contra o universo compatível;
- nutness;
- blockers do range e das mãos que venceriam o Hero.

Essas features são úteis, mas ainda são descrições **das cartas**. A pergunta mais diretamente ligada à estratégia é outra:

> duas mãos privadas atribuem valores parecidos às ações disponíveis nos mesmos infosets?

`deepsix_trainer/river_counterfactual_features.py` cria um primeiro baseline auditável para essa pergunta.

## Jogo usado

A feature é calculada sobre a árvore river já gated de `multi-size + one-raise`:

- sem bet enfrentada: CHECK ou um dos sizings iniciais;
- enfrentando bet: FOLD / CALL / RAISE_TO;
- enfrentando o primeiro raise: FOLD / CALL;
- sem re-raise.

Board, ranges, blockers, chance, evaluator Short Deck e terminal utilities continuam exatos.

## Reference policy

A v1 usa uma política de continuação **uniforme** em todos os infosets futuros.

Isso é deliberado. A feature não é treinada contra a mesma política que depois será julgada, evitando transformar o primeiro baseline em um mecanismo circular difícil de auditar.

A política uniforme não é tratada como boa estratégia. Ela é apenas uma régua fixa e reproduzível para medir como cada mão responde à geometria da árvore de ações.

## Counterfactual action values

Para uma mão privada exata `h`, um infoset `I` do jogador `i` e uma ação legal `a`, calculamos o valor de:

```text
forçar a ação a em I
  -> seguir a reference policy uniforme em todas as decisões futuras
  -> integrar exatamente todos os deals compatíveis com h
```

Em forma conceitual:

```text
Q_i(h, I, a)
  = Σ_d w(d | h, I) * U_i(d, I+a ; π_ref)
```

onde o peso counterfactual ignora o reach anterior do próprio jogador e preserva chance + reach do adversário.

Na reference policy uniforme, para um mesmo histórico público `I`, a probabilidade das ações anteriores do adversário é independente da mão privada dele. Esse fator é igual para todos os deals compatíveis e cancela ao normalizar. Portanto a implementação v1 pode usar diretamente as probabilidades de chance condicionadas à mão exata sem aproximar a distribuição.

A convenção de utilidade é sempre do jogador descrito pela feature: valor maior é melhor tanto para P0 quanto para P1.

## Vetor da mão

Para cada mão, percorremos **todos os infosets daquele jogador** em ordem canônica e concatenamos os valores de todas as ações legais.

Cada valor é dividido pelo pot da fixture:

```text
normalized_cfv = Q_i / pot
```

Isso remove escala nominal de fichas entre fixtures sem remover diferenças relativas entre ações.

A dimensão do vetor é fixa dentro do mesmo jogador/jogo de ação. Mãos diferentes não podem mudar a aridade ou a ordem das ações.

## Bucketing: deterministic k-medoids

`cfv_kmedoids_bucket_map` agrupa os vetores exatos usando distância Euclidiana quadrática e k-medoids determinístico.

A inicialização é farthest-first:

1. primeiro medoid = mão com maior distância quadrática total para a população;
2. próximos medoids = mãos que maximizam distância ao medoid mais próximo;
3. atualização PAM-style escolhe, em cada cluster, a mão que minimiza a distância total às demais;
4. empates são resolvidos pela ordem canônica das cartas.

Quando o número solicitado de buckets é pelo menos o número de mãos, o builder devolve identidade exata.

O uso de medoids, em vez de centroides artificiais, mantém todo representante como uma mão real e facilita auditoria.

## Gate estratégico

O bucket só é usado durante o CFR.

Depois:

```text
bucket policy
  -> expandir para cada combo exato
  -> Dynamic Exact Best Response no jogo NÃO abstraído
```

Assim, o CFV feature space não consegue esconder a informação que perdeu. Se duas mãos foram agrupadas de forma ruim, a exploitability exata original aumenta.

## Gates unitários

A suíte exige atualmente:

- cobertura de todas as mãos configuradas;
- vetores finitos e dimensão estável;
- um spot construído analiticamente em que uma mão Broadway prefere CALL a FOLD contra raise, enquanto uma mão high-card prefere FOLD a CALL;
- determinismo do k-medoids;
- respeito ao número pedido de buckets;
- degeneração para identity quando `k >= número de mãos`;
- rejeição de jogador, mão ou quantidade de buckets inválidos.

## River Benchmark Battery v3

A bateria de state abstraction agora compara, nas mesmas fixtures e larguras:

- identity;
- conditional-equity quantiles;
- equity + nutness + blocker Borda quantiles;
- **uniform-reference CFV k-medoids**;
- showdown category;
- single bucket.

Além de exploitability/pot, nós e throughput, a v3 registra separadamente:

```text
mapping_build_seconds
```

Isso é importante porque uma feature mais rica pode ser barata no treino depois de construída, mas cara para pré-computar.

O analyzer Ryzen reporta esse custo separadamente; ele ainda não entra automaticamente na fronteira de Pareto porque é um custo one-shot que pode amortizar de modo muito diferente de throughput de CFR.

## Limites da v1

A v1 não prova que CFV k-medoids é melhor que equity ou blockers.

Limitações explícitas:

- reference policy uniforme não representa ranges de ação realistas;
- o vetor é específico da árvore river atual;
- não existe informação multi-street;
- k-medoids usa distância Euclidiana simples;
- nenhuma ponderação foi ajustada para maximizar resultado em uma fixture;
- ranges da bateria continuam sintéticos até existirem estados/replays reais.

A promoção só pode ocorrer se os resultados no Ryzen 9 mostrarem vantagem reproduzível de erro estratégico por custo computacional.

## Próxima evolução possível

Se a v1 mostrar sinal útil, as extensões naturais são:

1. reference policies mais informativas, mas congeladas e independentes do policy-under-test;
2. CFVs condicionados a distribuições derivadas de replay real;
3. distâncias aprendidas ou clustering treinado contra erro medido pela exact BR;
4. extensão para public states anteriores ao river;
5. comparação a wall-clock igual, não apenas a número igual de iterações.

Nenhuma dessas extensões deve substituir os baselines identity/equity atuais; elas devem competir contra eles sob o mesmo oracle.
