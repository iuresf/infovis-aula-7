import unittest

from loader import rows


class RowsTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
