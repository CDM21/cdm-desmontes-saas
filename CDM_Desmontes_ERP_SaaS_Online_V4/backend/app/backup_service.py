import gzip
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import inspect

from .db import engine


def _env(name, default=""):
    return str(os.getenv(name, default) or "").strip()


def build_backup_v2():
    inspector = inspect(engine)
    payload = {
        "format": "cdm-logical-backup-v2",
        "backup_id": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tables": {},
        "table_counts": {},
    }
    with engine.connect() as conn:
        for table in inspector.get_table_names():
            rows = conn.exec_driver_sql(f'SELECT * FROM "{table}"').mappings().all()
            clean = []
            for row in rows:
                item = {}
                for key, value in dict(row).items():
                    item[key] = value.isoformat() if hasattr(value, "isoformat") else value
                clean.append(item)
            payload["tables"][table] = clean
            payload["table_counts"][table] = len(clean)

    integrity_source = json.dumps(
        {"tables": payload["tables"], "table_counts": payload["table_counts"]},
        ensure_ascii=False,
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(integrity_source).hexdigest()
    payload["integrity"] = {"algorithm": "sha256", "sha256": digest}

    raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    blob = gzip.compress(raw, compresslevel=6)
    filename = (
        f"cdm-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-"
        f"{payload['backup_id'][:8]}.json.gz"
    )
    return {
        "blob": blob,
        "filename": filename,
        "backup_id": payload["backup_id"],
        "sha256": digest,
        "tables": len(payload["tables"]),
        "rows": sum(int(x or 0) for x in payload["table_counts"].values()),
        "bytes": len(blob),
    }


def offsite_config():
    endpoint = _env("BACKUP_S3_ENDPOINT")
    access_key = _env("BACKUP_S3_ACCESS_KEY")
    secret_key = _env("BACKUP_S3_SECRET_KEY")
    bucket = _env("BACKUP_S3_BUCKET")
    region = _env("BACKUP_S3_REGION", "auto") or "auto"
    prefix = _env("BACKUP_S3_PREFIX", "cdm-backups").strip("/")

    configured = all([endpoint, access_key, secret_key, bucket])
    auto_raw = _env("AUTO_BACKUP_ENABLED")
    automatic_enabled = (
        configured
        if auto_raw == ""
        else auto_raw.lower() in {"1", "true", "yes", "on"}
    )
    try:
        interval_hours = max(
            1, min(int(_env("AUTO_BACKUP_INTERVAL_HOURS", "24") or "24"), 168)
        )
    except Exception:
        interval_hours = 24

    return {
        "configured": configured,
        "automatic_enabled": automatic_enabled,
        "interval_hours": interval_hours,
        "endpoint": endpoint,
        "bucket": bucket,
        "region": region,
        "prefix": prefix,
        "access_key": access_key,
        "secret_key": secret_key,
    }


def _client(cfg):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=cfg["endpoint"],
        aws_access_key_id=cfg["access_key"],
        aws_secret_access_key=cfg["secret_key"],
        region_name=cfg["region"],
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )



