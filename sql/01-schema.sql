CREATE TABLE IF NOT EXISTS geracao_usina (
    chave_linha text PRIMARY KEY,
    data_hora timestamptz NOT NULL,
    regiao text NOT NULL,
    fonte text NOT NULL,
    geracao_mwh double precision NOT NULL,
    usina text,
    recurso_url text NOT NULL,
    carregado_em timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS geracao_usina_data_hora_idx ON geracao_usina (data_hora);

CREATE OR REPLACE VIEW fato_geracao AS
SELECT
    data_hora,
    regiao,
    fonte,
    SUM(geracao_mwh)::double precision AS geracao_mwh
FROM geracao_usina
GROUP BY data_hora, regiao, fonte;

COMMENT ON VIEW fato_geracao IS
  'Geração horária agregada por região e fonte, pronta para análise no Metabase.';
