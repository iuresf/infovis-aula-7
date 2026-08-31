# Aula 7 — Visualização da geração elétrica do ONS

Projeto didático autocontido de **Introdução à Visualização da Informação**. Um loader
descobre no catálogo de Dados Abertos do ONS o arquivo do mês escolhido, baixa o CSV
(ou ZIP), normaliza os campos e o grava no PostgreSQL. O Metabase fornece a interface
para explorar e construir visualizações, sem instalar Python ou banco de dados na máquina.

## Pré-requisitos e início rápido

- Docker Engine com o plugin Docker Compose;
- acesso à internet no primeiro uso (imagens e catálogo do ONS);
- portas `3000` e `5432` livres.

```bash
cp .env.example .env
docker compose up --build
```

A primeira carga pode demorar alguns minutos. Quando o Metabase estiver saudável,
abra <http://localhost:3000>. O loader termina com código zero; isso é esperado: ele é
um processo de carga, não um serviço permanente.

## Primeira configuração do Metabase

Crie a conta administrativa pedida pelo assistente e escolha **Adicionar seus dados**.
Use estes valores (eles correspondem ao `.env.example`):

| Campo | Valor |
|---|---|
| Tipo | PostgreSQL |
| Nome de exibição | ONS — Aula 7 |
| Host | `postgres` |
| Porta | `5432` |
| Banco | `ons` |
| Usuário | `ons` |
| Senha | `ons_aula7` |

O nome `postgres` funciona de dentro do Compose; `localhost` não funciona nesse campo.
Se você alterou credenciais no `.env`, use os novos valores. Em seguida, navegue até
**Nova → Pergunta → ONS — Aula 7 → Fato Geracao**. Uma atividade sugerida é criar uma
série temporal com `Data Hora` no eixo x, soma de `Geracao Mwh` no eixo y e `Fonte`
como divisão, filtrando uma `Regiao`.

## Dados e modelo

Por padrão, o projeto usa janeiro de 2024. Para selecionar outro mês, edite antes da
carga:

```dotenv
ONS_YEAR=2023
ONS_MONTH=7
```

O loader consulta a API CKAN do [catálogo de Dados Abertos do ONS](https://dados.ons.org.br/),
procura o recurso cujo nome ou URL contenha o ano e mês e só então segue a URL publicada
pelo catálogo. Portanto, não há URL fixa de arquivo mensal no código. Arquivos CSV e ZIP
são aceitos, assim como separadores `;`, `,` e tabulação e os formatos numéricos usuais
no Brasil.

A tabela `geracao_usina` preserva a granularidade usina/hora necessária à carga. A chave
é um SHA-256 determinístico dos campos de negócio; `ON CONFLICT DO NOTHING` torna toda
reexecução idempotente. A view analítica soma usinas por hora, região e fonte:

```sql
SELECT data_hora, regiao, fonte, geracao_mwh
FROM fato_geracao
ORDER BY data_hora, regiao, fonte;
```

Neste conjunto horário, a potência média (`MW`) durante uma janela de uma hora equivale
numericamente à energia (`MWh`) nessa janela; a view usa o nome didático `geracao_mwh`.
`fonte` prioriza o tipo de combustível informado pelo ONS e usa o tipo de usina como
alternativa. `regiao` corresponde ao subsistema elétrico.

## Operação e diagnóstico

```bash
# Estado e healthchecks
docker compose ps

# Acompanhar somente a descoberta e a carga
docker compose logs -f loader

# Conferir a view no terminal
docker compose exec postgres psql -U ons -d ons \
  -c 'SELECT * FROM fato_geracao LIMIT 10;'

# Reexecutar a carga do mês configurado (não duplica linhas)
docker compose run --rm loader
```

O PostgreSQL só libera os dependentes após `pg_isready`. O Metabase começa após o loader
concluir e testa seu endpoint `/api/health`. Se o ONS estiver temporariamente indisponível,
o loader reinicia automaticamente. Para trocar o mês mantendo os dados anteriores, altere
`.env` e execute `docker compose run --rm loader`; meses diferentes coexistem na tabela.

### Erro de coluna de geração não encontrada

O cabeçalho do conjunto `GERACAO_USINA-2` usa `val_geracao`, enquanto versões anteriores
do loader procuravam somente variações como `val_geracaomwmed`. O loader atual aceita
ambas as nomenclaturas e, ao iniciar, registra no log a lista de colunas compatíveis.

Se o traceback ainda mostrar uma lista que **não contém `val_geracao`** (como no erro que
termina em `('val_geracaomwmed', 'val_geracaomw', 'geracao_mw', ...)`), o contêiner em
execução é anterior à correção. Pare o acompanhamento de logs com `Ctrl+C` e aplique a
configuração atual com um único comando (os dados do PostgreSQL permanecem preservados):

```bash
docker compose up -d --build --force-recreate loader
```

O arquivo `loader.py` do checkout é montado como somente leitura no contêiner. Assim, a
recriação acima não pode continuar usando o código antigo armazenado na imagem. Em seguida,
confira se a primeira linha do novo log contém `val_geracao`:

```bash
docker compose logs -f loader
```

## Reset

Reset completo (remove banco ONS, configurações/usuários do Metabase e volume):

```bash
docker compose down -v --remove-orphans
docker compose up --build
```

Para apenas parar e preservar tudo, use `docker compose down`. Os scripts em `sql/` são
executados pelo PostgreSQL ao criar um volume novo; por isso alterações neles exigem o
reset completo em um ambiente já inicializado.

## Estrutura

```text
compose.yaml                 serviços, dependências e healthchecks
loader/Dockerfile            imagem Python mínima
loader/loader.py             catálogo, download, normalização e upsert
sql/00-create-metabase-db.sh banco interno do Metabase
sql/01-schema.sql            tabela, índice e view fato_geracao
.env.example                 configuração local reproduzível
```

> As condições de uso, revisões e semântica oficial dos campos são responsabilidade do
> ONS. Este repositório não redistribui os dados: obtém o recurso diretamente do catálogo.