def validate_backup_blob(blob, expected_sha256=""):
    if not isinstance(blob, (bytes, bytearray)) or not blob:
        raise RuntimeError("Backup vazio ou inválido.")

    try:
        raw = gzip.decompress(bytes(blob))
    except Exception as exc:
        raise RuntimeError(f"Backup não pôde ser descompactado: {exc}") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Backup não contém JSON válido: {exc}") from exc

    if payload.get("format") != "cdm-logical-backup-v2":
        raise RuntimeError("Formato de backup não reconhecido.")

    tables = payload.get("tables")
    table_counts = payload.get("table_counts")
    integrity = payload.get("integrity") or {}

    if not isinstance(tables, dict) or not isinstance(table_counts, dict):
        raise RuntimeError("Estrutura interna do backup está incompleta.")
    if set(tables) != set(table_counts):
        raise RuntimeError("Tabelas e contagens do backup não correspondem.")

    for table, rows in tables.items():
        if not isinstance(rows, list):
            raise RuntimeError(f"Tabela {table} possui estrutura inválida.")
        try:
            declared = int(table_counts.get(table))
        except Exception as exc:
            raise RuntimeError(f"Contagem inválida para a tabela {table}.") from exc
        if declared != len(rows):
            raise RuntimeError(
                f"Contagem divergente na tabela {table}: "
                f"declarado={declared}, encontrado={len(rows)}."
            )

    integrity_source = json.dumps(
        {"tables": tables, "table_counts": table_counts},
        ensure_ascii=False,
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    calculated = hashlib.sha256(integrity_source).hexdigest()
    stored = str(integrity.get("sha256") or "").strip().lower()

    if str(integrity.get("algorithm") or "").lower() != "sha256" or not stored:
        raise RuntimeError("Backup não possui assinatura de integridade SHA-256.")
    if calculated != stored:
        raise RuntimeError("SHA-256 interno do backup não confere.")

    expected = str(expected_sha256 or "").strip().lower()
    if expected and calculated != expected:
        raise RuntimeError("SHA-256 do objeto salvo não confere com o backup enviado.")

    return {
        "verified": True,
        "format": payload.get("format"),
        "backup_id": payload.get("backup_id"),
        "created_at": payload.get("created_at"),
        "sha256": calculated,
        "tables": len(tables),
        "rows": sum(len(rows) for rows in tables.values()),
        "bytes": len(blob),
    }


def verify_offsite_object(key, expected_sha256=""):
    cfg = offsite_config()
    if not cfg["configured"]:
        raise RuntimeError(
            "Backup externo não configurado. Faltam as credenciais S3/R2 no servidor."
        )
    if not str(key or "").strip():
        raise RuntimeError("Chave do backup externo não informada.")

    client = _client(cfg)
    response = client.get_object(Bucket=cfg["bucket"], Key=key)
    blob = response["Body"].read()
    metadata = response.get("Metadata") or {}
    metadata_sha = str(metadata.get("sha256") or "").strip()
    verify_against = expected_sha256 or metadata_sha

    result = validate_backup_blob(blob, expected_sha256=verify_against)
    result.update(
        {
            "bucket": cfg["bucket"],
            "key": key,
            "etag": str(response.get("ETag") or "").strip('"'),
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return result


def _quote_sqlite_identifier(value):
    return '"' + str(value).replace('"', '""') + '"'


def _download_offsite_payload(key=""):
    cfg = offsite_config()
    if not cfg["configured"]:
        raise RuntimeError(
            "Backup externo não configurado. Faltam as credenciais S3/R2 no servidor."
        )

    selected_key = str(key or "").strip()
    if not selected_key:
        recent = list_offsite(1).get("items", [])
        if not recent:
            raise RuntimeError("Nenhum backup externo encontrado no R2.")
        selected_key = str(recent[0].get("key") or "").strip()

    client = _client(cfg)
    response = client.get_object(Bucket=cfg["bucket"], Key=selected_key)
    blob = response["Body"].read()
    metadata = response.get("Metadata") or {}
    expected_sha = str(metadata.get("sha256") or "").strip()

    verification = validate_backup_blob(
        blob,
        expected_sha256=expected_sha,
    )
    payload = json.loads(gzip.decompress(blob).decode("utf-8"))

    return {
        "bucket": cfg["bucket"],
        "key": selected_key,
        "blob": blob,
        "payload": payload,
        "verification": verification,
    }


def restore_drill_offsite(key=""):
    """
    Teste de restauração seguro.

    Nunca escreve no banco de produção. O backup é lido do R2, validado e
    reconstruído em um banco SQLite temporário, que é apagado ao final.

    Como o formato V2 não armazena o DDL original das tabelas, as colunas do
    ambiente temporário são recriadas como TEXT. O objetivo deste drill é
    provar que todos os dados do backup podem ser materializados novamente,
    sem alterar o sistema real.
    """
    import sqlite3
    import tempfile

    downloaded = _download_offsite_payload(key)
    payload = downloaded["payload"]
    tables = payload.get("tables") or {}
    declared_counts = payload.get("table_counts") or {}

    temp_path = None
    conn = None
    restored_counts = {}
    restored_rows = 0

    try:
        handle = tempfile.NamedTemporaryFile(
            prefix="cdm-restore-drill-",
            suffix=".sqlite3",
            delete=False,
        )
        temp_path = handle.name
        handle.close()

        conn = sqlite3.connect(temp_path)

        for table_name, rows in tables.items():
            table_ident = _quote_sqlite_identifier(table_name)

            columns = []
            seen = set()
            for row in rows:
                for column in row.keys():
                    if column not in seen:
                        seen.add(column)
                        columns.append(column)

            if not columns:
                conn.execute(
                    f"CREATE TABLE {table_ident} "
                    '("__cdm_empty_table__" TEXT)'
                )
            else:
                column_sql = ", ".join(
                    f"{_quote_sqlite_identifier(column)} TEXT"
                    for column in columns
                )
                conn.execute(f"CREATE TABLE {table_ident} ({column_sql})")

                placeholders = ", ".join("?" for _ in columns)
                quoted_columns = ", ".join(
                    _quote_sqlite_identifier(column)
                    for column in columns
                )
                insert_sql = (
                    f"INSERT INTO {table_ident} ({quoted_columns}) "
                    f"VALUES ({placeholders})"
                )

                values = []
                for row in rows:
                    converted = []
                    for column in columns:
                        value = row.get(column)
                        if isinstance(value, (dict, list)):
                            value = json.dumps(
                                value,
                                ensure_ascii=False,
                                sort_keys=True,
                            )
                        elif value is not None and not isinstance(
                            value, (str, int, float, bool)
                        ):
                            value = str(value)
                        converted.append(value)
                    values.append(tuple(converted))

                if values:
                    conn.executemany(insert_sql, values)

            count = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM {table_ident}"
                ).fetchone()[0]
            )
            restored_counts[table_name] = count
            restored_rows += count

        conn.commit()
        conn.close()
        conn = None

        # Reabre o arquivo para provar que os dados foram realmente gravados.
        conn = sqlite3.connect(temp_path)
        reopened_counts = {}
        for table_name in tables.keys():
            table_ident = _quote_sqlite_identifier(table_name)
            reopened_counts[table_name] = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM {table_ident}"
                ).fetchone()[0]
            )
        conn.close()
        conn = None

        normalized_declared = {
            str(name): int(count or 0)
            for name, count in declared_counts.items()
        }
        counts_match = (
            restored_counts == normalized_declared
            and reopened_counts == normalized_declared
        )

        if not counts_match:
            raise RuntimeError(
                "As contagens restauradas no banco temporário "
                "não conferem com o backup."
            )

        return {
            "ok": True,
            "safe_mode": True,
            "production_database_untouched": True,
            "temporary_database": "sqlite",
            "temporary_schema_mode": "text-columns",
            "temporary_database_deleted": True,
            "bucket": downloaded["bucket"],
            "key": downloaded["key"],
            "backup_id": downloaded["verification"].get("backup_id"),
            "sha256": downloaded["verification"].get("sha256"),
            "tables": len(tables),
            "rows": restored_rows,
            "counts_match": True,
            "reopen_check": True,
            "created_at": payload.get("created_at"),
            "tested_at": datetime.now(timezone.utc).isoformat(),
            "note": (
                "O backup V2 foi reconstruído em banco isolado e descartável. "
                "O teste valida recuperação dos dados e contagens; "
                "não substitui uma restauração futura com DDL nativo."
            ),
        }
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        if temp_path:
            try:
                os.remove(temp_path)
            except FileNotFoundError:
                pass

