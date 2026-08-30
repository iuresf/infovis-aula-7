"""Localiza no catálogo do ONS e ingere um recurso mensal de geração."""

import csv
import hashlib
import io
import json
import os
import re
import unicodedata
import zipfile
from datetime import datetime

import psycopg
import requests

CATALOG_API = "https://dados.ons.org.br/api/3/action"
TIMEOUT = (20, 300)


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", value.lower())


def find_resource(year: int, month: int) -> dict:
    """Pesquisa o CKAN em vez de depender de um endereço mensal fixo."""
    wanted = (str(year), f"{month:02d}")
    candidates = []
    # A busca sem acentos é tolerada pelo CKAN atual; a segunda forma protege contra
    # mudanças de analisador no catálogo.
    for query in ('"Geracao por Usina em Base Horaria"', "geracao usina"):
        response = requests.get(
            f"{CATALOG_API}/package_search",
            params={"q": query, "rows": 100},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        for package in response.json()["result"]["results"]:
            title = normalized(f"{package.get('title', '')} {package.get('name', '')}")
            if "geracao" not in title or "usina" not in title:
                continue
            for resource in package.get("resources", []):
                text = f"{resource.get('name', '')} {resource.get('url', '')}"
                numbers = re.findall(r"(?<!\d)(20\d{2})[-_/.]?(0[1-9]|1[0-2])(?!\d)", text)
                if wanted in numbers and resource.get("url"):
                    candidates.append(resource)
        if candidates:
            break
    if not candidates:
        raise RuntimeError(f"Recurso mensal {year}-{month:02d} não encontrado no catálogo do ONS")
    candidates.sort(key=lambda r: (str(r.get("format", "")).lower() not in {"csv", "zip"}, r.get("name", "")))
    return candidates[0]


def csv_bytes(resource: dict) -> bytes:
    response = requests.get(resource["url"], timeout=TIMEOUT)
    response.raise_for_status()
    content = response.content
    if zipfile.is_zipfile(io.BytesIO(content)):
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if not names:
                raise RuntimeError("O ZIP mensal não contém arquivo CSV")
            return archive.read(names[0])
    return content


def pick(row: dict, aliases: tuple[str, ...], required: bool = True) -> str:
    lookup = {normalized(key): value for key, value in row.items()}
    for alias in aliases:
        value = lookup.get(normalized(alias))
        if value is not None and str(value).strip():
            return str(value).strip()
    if required:
        raise ValueError(f"Nenhuma coluna encontrada para {aliases}")
    return ""


def parse_time(value: str) -> datetime:
    value = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        for pattern in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
            try:
                return datetime.strptime(value, pattern)
            except ValueError:
                pass
    raise ValueError(f"Data/hora inválida: {value}")


def parse_number(value: str) -> float:
    value = value.strip().replace(" ", "")
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")
    return float(value)


def rows(content: bytes, resource_url: str):
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    for source in csv.DictReader(io.StringIO(text), dialect=dialect):
        data_hora = parse_time(pick(source, ("din_instante", "data_hora", "instante")))
        regiao = pick(source, ("nom_subsistema", "id_subsistema", "regiao", "subsistema"))
        tipo = pick(source, ("nom_tipocombustivel", "tipo_combustivel", "fonte"), required=False)
        fonte = tipo or pick(source, ("nom_tipousina", "tipo_usina"))
        # O ONS publica linhas sem medição no mesmo arquivo. Um campo presente, mas
        # vazio, não deve derrubar a carga inteira (pick trata vazio como ausente).
        geracao_texto = pick(
            source,
            ("val_geracaomwmed", "val_geracaomw", "val_geracao", "geracao_mw", "geracao_mwh", "valor"),
            required=False,
        )
        if not geracao_texto:
            continue
        geracao = parse_number(geracao_texto)
        usina = pick(source, ("id_ons", "cod_usina", "nom_usina", "usina"), required=False)
        identity = json.dumps([data_hora.isoformat(), regiao, fonte, geracao, usina], ensure_ascii=False)
        yield (hashlib.sha256(identity.encode()).hexdigest(), data_hora, regiao, fonte, geracao, usina, resource_url)


def main() -> None:
    year = int(os.getenv("ONS_YEAR", "2024"))
    month = int(os.getenv("ONS_MONTH", "1"))
    if not 1 <= month <= 12:
        raise ValueError("ONS_MONTH deve estar entre 1 e 12")
    resource = find_resource(year, month)
    print(f"Baixando {resource.get('name', resource['url'])}: {resource['url']}")
    content = csv_bytes(resource)
    records = list(rows(content, resource["url"]))
    if not records:
        raise RuntimeError("O recurso mensal está vazio")
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO geracao_usina
                   (chave_linha, data_hora, regiao, fonte, geracao_mwh, usina, recurso_url)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (chave_linha) DO NOTHING""",
                records,
            )
        connection.commit()
    print(f"Carga concluída: {len(records)} linhas lidas (reexecução é segura).")


if __name__ == "__main__":
    main()
