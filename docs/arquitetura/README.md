# Arquitetura e métodos do projeto

## 1. Estado e limite desta documentação

Este documento descreve o **protótipo inicial** e a arquitetura planejada para ampliar o uso de dados oficiais. A interface carrega uma amostra observada de chuva do SGB, separada da exploração regional criada deterministicamente por `src/demo_data.py`. Nenhum download de INMET, INPE ou ANA ocorre ao abrir o painel. Valores, fases ENSO, índices e padrões da exploração regional são artificiais e não devem ser citados como resultados.

## 2. Objetivo técnico

Construir um caminho incremental que seja visível, reproduzível e compatível com memória limitada:

```text
fontes oficiais -> arquivos originais (raw) -> validação/normalização -> Parquet tratado -> agregados analíticos -> painel
```

O volume não é um objetivo isolado. O projeto demonstrará ingestão retomável, controle de qualidade, processamento em partes, formatos colunares, rastreabilidade e comparação regional/temporal. Pandas é suficiente para o MVP se cada partição couber em memória; se não couber, particionar mais e/ou usar DuckDB para consultas sobre Parquet é a extensão prevista.

## 3. Estrutura de pastas

```text
big-data-project/
├── README.md
├── requirements.txt
├── src/
│   ├── app.py                 # servidor HTTP local e rotas
│   ├── build_real_sample.py   # extração reprodutível do recorte SGB
│   ├── demo_data.py           # criação determinística do conjunto simulado
│   ├── index.html             # painel, mapa, gráficos SVG e interação
│   └── static/
│       ├── regioes_ibge.geojson # geometria oficial simplificada das regiões
│       └── porto_alegre_chuva_maio_2024.json # amostra observada para o painel
├── docs/
│   ├── tema/README.md         # pergunta científica, conceitos, fontes e limites
│   └── arquitetura/README.md  # desenho técnico, esquema, decisões e expansão
├── data/                      # planejado; ignorar dados grandes no Git
│   ├── raw/                   # origem imutável por fonte/ano
│   ├── sample/                # pequeno recorte observado versionado
│   ├── processed/             # arquivos normalizados Parquet
│   └── analytics/             # agregados que alimentam análises
├── manifests/                 # planejado; inventários/checksums de ingestão
└── reports/                   # planejado; perfis e resumos da execução
```

O arquivo bruto do SGB fica em `data/raw/sgb/` e é ignorado pelo Git. O CSV pequeno da amostra em `data/sample/` pode ser versionado. Dados grandes e credenciais não devem entrar no Git.

## 4. Componentes que já existem

### `src/build_real_sample.py`

- Baixa, quando necessário, o ZIP de dados pluviográficos diários do SGB para `data/raw/sgb/`.
- Confere o SHA-256 da edição usada nesta demonstração.
- Lê somente os 31 arquivos da estação `03051011` referentes a maio de 2024 diretamente de dentro do ZIP, sem extração geral.
- Confere cobertura diária e valores e usa pandas para gerar CSV, resumo e JSON.
- Mantém o nome do arquivo original em cada linha do CSV para rastreabilidade. O método e os limites estão em `docs/dados-reais/README.md`.

### `src/demo_data.py`

- Constrói uma linha por mês e região entre 2010 e 2025 usando pandas.
- Usa funções trigonométricas e regras explícitas para criar sazonalidade e padrões didáticos.
- Retorna dicionário serializável com regiões, métricas, anos e registros.
- Marca `data_status = simulado` e os nomes de fase incluem `(simulado)`.
- É determinístico: a mesma versão do código produz os mesmos dados.
- Não lê relógio, rede, arquivo externo nem aleatoriedade global; facilita apresentação repetível.
- Valores simulados não são calibrados nem derivados dos portais citados.

### `src/app.py`

- Usa `ThreadingHTTPServer` e `BaseHTTPRequestHandler`, ambas da biblioteca padrão.
- Serve `/` e `/index.html` com a interface estática.
- Serve `/api/data` como JSON gerado por `demo_payload()`.
- Serve `/api/observed` com o JSON derivado do SGB e `/sample/porto_alegre_chuva_maio_2024.csv` para download do CSV pequeno.
- Escuta por padrão apenas em `127.0.0.1:8000`; `--host` e `--port` são configuráveis.
- Não precisa de banco, segredo, conta, serviço externo nem framework web.
- Trata `Ctrl+C` para parar o servidor e fecha o socket no bloco `finally`.

