# Guia da frente de processamento de dados

## 1. O que esta frente entrega

O estudo cruza três observações em uma mesma escala, **estado do Nordeste por mês**: intensidade do fenômeno ENOS (ONI), chuva (CHIRPS) e focos de calor detectados pelo satélite de referência (INPE). O produto da frente de processamento é uma tabela com uma linha por `(competencia, uf_codigo_ibge)`, acompanhada de métricas de qualidade e da origem dos dados. Essa tabela permite à análise estatística e ao painel trabalhar sem abrir os arquivos brutos.

Os pilotos executados usam **2023, 2024 e 2025** e os nove estados do Nordeste. O episódio de El Niño aparece de maio de 2023 a abril de 2024 pelo critério histórico ONI usado no código; isso permite comparar sua evolução nos dados observados. Uma referência sazonal exploratória projeta 2026 com base em 2025 e mostra a variação entre 2024 e 2025. A análise histórica planejada usa chuva de 1991–2025 para formar a climatologia 1991–2020 e compara chuva e fogo no período 2003–2025. **Três anos do piloto não permitem calcular anomalia climática confiável nem sustentar conclusões causais sobre El Niño ou aquecimento global.**

## 2. Entradas, saídas e localização

| Etapa | Arquivo ou pasta | Conteúdo |
|---|---|---|
| Coleta | `raw/manifesto_coleta.json` | URL, tamanho, hash SHA-256, horário e estado de cada download. |
| Bruto | `raw/enso/oni_cpc_v6.html` | Série histórica ONI da NOAA CPC. |
| Bruto | `raw/chirps_v3_mensal_latam/chirps-v3.0.AAAAMM.tar.gz` | 36 grades mensais CHIRPS v3 de 2023–2025, com `.hdr` e `.bil`. |
| Bruto | `raw/inpe_focos_sat_ref/focos_br_ref_AAAA.zip` | Um CSV anual do satélite de referência do INPE para cada ano observado. |
| Referência | `raw/referencias/ufs_ibge.geojson` | Malhas simplificadas das nove UFs obtidas na API do IBGE. |
| Referência | `src/bigdata/referencias/ufs_nordeste.csv` | Código IBGE, sigla e nome canônico das UFs. |
| Processado | `clean/referencias/chirps_celula_uf_piloto_AAAA.csv` | Associação auditável de linha/coluna da grade a UF. |
| Amostra | `amostras/piloto_AAAA/` | CSVs pequenos, fatos integrados, resumos regionais e relatórios de qualidade de cada ano completo. |
| Projeção | `amostras/projecao_AAAA/` | Referência para o ano seguinte ao último observado, faixa de variação e documentação do método. |

`raw/` e `clean/` ficam fora do Git. As tabelas pequenas de `amostras/` entram no repositório para qualquer integrante ver o resultado sem baixar as bases. Os dados originais permanecem intactos: a rotina lê os ZIPs/TAR.GZ diretamente e não os extrai em massa.

As fontes oficiais são [NOAA CPC ONI v6](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/index.php), [CHIRPS v3 mensal](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/latam/bils/), [INPE, satélite de referência](https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/Brasil_sat_ref/) e [API de malhas do IBGE](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3). A malha usada aqui é a opção `qualidade=minima`; para um resultado espacial definitivo, avaliar uma malha de maior detalhe.

## 3. Como reproduzir o piloto

