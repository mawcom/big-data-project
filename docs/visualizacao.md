# Decisões de visualização do painel

Este documento aplica ao painel os conceitos da aula *Visualização de Dados* (Big Data em Python, FACIMP Wyden). Ele serve de roteiro para defender cada visual na apresentação.

- **`/painel`** (versão final): focado em um tema, *principais impactos causados pelo El Niño no Nordeste*. É descrito na primeira parte.
- **`/piloto-real`** (versão exploratória): todos os visuais, com rolagem. É descrito na segunda parte.

# Painel final `/painel`: impactos do El Niño no Nordeste

## Contexto antes de desenhar

- **Tipo de painel:** explanatório, com um único tema e sem poluição visual.
- **Público:** gestores estaduais de defesa civil, recursos hídricos e agricultura do Nordeste.
- **O que ele precisa fazer:** decidir como se preparar para a próxima quadra chuvosa (fev–mai) com um El Niño em curso.
- **Pergunta:** o que mudou na chuva e nos focos de fogo do Nordeste durante o El Niño?
- **Comparação usada em todo o painel:** cada mês do episódio é comparado com a **média do mesmo mês do calendário em anos sem El Niño**. Comparar mai/2023 com mai/2024 e mai/2025, e não com o resto do ano, neutraliza a sazonalidade, que é muito mais forte do que o efeito do ENSO.
- **Episódio:** é detectado nos dados como o último trecho contínuo de meses com fase El Niño (ONI ≥ +0,5 °C). Com 2023–2025, vai de mai/2023 a abr/2024 (12 meses, pico de +2,0 °C em dez/2023).
- **Big Idea (gerada a partir dos dados):** "Nordeste, El Niño de mai/23 a abr/24: +16% de chuva e 0% de focos em relação aos mesmos meses sem El Niño — o episódio não trouxe a seca esperada." A frase muda com o recorte (Nordeste ou estado).

## Tela única por aba (sem rolagem)

Cada aba cabe inteira na janela a partir de 1000 × 600 px; o layout foi verificado em 1366 × 768 e 1715 × 969. O resumo fica fixo e só a área de baixo muda entre as abas. Abaixo disso, o painel volta ao fluxo com rolagem.

```
┌ título · filtro único: Recorte (Nordeste ou estado) ────────────────┐
│ Big Idea                                                             │
│ [Episódio] [Pico ONI] [Chuva vs. normal] [Focos vs. normal]          │
│ Visão geral | Linha do tempo | Por estado | 2026 vs. passado         │
├──────────────────────────────────────────────────────────────────────┤
│ Visão geral:    chuva mês a mês │ mapa (chuva/focos)  │ Leitura      │
│                 focos mês a mês │                     │              │
│ Linha do tempo: ONI, chuva e focos 2023–2025 alinhados, El Niño      │
│                 sombreado                                            │
│ Por estado:     ranking de chuva %  │  ranking de focos %            │
│ 2026 vs. passado: chuva 2026–27 │ erro de cada │ mapa: fev–mai após   │
│                   focos 2026–27 │ regra        │ El Niños fortes      │
└──────────────────────────────────────────────────────────────────────┘
```

