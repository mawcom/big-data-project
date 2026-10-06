# Tema: El Niño, aquecimento global e extremos climáticos no Brasil

## 1. Resumo do tema

Este projeto propõe estudar como episódios de El Niño se relacionam com extremos climáticos no Brasil e como os efeitos observados variam entre regiões. O aquecimento global entra como contexto de longo prazo: ele altera a linha de base térmica sobre a qual variabilidade natural, como o El Niño–Oscilação Sul (ENSO), atua.

O ponto de partida é uma hipótese de trabalho, não uma conclusão: em determinadas épocas e regiões, condições associadas ao El Niño podem coincidir com maior calor, estiagem, chuva intensa, cheias ou risco de fogo. Esses efeitos não são uniformes no território e nem todos os eventos extremos podem ser atribuídos ao El Niño ou à mudança do clima isoladamente.

## 2. Pergunta e objetivos

### Pergunta principal

**Como a ocorrência e a intensidade de extremos de chuva, calor e estiagem variam entre regiões brasileiras durante episódios de El Niño, em comparação com períodos neutros e de La Niña, considerando a tendência de aquecimento de longo prazo?**

### Objetivos específicos

1. Construir uma base temporal consistente a partir de dados meteorológicos e de focos de fogo.
2. Calcular anomalias de chuva e temperatura em relação a uma climatologia de referência documentada.
3. Comparar os indicadores por região, estação do ano e fase ENSO.
4. Investigar associações entre calor/estiagem e focos de calor, explicitando as limitações de detecção por satélite.
5. Documentar qualidade, cobertura, decisões, código e limitações para que outra pessoa reproduza a análise.

### Hipóteses exploratórias

- Os efeitos associados ao ENSO variam por região e estação, em vez de apresentar o mesmo sinal em todo o país.
- Meses mais quentes e secos podem coincidir com mais focos detectados, mas essa associação também depende de uso do solo, vegetação, atividade humana, condições locais e do satélite.
- A mesma anomalia de temperatura pode representar risco diferente em contextos regionais distintos.

Essas hipóteses serão testadas nos dados; não devem ser codificadas como verdades do estudo.

## 3. Conceitos que o relatório deve distinguir

### El Niño e ENSO

El Niño é a fase quente do fenômeno oceano-atmosfera ENSO, associado a anomalias de temperatura no Pacífico equatorial e a mudanças de circulação atmosférica. La Niña é a fase fria; há também períodos neutros. A classificação deve vir de uma série/index oficial e de regra temporal declarada (por exemplo, índice Niño 3.4 e limiar/persistência adotados). O rótulo não deve ser inferido a partir da própria chuva ou temperatura brasileira, para evitar raciocínio circular.

### Aquecimento global

É uma tendência de longo prazo no sistema climático, causada principalmente pelo aumento de gases de efeito estufa de origem humana. Para estimar uma tendência climática são necessárias séries longas e tratamento consistente de estações, mudanças de instrumentos e cobertura espacial. Uma série curta ou um único evento ENSO não permite quantificar essa tendência.

### Extremo meteorológico, desastre e impacto

Uma anomalia climática é um desvio em relação a uma referência. Um extremo pode ser definido por limiares físicos ou percentis. Desastre é o resultado de exposição e vulnerabilidade combinadas com o perigo, e não apenas do tempo meteorológico. Por isso, chuva intensa não é sinônimo de enchente com dano; seca meteorológica não é automaticamente crise de abastecimento.

### Atribuição

Encontrar coincidência temporal ou correlação não prova que ENSO ou aquecimento global causaram um evento individual. Atribuição formal exige métodos e dados apropriados, como comparação entre mundos factuais e contrafactuais, além de quantificação de incerteza. O escopo inicial é análise descritiva e associativa.

## 4. Mecanismos e padrões regionais a investigar

Órgãos brasileiros descrevem, em termos gerais, um contraste recorrente: maior probabilidade de chuva acima da média no Sul em certas estações e maior risco de déficit de chuva em partes do Norte e do Nordeste. Esses padrões são probabilísticos. A intensidade e o momento variam entre episódios, e Atlântico tropical, circulação regional, sazonalidade, topografia e condições antecedentes também importam.

- **Sul:** investigar acumulados extremos, sequência de dias chuvosos, cheias e níveis de rios; separar chuva mensal de chuva concentrada em poucos dias.
- **Norte/Amazônia:** investigar déficit de chuva, temperatura, estiagem, níveis fluviais e focos detectados; considerar diferenças entre leste/norte e oeste/sudoeste da Amazônia.
- **Nordeste:** investigar chuva e períodos secos com recorte por sub-região; a região não deve ser tratada como climaticamente homogênea.
- **Centro-Oeste e Sudeste:** explorar transição sazonal, ondas de calor, períodos secos, reservatórios e focos de calor quando os dados escolhidos sustentarem a análise.

A descrição é motivação para a pesquisa, não uma previsão determinística. Impactos de cada caso devem ser comparados aos dados observados e a boletins técnicos do período.

## 5. Dados planejados