def upload_offsite(backup=None):
    cfg = offsite_config()
    if not cfg["configured"]:
        raise RuntimeError(
            "Backup externo não configurado. Faltam as credenciais S3/R2 no servidor."
        )

    backup = backup or build_backup_v2()
    key = (
        f"{cfg['prefix']}/{backup['filename']}"
        if cfg["prefix"]
        else backup["filename"]
    )
    client = _client(cfg)
    client.put_object(
        Bucket=cfg["bucket"],
        Key=key,
        Body=backup["blob"],
        ContentType="application/gzip",
        Metadata={
            "cdm-backup-id": backup["backup_id"],
            "sha256": backup["sha256"],
            "format": "cdm-logical-backup-v2",
        },
    )

    # O backup só é considerado concluído depois de ser lido de volta do R2
    # e passar novamente pela validação de formato, contagens e SHA-256.
    verification = verify_offsite_object(
        key,
        expected_sha256=backup["sha256"],
    )

    return {
        "ok": True,
        "verified": True,
        "bucket": cfg["bucket"],
        "key": key,
        "backup_id": backup["backup_id"],
        "sha256": backup["sha256"],
        "bytes": backup["bytes"],
        "tables": backup["tables"],
        "rows": backup["rows"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "verification": verification,
    }


def list_offsite(limit=10):
    cfg = offsite_config()
    if not cfg["configured"]:
        return {"configured": False, "items": []}

    client = _client(cfg)
    prefix = f"{cfg['prefix']}/" if cfg["prefix"] else ""
    result = client.list_objects_v2(
        Bucket=cfg["bucket"],
        Prefix=prefix,
        MaxKeys=max(1, min(int(limit), 100)),
    )
    items = sorted(
        result.get("Contents", []),
        key=lambda x: x.get("LastModified") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return {
        "configured": True,
        "bucket": cfg["bucket"],
        "prefix": cfg["prefix"],
        "items": [
            {
                "key": item.get("Key"),
                "bytes": item.get("Size"),
                "last_modified": (
                    item.get("LastModified").isoformat()
                    if item.get("LastModified")
                    else None
                ),
            }
            for item in items[:limit]
        ],
    }