### `src/index.html`

- É uma página responsiva sem build frontend.
- Busca `/api/observed` e desenha uma série diária de chuva observada, identificando fonte e limites da interpretação.
- Busca `/api/data`, expõe filtros para região, indicador e ano final na exploração simulada.
- Inclui mapa SVG clicável com os limites simplificados oficiais das cinco Grandes Regiões do IBGE, colorido pela média sintética do indicador e conectado ao filtro regional. A geometria fica em `src/static/regioes_ibge.geojson` e é servida localmente.
- Desenha gráfico temporal em SVG diretamente no navegador e constrói a tabela.
- Exporta o recorte selecionado como CSV com delimitador `;` e BOM UTF-8 para uso comum no Excel pt-BR.
- Aviso persistente informa que as séries são simuladas.
- Links de documentação são locais.

## 5. Stack e dependências

| Componente | Uso | Motivo neste estágio |
|---|---|---|
| Python 3.10+ | lógica, servidor local e integração futura | linguagem principal do projeto. |
| pandas 2.2 a <4 | estrutura tabular sintética agora; transformação CSV/Parquet planejada | satisfaz o aprendizado solicitado e oferece ferramentas de tempo/séries. |
| `http.server`, `json`, `argparse`, `pathlib` | serviço HTTP, serialização, CLI e caminhos | módulos da biblioteca padrão; protótipo leve. |
| HTML/CSS/JavaScript/SVG | filtros, tabela, mapa, gráficos e exportação CSV | interface sem framework; geometria IBGE carregada de arquivo local. |
| PyArrow (planejado) | leitura/escrita Parquet | declarar quando o pipeline real for implementado. |
| DuckDB (opcional planejado) | SQL sobre Parquet para agregações que excedam o conforto do pandas | extensão local sem cluster; medir antes de introduzir. |

`requirements.txt` contém apenas pandas. Não se usa Spark ou cluster neste MVP: adicionar infraestrutura distribuída sem necessidade demonstrada aumentaria o custo didático e operacional.

## 6. Esquema da demonstração

Grão: uma região por mês. A tabela atual tem cinco regiões demonstrativas e 16 anos, totalizando 960 linhas.

| Campo | Tipo | Significado no protótipo |
|---|---|---|
| `date` | ISO `YYYY-MM-DD` | início do mês sintético |
| `year`, `month` | inteiro | dimensões temporais |
| `region` | texto | uma das regiões escolhidas para a UI |
| `enso_phase` | texto | rótulo didático artificial com sufixo “simulado” |
| `rain_anomaly_mm` | float | anomalia de chuva artificial em milímetros |
| `temperature_anomaly_c` | float | anomalia de temperatura artificial em °C |
| `hotspot_index` | float | indicador sintético sem correspondência com contagem oficial |
| `extreme_rain_days` | inteiro | quantidade ilustrativa artificial de dias |
| `drought_index` | float | índice didático artificial de 0 a 100 |
| `data_status` | texto | “simulado” |

**Não interpretar numericamente esses campos como medições, anomalias observadas ou índices científicos.** O esquema real precisará distinguir estação/sensor, localização, unidade original, unidade normalizada, método, qualidade e fonte.

O mapa usa as geometrias simplificadas da API de Malhas do IBGE para as cinco Grandes Regiões, baixadas em 6 de outubro de 2026 e guardadas localmente. A simplificação é adequada à visualização deste protótipo, mas não deve substituir a malha original em cálculos de área ou análises espaciais de maior precisão. As cores representam dados sintéticos agrupados por região; a geometria oficial não torna a série climática observacional.

## 7. Desenho futuro do pipeline real

### 7.1 Inventário e aquisição (raw)