- **Paleta da aula** (extraída do PDF da disciplina), em tema claro: fundo neutro `#f5f5f6`, títulos `#2b1055`, texto `#3e3a47`; **roxo `#6a1b9a` = chuva**, **magenta `#d81b60` = focos**, **laranja `#f7941d` = período de El Niño**, cinza-lilás `#d3cfda` = referência (meses sem El Niño). No mapa, a escala é divergente: zero em cinza-lilás, "mais" na cor da métrica (roxo no mapa de chuva, magenta no de focos) e "menos" em cinza escuro `#5f5a6b`. O lado negativo não usa a cor da outra métrica, para roxo significar sempre chuva e magenta sempre focos (similaridade).
- **Um único filtro.** O recorte pode ser escolhido no seletor, no mapa ou nas barras por estado. Clicar de novo no mesmo estado, ou apertar `Esc`, volta ao Nordeste.
- **Cada aba tem um endereço** (`/painel#geral`, `#tempo`, `#estados`, `#2026`), para abrir direto na apresentação. Trocar o `#` com a página aberta também troca a aba, e os botões voltar e avançar do navegador passam pelas abas visitadas.
- **História com começo, meio e fim:** a Big Idea e os KPIs são o começo; os gráficos são o meio; o último item da Leitura, **"O que fazer"**, é a chamada para ação. Ele usa a projeção da aba 2026 para a quadra chuvosa seguinte (média dos El Niños e só os fortes) e o histórico dos municípios depois de El Niños fortes, no recorte escolhido (com um município, o histórico é dele e a projeção é do estado). O texto muda conforme o sinal: abaixo do normal, acima do normal ou sem sinal claro, e sempre manda reavaliar com a previsão sazonal oficial. Só aparece quando `amostras/projecao_el_nino_<ano>/` existe.
- **Laranja só para El Niño:** a etiqueta "Cuidado" da Leitura fica em cinza, e "O que fazer" na cor dos títulos.
- **Foco em municípios (opcional):** escolher um estado aproxima o mapa e pinta os municípios pela variação no El Niño. A chuva aparece em %; os focos aparecem como diferença em número de focos, porque muitos municípios têm poucos focos e o % explode. A escala usa o percentil 95, para um município extremo não apagar os outros, e os estados vizinhos ficam em cinza. Escolher um município, no mapa ou no segundo seletor, foca nele o painel inteiro: frase, KPIs, gráficos e linha do tempo. Um caminho "Nordeste › Estado › Município" sobre o mapa e a tecla `Esc` voltam um nível. Os dados municipais só são carregados quando um estado é escolhido.
- **Recorte pelo endereço:** `/painel?uf=MA&mun=2105302#tempo` abre Imperatriz na aba Linha do tempo, útil para a apresentação.
- **Aba "2026 vs. passado"** (`#2026`): compara o El Niño em curso com o que os El Niños passados previam. Lê `amostras/projecao_el_nino_<ano>/` pela rota `/api/el-nino`; sem essa pasta, a aba mostra o comando que falta rodar.
  - *Chuva e focos 2026–27:* gráfico indexado. O eixo é a diferença para o normal do mês (chuva 1991–2020; focos 2003–2025), então a linha do zero é o normal. Linha colorida = 2026 observado (único destaque), linha cinza = média dos El Niños passados, faixa cinza = entre os El Niños nos meses projetados. A área laranja clara marca a projeção. A diferença fica em mm ou em focos, e não em %, porque o % dispara nos meses secos ou com poucos focos. "Só fortes" (pico ONI ≥ 1,5) fica no tooltip e na nota. O título compara o observado nos meses de El Niño com o que a média previa; a nota traz a projeção do trecho-chave (quadra chuvosa para chuva; nov–dez para focos).
    - *Por que trocou:* a versão anterior (barra cinza + barra colorida + duas linhas laranja + traços de faixa + legenda embaixo) tinha 6 ou 7 elementos e dois destaques disputando o olhar. A aula pede no máximo 4–5 elementos (memória de trabalho), um destaque por visual, rótulo direto (proximidade), linha para evolução no tempo e gráfico indexado no lugar de comparar alturas.
  - *Quanto cada regra errou:* cinco regras fixadas antes de olhar 2026 (média histórica, repetir o ano anterior, repetir o último El Niño, média dos El Niños, média dos fortes). São dois pequenos múltiplos (chuva e focos, mesma escala) em vez de barras agrupadas, cada um ordenado do menor erro para o maior, com só a melhor regra em cor. Nome completo da regra no tooltip.
  - *Mapa:* anomalia de chuva em fev–mai do ano seguinte, média dos El Niños fortes, por município. A nota cita a exceção (2023–24).
  - Segue o recorte do painel; com um município escolhido, os gráficos usam o estado dele.
- **Ficaram fora** a projeção sazonal simples, a tabela, o calendário e o ranking mensal, porque não respondem ao tema. Eles continuam no `/piloto-real`.

## Checklist de defesa por visual

