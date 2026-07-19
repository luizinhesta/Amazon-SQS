"""
Lambda Produtora — Recebe pesquisa do API Gateway, grava PENDING no DynamoDB
e envia mensagem para a fila SQS.
"""
import base64
import boto3
import json
import logging
import os
import uuid
from datetime import datetime, timezone


logger = logging.getLogger()
logger.setLevel(logging.INFO)

sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")

QUEUE_URL = os.environ["QUEUE_URL"]
TABLE_NAME = os.environ["TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)


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
        return resposta(400, {"mensagem": "Informe o produto no corpo da requisição"})

    produto = body.get("produto")
    if not isinstance(produto, str) or not produto.strip():
        return resposta(400, {"mensagem": "O campo produto é obrigatório e não pode ser vazio"})

    produto = produto.strip().lower()
    if len(produto) > 100:
        return resposta(400, {"mensagem": "O produto deve ter no máximo 100 caracteres"})

    search_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    mensagem = {
        "searchId": search_id,
        "produto": produto,
        "createdAt": created_at,
    }

    try:
        table.put_item(
            Item={**mensagem, "status": "PENDING"},
            ConditionExpression="attribute_not_exists(searchId)",
        )
        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(mensagem, ensure_ascii=False),
        )
        logger.info(json.dumps(
            {"evento": "pesquisa_enfileirada", "searchId": search_id, "produto": produto},
            ensure_ascii=False,
        ))
    except Exception:
        logger.exception(json.dumps({"evento": "erro_ao_criar_pesquisa", "searchId": search_id}))
        return resposta(500, {"mensagem": "Não foi possível criar a pesquisa"})

    return resposta(202, {
        "searchId": search_id,
        "status": "PENDING",
        "mensagem": "Pesquisa recebida e enviada para processamento",
    })
