# El Niño, aquecimento global e extremos no Brasil

Protótipo estudantil para explorar como fases do El Niño podem se relacionar com extremos climáticos em diferentes regiões brasileiras, considerando o aquecimento global como contexto de longo prazo.

> **Estado atual:** protótipo visual com dados simulados. Os gráficos não são resultados científicos nem observações oficiais.

## Abrir o painel

Requer Python 3.10 ou mais recente. O arquivo `requirements.txt` lista as dependências Python (neste protótipo, pandas). No PowerShell, na pasta do projeto:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python src\app.py
```

Abra [http://127.0.0.1:8000](http://127.0.0.1:8000). Para encerrar o servidor, volte ao terminal e pressione `Ctrl+C`.

Se o comando `py` não existir, use `python` no lugar dele para criar o ambiente. Se o PowerShell bloquear a ativação do ambiente, rode os comandos diretamente pelo executável local:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\app.py
```

É possível alterar a porta: `python src\app.py --port 8080`.

## O que há no protótipo

- painel interativo com filtro por região, período e indicador;
- mapa escuro e clicável das cinco Grandes Regiões, com limites simplificados do IBGE e ligado aos mesmos filtros;
- séries mensais simuladas de chuva, temperatura, focos de calor e extremos;
- marcação visual de fases ENSO simuladas;
- resumo e tabela mensal exportável como CSV pelo navegador;
- documentação de contexto científico e de arquitetura.

## Documentação

- [Tema e método de análise](docs/tema/README.md)
- [Arquitetura e decisões de programação](docs/arquitetura/README.md)

## Próximos passos recomendados

1. **Fechar a pergunta e o recorte:** escolher uma região, período e extremos a comparar durante El Niño, La Niña e neutralidade.
2. **Montar uma amostra real pequena:** baixar um ano de uma fonte oficial, preservando os arquivos originais e anotando URL, data de coleta, licença e cobertura.
3. **Preparar os dados com pandas:** ler CSV em partes quando necessário, padronizar datas e unidades e registrar valores ausentes, duplicatas e critérios de qualidade.
4. **Definir a comparação científica:** documentar a fonte/classificação ENSO, a definição de cada extremo e como separar sazonalidade e aquecimento de longo prazo. Associação nos dados não prova causalidade.
5. **Salvar uma camada tratada em Parquet:** particionar por fonte e ano, manter manifesto com hashes e testar se cada partição cabe na memória.
6. **Validar e só então ampliar:** conferir resultados da amostra; usar DuckDB para consultas sobre Parquet se necessário; aumentar anos/fontes e incluir ANA depois.
7. **Ligar os resultados observados ao painel:** preservar a identificação da fonte, período e cobertura e distinguir visualmente dados observados de simulações.