| Visual | Pergunta que responde | Por que este tipo | Destaque pré-atentivo | Honestidade |
|---|---|---|---|---|
| KPIs | Quanto durou, quão forte foi e o que mudou? | "Às vezes o melhor gráfico é um número" | Cor da métrica (roxo = chuva, magenta = focos) | Cada % mostra os dois totais comparados |
| Chuva / focos mês a mês | Em que meses o El Niño se afastou do normal? | Barra colorida (El Niño) dentro de barra cinza (normal), mesmo eixo | Rótulo direto só no mês com maior diferença | Eixo no zero; ONI de cada mês sob o eixo; anos de referência no tooltip |
| Mapa | Onde mudou? (estado → município) | Coroplético divergente: zero em cinza-lilás, mais = cor da métrica, menos = cinza escuro | Estado do recorte com contorno branco | Escala simétrica (−X% a +X%); valor escrito nos estados grandes, tooltip nos pequenos |
| Leitura | O que concluir e o que fazer? | Texto curto calculado | Rótulos coloridos por métrica; "O que fazer" separado por uma linha | Ressalva sempre presente (um episódio só, associação não é causa); a ação cita a faixa da projeção e pede reavaliação com a previsão oficial |
| Linha do tempo | O efeito aparece antes, durante e depois? | Small multiples alinhados no mesmo eixo de meses, sem eixo Y duplo | Barras coloridas só no episódio, cinza fora dele; faixa sombreada | Limiar +0,5 °C desenhado e rotulado |
| Por estado | Quais estados mudaram mais? | Barras horizontais divergentes e ordenadas | Estado do recorte em cor, os demais em cinza | Zero rotulado ("igual ao normal"); intervalo citado no título |
| 2026 vs. passado | 2026 está seguindo o que os El Niños previam? | Linha de diferença para o normal (gráfico indexado), 3 elementos | Só 2026 em cor; previsão e faixa em cinza | Zero = normal do mês, rotulado; projeção sombreada e escrita "PROJEÇÃO"; 2026 de focos marcado como preliminar |
| Erro das regras | Qual regra prevê melhor? | Pequenos múltiplos de barras ordenadas | Só a melhor regra de cada medida em cor | Mesma escala nos dois blocos; barras no zero; regras fixadas antes de olhar 2026 |

## Resultado com 2023–2025

- **Chuva:** choveu mais nos 9 estados durante o episódio (de +1% em SE a +30% em RN). Na estação chuvosa de fev–abr/2024, o Nordeste teve +48%. A seca que se costuma esperar no norte do Nordeste não apareceu neste episódio.
- **Focos:** no total da região, ficaram estáveis (0%). Subiram em 3 estados (PI +17%, BA +14%, AL +5%) e caíram em 6. O pico de focos cai em outubro todos os anos, com ou sem El Niño.
- **Limite:** há um único episódio, comparado com dois anos. O resultado não vale para todo El Niño e mostra associação, não causa. Todos os textos são recalculados quando novos anos entram em `amostras/`.

# Painel exploratório `/piloto-real`

## Contexto antes de desenhar

- **Tipo de painel:** explanatório. Ele foi feito para outra pessoa decidir, não para exploração.
- **Público:** gestores estaduais de defesa civil e meio ambiente, brigadas e comunidade.
- **O que o público precisa saber:** quando a temporada de focos acontece no seu estado, quanto ela acompanha a seca e se o El Niño mudou a chuva.
- **Big Idea (gerada a partir dos dados):** "Maranhão, 2025: 63% dos focos do ano ocorreram entre set e nov, meses com 30 mm de chuva em média, contra 143 mm no resto do ano." A frase muda com o estado e o ano selecionados.

## Tela única (sem rolagem)

Tudo o que a apresentação precisa cabe em uma janela, a partir de 1100 × 600 px. O layout foi verificado em 1366 × 768 e 1715 × 969.

```
┌ título · filtros (estado, ano, mês) · Limpar filtros ───────────────┐
│ Big Idea: frase com a conclusão                                     │
│ [Focos no ano] [vs. ano anterior] [Mês crítico] [Chuva acumulada]   │
├────────────────────┬────────────────────┬───────────────────────────┤
│ Focos por mês      │ Chuva por mês      │ Mapa (estados →           │
├────────────────────┼────────────────────┤  municípios)              │
│ ONI + El Niño      │ Hipóteses H1 e H2  │                           │
└────────────────────┴────────────────────┴───────────────────────────┘
```

A narrativa segue começo, meio e fim dentro da própria tela:

- **Começo:** Big Idea e KPIs.
- **Meio:** gráficos de evidência, veredito das hipóteses e mapa.
- **Fim:** a ação recomendada fica logo abaixo, em "O que observar a seguir".

O **padrão Z** guia a leitura. O KPI principal (focos no ano, em laranja e maior) fica no canto superior esquerdo, as tendências no meio e o mapa e as hipóteses à direita e embaixo.

Abaixo da tela ficam os **detalhes para consulta**: gráficos completos das hipóteses, ranking, calendário, tabela e referência sazonal do próximo ano. Em telas menores, o painel volta ao fluxo normal com rolagem.

## Checklist de defesa por visual

