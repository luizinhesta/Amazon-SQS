"""
Lambda Consumidora — Consome mensagens do SQS, busca produto na tabela
catalogo-produtos do DynamoDB e grava resultado em pesquisas-produtos.
"""
import boto3
import json
import logging
import os
import time
from datetime import datetime, timezone
from decimal import Decimal

from botocore.exceptions import ClientError


logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

TABLE_NAME = os.environ["TABLE_NAME"]           # pesquisas-produtos
CATALOGO_TABLE = os.environ["CATALOGO_TABLE"]   # catalogo-produtos

table = dynamodb.Table(TABLE_NAME)
catalogo = dynamodb.Table(CATALOGO_TABLE)


def buscar_produto(slug):
    """Busca produto pelo slug na tabela de catálogo."""
    resultado = catalogo.get_item(Key={"slug": slug})
    return resultado.get("Item")


def atualizar_resultado(search_id, produto_slug, created_at, dados_produto):
    """Atualiza o item no DynamoDB com resultado da pesquisa."""
    processed_at = datetime.now(timezone.utc).isoformat()

    nomes = {"#status": "status"}

    if dados_produto:
        valores = {
            ":pending": "PENDING",
            ":status": "COMPLETED",
            ":produto": produto_slug,
            ":createdAt": created_at,
            ":processedAt": processed_at,
            ":nome": dados_produto["nome"],
            ":marca": dados_produto["marca"],
            ":categoria": dados_produto["categoria"],
            ":preco": dados_produto["preco"],
            ":unidade": dados_produto["unidade"],
            ":imagem_url": dados_produto.get("imagem_url", ""),
        }
        expressoes = [
            "#status = :status",
            "produto = :produto",
            "createdAt = if_not_exists(createdAt, :createdAt)",
            "processedAt = :processedAt",
            "nome = :nome",
            "marca = :marca",
            "categoria = :categoria",
            "preco = :preco",
            "unidade = :unidade",
            "imagem_url = :imagem_url",
        ]
    else:
        valores = {
            ":pending": "PENDING",
            ":status": "NOT_FOUND",
            ":produto": produto_slug,
            ":createdAt": created_at,
            ":processedAt": processed_at,
            ":mensagem": f"Produto '{produto_slug}' não encontrado no catálogo.",
        }
        expressoes = [
            "#status = :status",
            "produto = :produto",
            "createdAt = if_not_exists(createdAt, :createdAt)",
            "processedAt = :processedAt",
            "mensagem = :mensagem",
        ]

    try:
        table.update_item(
            Key={"searchId": search_id},
            UpdateExpression="SET " + ", ".join(expressoes),
            ConditionExpression="attribute_exists(searchId) AND #status = :pending",
            ExpressionAttributeNames=nomes,
            ExpressionAttributeValues=valores,
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.info(json.dumps({"evento": "mensagem_duplicada_ignorada", "searchId": search_id}))
            return
        raise

    status_final = "COMPLETED" if dados_produto else "NOT_FOUND"
    logger.info(json.dumps(
        {"evento": "pesquisa_processada", "searchId": search_id, "produto": produto_slug, "status": status_final},
        ensure_ascii=False,
    ))


def processar_registro(record):
    """Processa um único registro do SQS."""
    mensagem = json.loads(record["body"])
    search_id = mensagem.get("searchId")
    produto = mensagem.get("produto")
    created_at = mensagem.get("createdAt")

    if not all(isinstance(v, str) and v for v in (search_id, produto, created_at)):
        raise ValueError("Mensagem sem searchId, produto ou createdAt válido")

    # Erro proposital para testar retry e DLQ
    if produto == "erro":
        raise Exception("Erro proposital para testar retry e DLQ")

    # Simula processamento (2 segundos)
    time.sleep(2)

    # Busca produto no catálogo (DynamoDB)
    dados_produto = buscar_produto(produto)

    # Atualiza resultado
    atualizar_resultado(search_id, produto, created_at, dados_produto)


def lambda_handler(event, context):
    """Handler principal — processa batch de mensagens SQS."""
    falhas = []

    for record in event.get("Records", []):
        message_id = record.get("messageId", "desconhecido")
        try:
            processar_registro(record)
        except Exception:
            logger.exception(json.dumps(
                {"evento": "erro_ao_processar_mensagem", "messageId": message_id}
            ))
            falhas.append({"itemIdentifier": message_id})

    return {"batchItemFailures": falhas}
