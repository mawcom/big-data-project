# Decisões de visualização do painel `/piloto-real`

Este documento aplica ao painel os conceitos da aula *Visualização de Dados* (Big Data em Python, FACIMP Wyden). Ele serve de roteiro para defender cada visual na apresentação.

## Contexto antes de desenhar

- **Tipo de painel:** explanatório. Ele foi feito para outra pessoa decidir, não para exploração.
- **Público:** gestores estaduais de defesa civil e meio ambiente, brigadas e comunidade.
- **O que o público precisa saber:** quando a temporada de focos acontece no seu estado, quanto ela acompanha a seca e se o El Niño mudou a chuva.
- **Big Idea (gerada a partir dos dados):** "Maranhão, 2025: 63% dos focos do ano ocorreram entre set e nov, meses com 30 mm de chuva em média, contra 143 mm no resto do ano." A frase muda com o estado e o ano selecionados.

## Estrutura narrativa (começo, meio e fim)

| Seção | Papel na história | Conteúdo |
|---|---|---|
| 1 · Contexto | Começo | Big Idea, KPIs, faixa do episódio El Niño |
| 2 · Evidência mês a mês | Meio | Focos, chuva e ONI ao longo do ano |
| 3 · Hipóteses | Meio | H1 e H2 com veredito calculado |
| 4 · Onde | Meio | Ranking, calendário, mapa e tabela |
| 5 · O que observar a seguir | Fim | Ação recomendada e referência sazonal do próximo ano |

A página segue o **padrão Z**. O KPI principal (focos no ano, em laranja e maior) fica no canto superior esquerdo. Tendências ficam no meio, e tabela, notas e fontes ficam embaixo.

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