| Visual | Pergunta que responde | Por que este tipo | Destaque pré-atentivo | Gestalt | Affordance | Honestidade |
|---|---|---|---|---|---|---|
| KPIs | Qual o tamanho da temporada? | "Às vezes o melhor gráfico é um número" | Cor e tamanho só no KPI principal | Cercamento (cards) | — | Variação mostra o valor de referência |
| Focos por mês | Quando acontecem os focos? | Barras para contagem; meses em ordem natural | Três meses de pico em laranja, o resto em cinza | Figura e fundo; sem grade | Clique em um mês; tooltip | Eixo no zero; El Niño anotado em texto |
| Chuva por mês | Quando chove? | Linha para evolução no tempo | Trecho mais chuvoso em verde-água | Continuidade | Clique em um mês | Fonte e unidade na nota |
| ONI | Em que fase ENSO estava o ano? | Linha com limiares | Mês em detalhe com rótulo direto | Proximidade (limiar rotulado na linha) | Clique em um mês | Linha pode ter eixo ajustado; limiares explícitos |
| H1 · secas × focos | "X está associado a Y" | Barras por faixa de X | Faixas ≤ 30 mm em laranja | Similaridade (laranja = focos) | Tooltip com n | Valores escritos; n por faixa; "associação, não causalidade" |
| H2 · El Niño × chuva | "Grupo A difere do grupo B" | Barras horizontais ordenadas, com zero no centro | Estado selecionado em cor | Continuidade (ordenado) | Muda com o filtro de estado | Mesmo mês comparado; episódio único declarado |
| Ranking | Qual estado lidera? | Barra horizontal ordenada | Estado selecionado em cor | Continuidade | Clique seleciona o estado | Barras começam no zero |
| Calendário | Como o ano se distribui no Nordeste? | Heatmap com uma matiz | Célula em detalhe com contorno | Proximidade | Clique detalha | Legenda com mínimo e máximo reais |
| Mapa | Onde? | Coroplético, uma matiz | Estado selecionado com contorno | Figura e fundo | Clique aproxima; navegação estrutural (breadcrumb); "+/−" | Limites simplificados declarados |
| Tabela | Qual o valor exato? | Tabela para consulta pontual | Linha do mês em detalhe | Borda mínima | — | — |
| Referência do próximo ano | O que esperar? | Linha com faixa | Trecho projetado tracejado e sombreado | Fundo distinto para o não observado | — | Rótulo "não observado"; método e erro declarados |

## Regras aplicadas em todo o painel

- **Uma cor por métrica:** laranja = focos, verde-água = chuva, claro = ONI. Cinza = contexto.
- **Um destaque por visual.** O contorno branco indica o estado da interação (mês ou estado em detalhe), não um segundo destaque de dado.
- **Títulos dizem a conclusão** e são calculados a partir dos dados ("63% dos focos entre set e nov").
- **Menos tinta:** sem grade, molduras, gradientes ou sombras decorativas. Ficam a linha de base e três marcas no eixo.
- **Rótulo direto** no valor máximo de cada série, em vez de legenda distante.
- **Cor nunca sozinha:** fases ENSO e vereditos também aparecem em texto.
- **Affordance:** barra de filtros fixa no topo, "Limpar filtros" sempre visível, linha "Exibindo…" com o estado ativo, dicas de clique e tooltips.
- **Destino comum:** o filtro de estado, ano e mês atualiza todos os visuais juntos.
- **Transparência:** fonte em cada gráfico e rodapé com fontes, data de coleta, cobertura de chuva do mês e limites de interpretação.
- **Evitados:** pizza, donut, 3D, bolhas e eixo Y duplo.
- **Agregue antes de plotar:** o navegador recebe só a tabela UF × mês (108 linhas por ano), não os focos brutos.

## Hipóteses (ciclo pergunta → hipótese → gráfico → resposta)

| Hipótese | Gráfico | Resultado com 2023–2025 |
|---|---|---|
| H1 · Meses secos concentram os focos | Barras por faixa de chuva | **Confirmada**: meses com até 30 mm são 34% das observações e concentram 61% dos focos; a média cai a cada faixa de chuva. |
| H2 · O El Niño reduziu a chuva | Barras por estado (diferença %) | **Refutada**: nos meses do episódio mai/2023–abr/2024 choveu mais que nos mesmos meses fora dele, nos 9 estados. Há um só episódio no recorte, então o resultado não generaliza. |

Os vereditos são recalculados no navegador quando novos anos entram em `amostras/`.