1. Definir fonte, URL oficial, intervalo e direito/termos de uso.
2. Baixar para arquivo temporário por blocos; usar timeout, número limitado de tentativas com espera progressiva e validação HTTP.
3. Validar ZIP (`testzip`), conteúdo esperado, tamanho, checksum SHA-256 e período coberto.
4. Extrair em pasta temporária com validação de caminhos internos; promover para `data/raw/fonte/ano/` somente após validar tudo.
5. Nunca sobrescrever silenciosamente o original. Em nova versão, registrar nome/hash/data e manter origem identificável.
6. Atualizar manifesto JSONL ou CSV com URL, horário UTC, bytes, hash, status, arquivos internos e erro quando houver.

Um diretório preenchido não é critério suficiente de sucesso. O manifesto deve permitir detectar ano ausente, download truncado e execução incompleta.

### 7.2 Normalização (processed)

- Inspecionar cabeçalhos/encoding/delimitador por arquivo e guardar uma tabela de correspondência para nomes canônicos.
- Converter datas explicitamente; declarar fuso horário e semântica da observação (hora local/UTC, hora de fechamento de acumulado).
- Converter colunas numéricas com registro de valores inválidos; diferenciar ausente, sentinela do fornecedor e zero real.
- Preservar colunas originais úteis para auditoria e manter identificador do arquivo de origem.
- Padronizar unidades sem apagar o valor original: `rain_mm`, `air_temperature_c`, `relative_humidity_pct`, latitude/longitude em graus decimais.
- Emitir Parquet particionado por fonte/ano e, após medição, talvez mês/UF. Evitar partições muito pequenas que gerem milhares de arquivos minúsculos.

### 7.3 Qualidade

Checagens planejadas e reportadas por partição:

- unicidade da chave definida (estação, timestamp, variável quando formato vertical);
- faixa plausível, sem descartar o valor bruto;
- monotonicidade e lacunas temporais esperadas por estação;
- percentual ausente por coluna, estação, ano e variável;
- duplicatas exatas e conflitos para a mesma chave;
- consistência da unidade, codificação, latitude/longitude e metadados da estação;
- volume de entrada, linhas lidas, válidas, rejeitadas e gravadas;
- cobertura antes/depois de qualquer exclusão.

Valores suspeitos devem ser sinalizados e explicados. Não aplicar clipping silencioso.

### 7.4 Integração espacial e temporal

Não associar foco de satélite à estação “mais próxima” sem regra e validação. Decidir a unidade geográfica (grade, município, bioma, bacia ou raio), sistema de referência, fonte dos limites e tratamento de pontos na fronteira. Comparar dados na menor granularidade temporal confiável comum. Manter tabela de correspondência espacial versionada.

### 7.5 Camada analítica (analytics)

Guardar agregados com grão declarado, por exemplo região-mês-variável. Cada agregado contém contagens válidas, denominador/cobertura, estatística, unidade, período-base e método. Separar chuva mensal de índices de extremos diários; um acumulado mensal não recupera intensidade e sequência de eventos.

## 8. Uso de pandas e memória

Para os arquivos reais:

- usar `read_csv(..., usecols=..., chunksize=...)` quando um CSV grande não couber confortavelmente em RAM;
- processar e liberar cada chunk antes de avançar, evitando concatenar todos os blocos sem necessidade;
- declarar tipos (`dtype`) e parse de data explicitamente para reduzir memória e erros de inferência;
- agregar incrementalmente quando possível ou gravar partes normalizadas antes de juntar;
- não usar `iterrows` para transformações vetorizáveis em larga escala;
- medir `memory_usage(deep=True)`, bytes no disco, tempo e linhas/s em uma amostra representativa;
- exportar colunas tipadas para Parquet, selecionar colunas e filtros de partição nas releituras.

O chunk precisa respeitar memória real disponível e largura das linhas. O número de linhas, sozinho, não determina a memória: strings e objetos Python podem expandir bastante em RAM.

## 9. Estatística e desenho de análise

1. Obter série temporal oficial de ENSO e definir rótulo a priori.
2. Usar climatologia oficial adequada para cálculo de anomalias; não chamar tendência de 2010–2025 de prova de aquecimento global.
3. Comparar épocas do ano semelhantes e informar tamanho/amostragem por grupo.
4. Fazer estatística descritiva e visualizações antes de modelos.
5. Se houver modelo, separar treino/teste por tempo, considerar autocorrelação e sazonalidade, reportar incerteza e evitar vazamento temporal.
6. Para alegação de contribuição causal de mudança climática ou ENSO a evento individual, ampliar o desenho e envolver literatura/métodos de atribuição climática.

