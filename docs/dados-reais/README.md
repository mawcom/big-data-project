# Primeira amostra com dados observados

## O que foi incluído

O painel mostra a **precipitação total registrada em cada arquivo diário de maio de 2024** da estação Porto Alegre–Jardim Botânico, código `03051011`, publicada no *Atlas Pluviométrico do Brasil* pelo Serviço Geológico do Brasil (SGB). A fonte reúne registros da estação pluviométrica de Porto Alegre e identifica também códigos associados à estação do INMET. A amostra aqui é a série dos **pluviogramas diários do SGB**, não uma extração direta do CSV horário do INMET.

- [Página oficial do conjunto](https://rigeo.sgb.gov.br/items/bc33cf6b-674e-407f-83a0-6eb06160fa72)
- [ZIP oficial de dados pluviográficos diários](https://rigeo.sgb.gov.br/bitstreams/b72a78e2-3b2e-4a28-8f4a-ed4e496ce0e0/download)
- SHA-256 do ZIP usado: `65d58709cf90d2b7b746b0e14e6946a632cd7f00f9feb1cc634da48c207c0f85`

O ZIP original fica em `data/raw/sgb/porto_alegre_diarios_1975_2024.zip`, ignorado pelo Git. O script extrai apenas os 31 arquivos de maio de 2024 e cria:

- `data/sample/porto_alegre_chuva_maio_2024.csv`: data, chuva em mm, tipo de registro e nome do arquivo original;
- `src/static/porto_alegre_chuva_maio_2024.json`: dados e resumo usados pelo painel.

## Como reproduzir

Depois de instalar `requirements.txt`, execute na raiz do projeto:

```powershell
python src\build_real_sample.py
```

Se o ZIP original não estiver presente, o script o baixa da fonte oficial. Ele confere o SHA-256 antes de processar e interrompe a execução se a edição obtida for diferente da que foi registrada aqui. O download original tem cerca de 12 MB; o CSV resultante tem cerca de 1,5 KB.

## Método aplicado

1. Selecionar no ZIP arquivos cujo nome segue `03051011-202405DD-CP.txt` ou `03051011-202405DD-SP.txt`.
2. Ler apenas a linha **“Precipitação Total no Pluviograma (mm)”** de cada arquivo e converter para número. `CP` indica arquivo com precipitação; `SP`, sem precipitação.
3. Rejeitar valores negativos ou um arquivo `SP` com chuva diferente de zero.
4. Conferir que as datas de 1 a 31 de maio aparecem uma vez cada.
5. Usar pandas para ordenar, somar, contar dias com chuva e localizar o maior total.
6. Exportar o CSV e o JSON pequenos; o servidor local lê esse JSON sem consultar a internet.

## Resultado reproduzido

| Indicador | Valor |
|---|---:|
| Registros diários | 31 |
| Soma dos totais dos arquivos de maio de 2024 | 464,23 mm |
| Registros com chuva maior que zero | 21 |
| Maior total em um arquivo diário | 98,27 mm, arquivo de 23/05/2024 |

## Limites da interpretação

A data apresentada é a data do arquivo e do cabeçalho do pluviograma. O intervalo medido pode cruzar dois dias civis; portanto, os totais não devem ser interpretados automaticamente como chuva de 00h a 24h. O resultado descreve **uma estação e um mês**. Diferenças entre instrumentos, períodos de medição e regras de qualidade podem produzir números diferentes em outras publicações para Porto Alegre.

Este recorte demonstra ingestão, rastreabilidade e apresentação de observações. Ele não mede o efeito do El Niño nem atribui a chuva ao aquecimento global. Para estudar essas relações, serão necessárias séries mais longas, fase ENSO definida por fonte oficial, comparação sazonal, tratamento de tendências e análise de incerteza.
