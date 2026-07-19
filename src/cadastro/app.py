"""
Lambda Cadastro — Cadastra produto no DynamoDB e retorna presigned URL
para upload da imagem no S3.
"""
import base64
import boto3
import json
import logging
import os
import re
import unicodedata
from decimal import Decimal, InvalidOperation


logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

CATALOGO_TABLE = os.environ["CATALOGO_TABLE"]   # catalogo-produtos
IMAGES_BUCKET = os.environ["IMAGES_BUCKET"]     # nome do bucket S3
IMAGES_PREFIX = os.environ.get("IMAGES_PREFIX", "images/produtos/")

catalogo = dynamodb.Table(CATALOGO_TABLE)


def resposta(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def gerar_slug(nome):
    """Gera slug a partir do nome (ex: 'Arroz Branco' -> 'arroz-branco')."""
    texto = unicodedata.normalize("NFKD", nome)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9]+", "-", texto)
    texto = texto.strip("-")
    return texto


def ler_body(event):
    body = event.get("body")
    if not body:
        return None
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    if isinstance(body, dict):
        return body
    return json.loads(body)


def lambda_handler(event, context):
    http_method = (event.get("requestContext", {}).get("http", {}).get("method")
                   or event.get("httpMethod", ""))
    if http_method == "OPTIONS":
        return resposta(200, {})

    try:
        body = ler_body(event)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return resposta(400, {"mensagem": "O corpo da requisição deve ser um JSON válido"})

    if not isinstance(body, dict):
        return resposta(400, {"mensagem": "Corpo da requisição inválido"})

    # Validar campos obrigatórios
    nome = (body.get("nome") or "").strip()
    marca = (body.get("marca") or "").strip()
    categoria = (body.get("categoria") or "").strip()
    unidade = (body.get("unidade") or "").strip()
    preco_raw = body.get("preco")

    if not all([nome, marca, categoria, unidade]):
        return resposta(400, {"mensagem": "Campos obrigatórios: nome, marca, categoria, unidade, preco"})

    try:
        preco = Decimal(str(preco_raw))
        if preco < 0:
            raise ValueError()
    except (InvalidOperation, TypeError, ValueError):
        return resposta(400, {"mensagem": "O campo preco deve ser um número válido >= 0"})

    slug = gerar_slug(nome)
    if not slug:
        return resposta(400, {"mensagem": "Não foi possível gerar um identificador para o produto"})

    # Extensão da imagem (frontend informa)
    extensao = body.get("extensao", "png").lower()
    if extensao not in ("png", "jpg", "jpeg", "webp"):
        extensao = "png"

    imagem_key = f"{IMAGES_PREFIX}{slug}.{extensao}"
    # URL pública via CloudFront/domínio do site (caminho relativo)
    imagem_url = f"/{imagem_key}"

    # Salvar no DynamoDB
    try:
        catalogo.put_item(
            Item={
                "slug": slug,
                "nome": nome,
                "marca": marca,
                "categoria": categoria,
                "preco": preco,
                "unidade": unidade,
                "imagem_url": imagem_url,
            }
        )
    except Exception:
        logger.exception(json.dumps({"evento": "erro_ao_cadastrar_produto", "slug": slug}))
        return resposta(500, {"mensagem": "Não foi possível cadastrar o produto"})

    # Gerar presigned URL para upload da imagem
    try:
        presigned_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": IMAGES_BUCKET,
                "Key": imagem_key,
                "ContentType": f"image/{extensao}",
            },
            ExpiresIn=300,  # 5 minutos
        )
    except Exception:
        logger.exception(json.dumps({"evento": "erro_ao_gerar_presigned_url", "slug": slug}))
        return resposta(500, {"mensagem": "Produto cadastrado mas não foi possível gerar URL de upload"})

    logger.info(json.dumps(
        {"evento": "produto_cadastrado", "slug": slug, "nome": nome},
        ensure_ascii=False,
    ))

    return resposta(201, {
        "mensagem": "Produto cadastrado com sucesso",
        "slug": slug,
        "imagem_url": imagem_url,
        "upload_url": presigned_url,
    })
