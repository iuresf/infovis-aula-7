import unittest

from loader import GENERATION_COLUMNS, rows


class RowsTest(unittest.TestCase):
    def test_current_ons_generation_column_is_declared(self):
        self.assertIn("val_geracao", GENERATION_COLUMNS)

    def test_ignores_row_without_generation_measurement(self):
        content = (
            "din_instante;nom_subsistema;nom_tipocombustivel;val_geracaomwmed;id_ons\n"
            "2024-01-01 00:00:00;SUDESTE;HIDRAULICA;;U1\n"
            "2024-01-01 01:00:00;SUDESTE;HIDRAULICA;12,5;U1\n"
        ).encode()

        records = list(rows(content, "https://example.test/data.csv"))

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0][4], 12.5)

    def test_accepts_val_geracao_column(self):
        content = (
            "din_instante;nom_subsistema;nom_tipocombustivel;val_geracao;id_ons\n"
            "2024-01-01 00:00:00;SUL;EOLICA;7.25;U2\n"
        ).encode()

        records = list(rows(content, "https://example.test/data.csv"))

        self.assertEqual(records[0][4], 7.25)

    def test_reports_received_header_when_generation_column_is_unknown(self):
        content = (
            "din_instante;nom_subsistema;nom_tipocombustivel;medicao_desconhecida;id_ons\n"
            "2024-01-01 00:00:00;SUL;EOLICA;7.25;U2\n"
        ).encode()

        with self.assertRaisesRegex(
            ValueError,
            "Colunas recebidas: din_instante, nom_subsistema, nom_tipocombustivel, "
            "medicao_desconhecida, id_ons",
        ):
            list(rows(content, "https://example.test/data.csv"))


if __name__ == "__main__":
    unittest.main()