| Fonte | Uso pretendido | Cuidados principais |
|---|---|---|
| INMET, dados históricos de estações automáticas | Temperatura, precipitação, umidade e variáveis horárias | Cabeçalhos e codificações podem variar; estações têm cobertura incompleta; verificar unidades, faltantes, coordenadas e mudanças de estação. |
| INPE, Programa Queimadas / dados abertos | Focos detectados por satélite, data, localização e atributos disponíveis | Foco detectado não é área queimada nem contagem direta de incêndios; sensor, órbita, nuvens, resolução e regra de seleção alteram a série. |
| ANA / HidroWeb (fase opcional) | Cotas e vazões em estações selecionadas | Acesso e formatos variam por serviço/estação; validar consistência e distinção entre dado bruto, adotado e consistido. |
| Índice ENSO oficial (fonte NOAA/CPTEC, a definir) | Classificação temporal de El Niño, La Niña e neutro | Registrar fonte, índice, unidade, limiar, versão e regra de persistência usados. |
| Normal climatológica oficial (a definir) | Referência para anomalias | Usar período e metodologia compatíveis, preferencialmente uma normal oficial de 30 anos; documentar lacunas e cobertura. |

Fontes institucionais para começar: [dados históricos do INMET](https://portal.inmet.gov.br/dados-historicos), [dados abertos de queimadas do INPE](https://data.inpe.br/queimadas/portal/pages/secao_downloads/dados-abertos/), [HidroWebservice da ANA](https://www.ana.gov.br/hidrowebservice/swagger-ui/index.html) e [manuais de serviços hidrológicos da ANA](https://www.gov.br/ana/pt-br/assuntos/monitoramento-e-eventos-criticos/monitoramento-hidrologico/orientacoes-manuais/manuais-de-sistemas-e-servicos-de-disponibilizacao-de-dados-hidrologicos).

## 6. Definições operacionais para uma futura análise real

Antes de obter os resultados, o grupo precisa decidir e registrar:

1. **Área:** estação, município, estado, bioma, bacia ou grade. Uma média de “região” precisa dizer como as estações foram agregadas e ponderadas.
2. **Janela temporal:** escolher anos completos; excluir ou marcar explicitamente anos parciais.
3. **Resolução:** preservar hora/dia na camada tratada e agregar para mês apenas na camada analítica.
4. **Chuva extrema:** definir por percentil local, índice climatológico ou limiar fixo e indicar período-base.
5. **Onda de calor:** definir duração e limiar local de temperatura máxima/mínima; não chamar um mês quente de onda de calor sem critério diário.
6. **Seca:** decidir se será meteorológica (precipitação), agrícola (umidade do solo) ou hidrológica (rios/reservatórios); não misturar conceitos.
7. **Foco de calor:** fixar satélite de referência/produto e explicar que o foco é um pixel/sinal detectado, não uma ocorrência confirmada de incêndio.
8. **ENSO:** obter a série de índice e documentar como meses/estações recebem o rótulo da fase.
9. **Anomalia:** comparar cada variável à sua própria distribuição e referência espacial/temporal.

## 7. Escopo por etapas

### Protótipo atual

Interface demonstrativa, com dados sintéticos e avisos explícitos. Serve para discutir recortes, indicadores e navegação; não sustenta conclusão ambiental.

### MVP de dados reais

Escolher uma pergunta estreita (por exemplo, contraste de chuva/temperatura e focos em dois recortes regionais), testar poucos anos, validar fontes, estabelecer o esquema canônico e publicar perfil de qualidade. Não começar com todos os anos e todas as estações do país.

### Expansão

Ampliar cobertura e volume, comparar múltiplos eventos ENSO, introduzir normal climatológica adequada, integrar ANA quando a pergunta exigir resposta hidrológica e acrescentar mapas somente depois de resolver os limites geográficos e a qualidade espacial.

## 8. Produtos e visualizações possíveis

- linha temporal de anomalias com faixas de fase ENSO;
- mapa ou tabela de cobertura das estações e percentuais faltantes;
- comparação regional em pequenos múltiplos, sem escalas que escondam diferenças;
- distribuição de extremos por estação do ano e fase ENSO;
- dispersão entre anomalia de temperatura/chuva e focos, com ressalva de correlação;
- painel de qualidade: completude, duplicatas, valores sinalizados, anos/estações incluídos;
- tabela e dicionário dos agregados publicados.

## 9. Como comunicar resultados

Cada gráfico deve indicar fonte, recorte, período-base, unidade, quantidade de observações válidas e se o valor é observado ou derivado. Informar incertezas e dados faltantes. Escrever “associado a”, “coincidiu com” ou “foi observado durante” quando a análise for descritiva. Reservar “causou” para evidência causal apropriada.

## 10. Leituras e fontes institucionais

- [INPE: o que sabemos sobre El Niño e seus impactos no Brasil](https://www.gov.br/inpe/pt-br/assuntos/ultimas-noticias/o-que-precisamos-saber-sobre-o-el-nino-e-seus-impactos-para-o-brasil/)
- [INMET: como foi a atuação do El Niño no Brasil](https://portal.inmet.gov.br/noticias/el-nino-saiba-como-foi-a-atuacao-do-fenomeno-no-brasil)
- [IPCC AR6, capítulo 12: informação climática regional e avaliação de risco](https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-12/)
- [INMET: dados históricos](https://portal.inmet.gov.br/dados-historicos)
- [INPE: dados abertos do Programa Queimadas](https://data.inpe.br/queimadas/portal/pages/secao_downloads/dados-abertos/)
- [ANA: HidroWebservice](https://www.ana.gov.br/hidrowebservice/swagger-ui/index.html)

As páginas e serviços podem mudar. Na coleta real, registrar URL consultada, data de acesso e versão do arquivo/documentação.
