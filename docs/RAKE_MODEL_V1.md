# DeepSix — Rake Model v1

## Objetivo

Rake altera diretamente a utilidade do cash game e, portanto, não pode entrar no trainer como uma aproximação implícita. A v1 implementa apenas a parte que conseguimos representar **exatamente** com parâmetros explícitos e mantém arredondamento/timing do cliente fora do Core até existir evidência real.

## Fatos publicados usados como referência

Na página oficial de rake da KKPoker consultada durante a construção desta versão, a seção de 6+ publica:

- rake percentual de 3%;
- ausência de rake se a mão termina preflop;
- ausência de rake para potes no limite publicado como `5BB` ou abaixo;
- caps expressos em antes: 3 antes nas stakes de ante 0.02 até 2 e 2 antes nas stakes 5 e 10.

A mesma página descreve a variante 6+ como ante-based e sem blinds, com o Button colocando dois antes. Por isso a expressão `5BB` no limiar de small pot não é convertida automaticamente pelo Core. A hipótese `1 BB = button blind = 2 antes`, que produziria threshold de 10 antes, continua sendo **hipótese de integração** até Hand Review/captura real confirmar a cobrança.

A página geral também publica redução de rake em mesas com até três jogadores. Como a seção específica de 6+ não repete explicitamente essa frase, a v1 não ativa essa redução automaticamente: existe um multiplicador configurável, mas seu valor default é 1.

Fonte de referência desta especificação: página oficial KKPoker `Rake Information`, versão observada em 16/08/2026 (a própria página indica atualização de percentuais/caps em 16/05/2024).

## Representação exata

`deepsix_core.rake` usa:

- pot e caps em unidades inteiras exatas da mesa;
- percentuais como `fractions.Fraction`;
- cap aplicado sobre o valor percentual exato;
- resultado de rake e net pot mantidos como `Fraction`.

Nenhum `round()`, floor, ceil ou conversão para float ocorre no caminho matemático.

## Separação de responsabilidades

`compute_exact_rake()` resolve somente:

1. isenção preflop configurada;
2. limiar de small pot configurado e inclusivo;
3. percentual exato;
4. multiplicador explícito de table size, se o chamador decidir habilitá-lo;
5. cap exato.

A função **não** resolve:

- qual unidade monetária mínima o cliente usa para debitar rake;
- se o rake fracionário é arredondado, truncado ou acumulado;
- em qual instante o pot visual já aparece líquido;
- como rake é distribuído entre main pot e side pots;
- se o limiar publicado como `5BB` significa exatamente 10 antes no 6+;
- se a regra geral de half rake em mesa <=3 jogadores é aplicada ao 6+;
- PVI/rakeback, jackpot ou atribuição individual de rake.

Essas camadas serão integradas somente após evidência ou como configurações explicitamente experimentais.

## Helper Short Deck

`shortdeck_percentage_cap_config()` converte somente múltiplos **explicitamente fornecidos** de ante para unidades da mesa.

Exemplo conceitual:

```text
ante_units = 10
cap_antes = 3
no_rake_threshold_antes = 10   # somente se/quanto isso estiver congelado
```

produz:

```text
cap_units = 30
threshold_units = 100
rate = 3/100
```

Se o threshold ainda não estiver resolvido, o chamador deve passar `None`; a API não inventa uma interpretação para `BB`.

## Gates

A suíte testa:

- no-rake preflop;
- threshold inclusivo;
- 3% como fração exata;
- cap antes de qualquer arredondamento;
- identificação de resultados que ainda precisam de rounding;
- multiplicador short-handed somente quando explicitamente configurado;
- helper em múltiplos de ante;
- threshold deliberadamente não resolvido;
- rejeição de taxas, caps, multiplicadores e valores inválidos.

## Próxima etapa

Depois das capturas reais, será criada uma política versionada de `ClientRakeRounding` e, se possível, um oracle de Hand Review:

```text
gross pot observado
→ exact rake v1
→ client rounding policy
→ net pot esperado
→ comparação byte/valor com replay real
```

Somente depois desse gate o rake líquido deverá participar dos targets econômicos do trainer principal.