Abra o PowerShell na raiz do projeto. Instale [uv](https://docs.astral.sh/uv/getting-started/installation/) se necessário; o projeto exige Python 3.10+.

```powershell
uv sync
uv run poe fetch_raw --range 2023-2025 --sources oni chirps inpe --effort low
uv run poe fetch_uf_geometry
uv run poe sync_data
```

Se os arquivos já estão em `raw/`, execute `sync_data`. O processamento depende apenas de `pandas` e `numpy` entre as bibliotecas do projeto; não precisa iniciar Spark. Também é possível executar `python src/limpeza/sincronizar_dados.py` com um Python que já tenha essas bibliotecas.

Confira os `fato_mensal_uf.csv` e `qualidade.json` de cada ano, além de `amostras/projecao_2026/metodo.json`. Para ver os gráficos, execute `uv run python dashboard/prototipo/app.py` e abra `http://127.0.0.1:8000/piloto-real`. O servidor também chama a sincronização quando a página é aberta; se houver um ano completo novo, processa e atualiza a projeção antes de enviar os dados. O processamento falha se o hash divergir de uma entrada registrada no manifesto, se uma grade tiver formato inesperado, se faltar uma UF ou se aparecer chave duplicada. Arquivos locais sem registro no manifesto são identificados no relatório de qualidade e recebem hash local. Reexecutar os comandos substitui as mesmas saídas; não acumula contagens.

### Acrescentar os próximos anos

Para um ano novo `AAAA`, use `uv run poe fetch_raw --range AAAA --sources oni chirps inpe --effort low` e recarregue `/piloto-real`. A malha IBGE é baixada uma vez só. O ONI é uma série cumulativa e a coleta atualiza sua cópia local em toda execução que inclua essa fonte, inclusive para um ano histórico; um download incompleto não substitui o arquivo anterior. Também é possível copiar os arquivos oficiais manualmente para as pastas e nomes indicados na tabela acima. O sincronizador procura o ZIP anual INPE, os **12 meses CHIRPS**, o HTML ONI e a malha; só publica o ano quando todos estiverem presentes e válidos. Caso contrário, o painel mantém os anos anteriores e informa quantos arquivos faltam. O HTML ONI precisa conter os 12 valores do ano; se estiver incompleto, o ano aguarda atualização da fonte. O ano projetado avança automaticamente para o seguinte ao último ano observado completo.

`uv run poe sync_data` permite conferir o estado sem abrir o painel: ele imprime os anos observados, os processados naquela execução, os anos pendentes e o ano projetado. Use `uv run poe sync_data --force` apenas quando quiser refazer todos os produtos. A verificação de arquivos originais e dos hashes anteriores evita processar novamente anos que não mudaram.

### Resultado observado nesta execução

- 40 arquivos de dados coletados: 36 meses CHIRPS, três ZIPs INPE e um HTML ONI; **130,57 MB** compactados no total nesta coleta.
- 51.061 células CHIRPS associadas a alguma UF nordestina pelo centro da célula; nos 36 meses, nenhuma dessas células tinha valor ausente ou negativo.
- Focos INPE nos nove estados: **56.537 em 2023**, **54.016 em 2024** e **60.467 em 2025**.
- Cada `fato_mensal_uf.csv` tem **108 linhas**, exatamente 9 UFs × 12 meses, sem chaves repetidas; a projeção de 2026 também tem 108 linhas, claramente rotuladas como não observadas.
- ONI de maio a dezembro de 2023 e janeiro a abril de 2024 classificado como El Niño pela regra de cinco janelas. O rótulo é derivado da série histórica ONI v6 e não representa o sistema operacional de monitoramento climático atual da NOAA.

Esses números são do arquivo publicado e da transformação descrita aqui, não equivalem a um número de incêndios ou a uma estimativa de área queimada.

## 4. Lógica do processamento

### 4.1 Conferência da coleta

`processar_piloto.py` exige os 14 arquivos de fonte esperados **por ano** e lê `raw/manifesto_coleta.json` quando disponível. Para cada arquivo registrado compara tamanho e SHA-256 antes de calcular as tabelas. Se um arquivo foi copiado manualmente e não consta no manifesto da última coleta, registra essa ausência e calcula seu hash local; os formatos continuam sendo validados. `qualidade.json` guarda os hashes, a data da coleta quando há manifesto, a malha espacial e as contagens. O GeoJSON do IBGE tem hash próprio, pois foi obtido em uma etapa separada.

### 4.2 Tempo e ONI

O HTML da NOAA contém anos e as 12 janelas sazonais `DJF`, `JFM`, ..., `NDJ`. A rotina transforma cada janela em um mês de referência: `DJF` → janeiro, `JFM` → fevereiro etc. Mantém o nome original em `janela_oni`. Converte ONI para número, ordena o histórico e valida a continuidade mensal. Só rotula **El Niño** ou **La Niña** quando há pelo menos cinco janelas trimestrais sobrepostas consecutivas, respectivamente com ONI ≥ +0,5 °C ou ≤ −0,5 °C. Os demais meses ficam `neutro`.

Esta é uma classificação histórica derivada do ONI. A [página da NOAA](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/index.php) informa que o monitoramento operacional passou a usar RONI; por isso o produto do projeto declara explicitamente `fonte_enso = NOAA CPC ONI v6`.

### 4.3 Focos do INPE

O CSV é lido diretamente dentro do ZIP em lotes de **50 mil linhas** com `pandas.read_csv(..., chunksize=50_000)`. A rotina:

1. converte `data_pas` para data e conta datas inválidas;
2. restringe os registros ao ano solicitado;
3. remove acentos e padroniza `estado`, mapeando o nome ao código IBGE da dimensão;
4. conta registros por `(ano, mes, uf_codigo_ibge)`;
5. só completa combinações sem detecção com zero depois de verificar que o arquivo anual contém registros em janeiro e dezembro.

O lote não é deduplicado por latitude, horário ou município: dois registros próximos podem ser detecções distintas. `focos_inpe` significa quantidade de linhas válidas do produto anual no recorte; o relatório registra linhas fora do Nordeste, datas inválidas e fora do ano. Para a série histórica, também será preciso verificar eventuais revisões ou duplicatas de identificadores do próprio INPE antes de escolher uma regra de deduplicação.

### 4.4 Chuva CHIRPS e associação espacial

Cada TAR.GZ tem um `.hdr` com dimensões, tipo, ordem dos bytes e georreferência; o `.bil` contém uma grade `float32`. A rotina valida o cabeçalho e o tamanho da grade, abre **um mês por vez** e descarta o anterior. Para esta grade, são 1.900 × 1.720 células na América Latina; a amostra de um mês descompactada ocupa cerca de 13 MB. Não se cria um DataFrame com todas as células de todos os meses.

A malha do IBGE é convertida em polígonos. O centro geográfico de cada célula é testado contra o polígono da UF, considerando ilhas e buracos. A associação `(linha, coluna) → uf_codigo_ibge` é calculada uma vez, gravada em `clean/referencias/` e reutilizada nos 12 meses. Uma célula atribuída a mais de uma UF causa erro. Valores negativos e não finitos são contados como ausentes.

Para cada UF/mês, `chuva_media_mm` é a **média aritmética dos valores mensais em mm das células válidas**, e não a soma: somar profundidades de chuva de locais diferentes não produz a precipitação da UF. A tabela também traz `celulas_validas`, `celulas_mapeadas` e `cobertura_chuva_pct`. Esta primeira média não é ponderada pela área real das células; a malha é simplificada. Isso afeta especialmente áreas de fronteira e UFs pequenas. Uma versão definitiva pode calcular fração de área interceptada e ponderar as células.

### 4.5 Integração e checagens

ONI e INPE são unidos à chuva pelas chaves de ano/mês e código IBGE de UF. `competencia` é o primeiro dia do mês (`YYYY-MM-01`). O merge usa validação de cardinalidade: uma linha por UF/mês nas fontes de chuva e fogo, e uma linha por mês no ONI. O fato final exige **108 linhas sem chave repetida** e chuva disponível em todas elas. O resumo regional soma os focos das nove UFs, mas apresenta `chuva_media_ufs_mm` como **média simples das nove médias estaduais**; ela não é uma média espacial ponderada do Nordeste. A soma de focos do resumo deve coincidir com a do fato.

As saídas incluem `fonte_chuva`, `fonte_fogo`, `fonte_enso`, `data_status=real_piloto` e indicadores de qualidade. `anomalia_chuva_mm` permanece vazia. Zero representa ausência de foco detectado no arquivo anual verificado; campo vazio representa medida não calculada ou sem informação. Essas situações não devem ser confundidas.

### 4.6 Referência sazonal do próximo ano e erro retrospectivo

`src/analise/projetar_proximo_ano.py` descobre os dois anos observados consecutivos mais recentes. Confere **108 chaves UF/mês em cada ano**, ausência de medidas nulas e correspondência entre as UFs. Para cada UF e mês, a referência do ano seguinte é o valor observado no mesmo mês do último ano. Na execução atual, isso produz **2026 com base em 2025**. Esse método se chama *persistência sazonal*: é um ponto de partida simples e auditável com apenas dois anos de entrada, não um modelo climático ou uma tendência de longo prazo.

A faixa do gráfico é `valor_base ± |valor_base − valor_ano_anterior|`, com limite inferior zero. Em 2026, `ano_base=2025` e `ano_anterior=2024`. Ela mostra a magnitude da mudança observada entre os dois anos de entrada. **Não é um intervalo de confiança, não tem probabilidade associada e não garante que o próximo ano ficará dentro dela.** A regra é aplicada separadamente à chuva e aos focos; nenhuma relação causal entre essas variáveis é presumida. Não há projeção de ONI ou fase ENSO.

Como verificação, o script simula uma previsão retrospectiva: usa o mês de 2024 como referência para o mesmo mês de 2025 e calcula o erro absoluto médio (MAE) por UF para chuva e focos. Por exemplo, no Maranhão o MAE foi **39,393 mm** de chuva e **401,9 focos por mês**. Isso quantifica a limitação da regra nos dados disponíveis; com um único ano de comparação, não é uma validação robusta. A data atual pode estar dentro de 2026, mas esses valores continuam sendo uma projeção calculada **apenas com informações até 2025**, sem atualização por observações de 2026.

O arquivo `projecao_mensal_uf.csv` traz as observações dos dois anos de entrada, referência e faixa do ano seguinte, `metodo=persistencia_sazonal` e `data_status=projecao_exploratoria`. `metodo.json` registra os anos, hashes dos fatos de entrada, MAE por UF, fórmula e limites. A interface exibe os trechos observados como linha contínua e a projeção como linha pontilhada, com faixa sombreada. Quando um ano novo completo chega, o sincronizador cria uma pasta `projecao_AAAA/` para o ano seguinte, preservando as projeções antigas para auditoria.

## 5. Contrato para quem analisa ou monta o painel

Os arquivos observados principais são os `amostras/piloto_AAAA/fato_mensal_uf.csv` de cada ano completo, iniciando em 2023. A chave de cada um é `(competencia, uf_codigo_ibge)`; `uf_sigla` e `uf_nome` servem para exibição. `chuva_media_mm` e `oni_c` são números; `focos_inpe` e as contagens de células são inteiros. `fase_enso`, `qualidade_chuva` e `qualidade_fogo` são categorias. `anomalia_chuva_mm` está intencionalmente nula nos anos do piloto. A projeção fica em uma pasta e esquema separados para impedir que seja confundida com observação.

Para verificar visualmente o resultado, abra `/piloto-real`, escolha **2023** e observe a entrada de El Niño a partir de maio; depois escolha **2024** para ver sua continuação até abril. O mapa, o ranking e o calendário usam **somente o ano observado escolhido**. Os gráficos do ano projetado usam um esquema e rótulo distintos. **As curvas não demonstram que El Niño causou os focos**: há sazonalidade, clima local, uso do solo, condições de detecção e outros fatores. A página inicial em `dashboard/prototipo/` ainda usa dados simulados.

## 6. Passagem do piloto para a série completa

1. Coletar CHIRPS mensal de **1991 a 2025**, INPE de **2003 a 2025** e a série ONI cumulativa. Confirmar meses esperados, revisões da fonte e hashes em cada execução.
2. Substituir a malha simplificada por uma versão de maior detalhe; definir se o resultado será por centro da célula ou por ponderação de área. Fixar a versão e o CRS dos limites usados.
3. Processar a grade grande em Parquet particionado por `ano`; construir o lookup espacial uma vez. A infraestrutura existente em `src/bigdata/` tem jobs para landing, Silver e Gold com Spark. Os jobs ainda precisam ser executados e auditados com a série completa; o piloto pandas **não comprova** que o pipeline Spark passou de ponta a ponta.
4. Calcular, por `(UF, mês do calendário)`, a média histórica de 1991–2020 a partir dos valores mensais válidos, exigindo cobertura suficiente nos 30 anos. Para cada ano, `anomalia_chuva_mm = chuva_media_mm − climatologia_mm`. Não calcular percentual quando a climatologia for zero ou ausente.
5. Analisar 2003–2025 com controle de sazonalidade, tendência e defasagens plausíveis entre ENOS, chuva e fogo. Registrar cobertura de cada fonte por UF/mês. Aquecimento global é contexto climático relevante, mas sua contribuição a um evento extremo requer método de atribuição próprio e não pode ser inferida de um gráfico de correlação.
6. Publicar apenas a Gold validada para o dashboard. Comparar agregados de pandas e Spark no mesmo recorte e registrar tempo, memória, tamanho de entrada e configuração da máquina. O ganho de escala está na leitura e agregação das grades, não nas 108 linhas do piloto.

## 7. O que apresentar como responsável pelo processamento

Mostre a sequência **arquivo oficial → manifesto/hash → detecção automática do ano → padronização de data e UF → lookup espacial → tabelas mensais → checagens → fato integrado → projeção separada**. Abra `qualidade.json` para apontar contagens, hashes e limites; depois mostre duas linhas do fato e o resumo de 12 meses. No painel, use 2023 e 2024 para mostrar o episódio ONI e contraste linhas contínuas de 2024–2025 com a linha pontilhada de 2026, explicando a fórmula e o MAE retrospectivo. Explique que a unidade de análise é UF/mês, que chuva é média em milímetros, fogo é número de detecções e ONI é contexto do ENOS. Termine com os próximos passos para anomalias e análise histórica, sem atribuir causalidade ao piloto.