Não definir os limiares de extremos depois de observar quais geram o resultado desejado. Registrar a decisão e sua justificativa antes da análise final.

## 10. API local do protótipo

| Rota | Método | Resposta |
|---|---|---|
| `/` | GET | página HTML do painel |
| `/index.html` | GET | mesma página |
| `/api/data` | GET | JSON de demonstração, metadados e registros |
| `/api/observed` | GET | amostra observada do SGB e resumo de maio de 2024 |
| `/sample/porto_alegre_chuva_maio_2024.csv` | GET | download do recorte observado com nomes dos arquivos de origem |
| `/static/regioes_ibge.geojson` | GET | geometria simplificada das cinco Grandes Regiões (IBGE) |
| demais | GET | HTTP 404 |

O servidor não implementa autenticação, TLS, persistência nem limites de requisição; foi pensado para execução local. O padrão `127.0.0.1` evita expor o protótipo à rede local por acidente.

## 11. Inicialização e operação

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python src\app.py
```

Depois, abrir `http://127.0.0.1:8000`. Outra porta: `python src\app.py --port 8080`. O terminal permanece ocupado enquanto o servidor roda; `Ctrl+C` encerra. O painel funciona offline após iniciado porque não carrega fontes externas.

No workspace atual, o comando `python` não estava disponível no PATH. Foi encontrado um Python 3.12.14 empacotado no runtime do Codex e pandas 3.0.1 já instalado nele. Para a entrega reproduzível em outra máquina, instalar `requirements.txt` em um ambiente virtual.

## 12. Decisões e alternativas

- **Servidor HTTP pequeno em vez de Streamlit:** runtime acessível já tinha pandas, mas não Streamlit/Plotly; evitar instalação obrigatória neste primeiro protótipo. Se o curso preferir Streamlit, a arquitetura permite trocar somente a camada de apresentação.
- **SVG no navegador em vez de plotly:** menos dependências e funciona offline. Para publicação científica, mapas ou interação mais rica, adotar biblioteca de visualização com versão fixada.
- **Mapa SVG com geometria IBGE simplificada:** mantém a interface sem biblioteca geográfica no navegador e usa os limites oficiais das Grandes Regiões. Análises espaciais mais precisas devem usar a malha original do IBGE e documentar o método de agregação.
- **Dados sintéticos em vez de coleta real inicial:** tornar a UI revisável sem falha de endpoint, grande download ou ambiguidade de qualidade. Rotular simulação de forma persistente.
- **Sem Spark:** ainda não foi demonstrado que um processamento local particionado excede os recursos disponíveis.
- **Pandas no centro didático:** manter o aprendizado solicitado, delimitando chunks e medições.

## 13. Limitações e riscos técnicos

- O simulador codifica efeitos artificiais deliberadamente; pode induzir intuição incorreta se o aviso for removido.
- As séries mensais escondem eventos diários extremos.
- O servidor é para uso local/educacional, não serviço de produção.
- A integração INMET/INPE/ANA pode exigir decisões geográficas, de calendário e de unidade que não estão resolvidas.
- O valor mensal `hotspot_index` atual não é foco observado; trocar o dataset não basta, o esquema e rótulo precisam ser revisados.
- O projeto não calcula atribuição de eventos nem tendência formal no protótipo atual.

## 14. Próximas entregas sugeridas

1. Validar recorte regional e pergunta com a equipe.
2. Ampliar a amostra oficial para mais anos e estações, sem confundir instrumentos e períodos de medição.
3. Produzir dicionário de dados, manifesto e perfil de qualidade para as séries ampliadas.
5. Definir normal climatológica, índice ENSO, indicador de extremo e regra espacial.
6. Trocar simulador por dados reais mantendo uma bandeira visível de fonte e cobertura.
7. Comparar tempo/memória de CSV e Parquet; decidir se DuckDB agrega valor.
8. Só expandir para anos nacionais após o MVP reproduzir resultados.
