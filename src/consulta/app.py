"""
Lambda Consulta — Lê o resultado da pesquisa no DynamoDB e retorna ao frontend.
"""
import boto3
import json
import logging
import os
from decimal import Decimal


logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)


class DecimalEncoder(json.JSONEncoder):
    def default(self, value):
        if isinstance(value, Decimal):
            return int(value) if value % 1 == 0 else float(value)
        return super().default(value)


def resposta(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body, cls=DecimalEncoder, ensure_ascii=False),
    }


def lambda_handler(event, context):
    http_method = (event.get("requestContext", {}).get("http", {}).get("method")
                   or event.get("httpMethod", ""))
    if http_method == "OPTIONS":
        return resposta(200, {})

    search_id = (event.get("pathParameters") or {}).get("searchId", "").strip()
    if not search_id:
        return resposta(400, {"mensagem": "O searchId é obrigatório"})

    try:
        resultado = table.get_item(Key={"searchId": search_id}, ConsistentRead=True)
    except Exception:
        logger.exception(json.dumps({"evento": "erro_ao_consultar_pesquisa", "searchId": search_id}))
        return resposta(500, {"mensagem": "Não foi possível consultar a pesquisa"})

    item = resultado.get("Item")
    if not item:
        return resposta(404, {"mensagem": "Pesquisa não encontrada", "searchId": search_id})

    logger.info(json.dumps({"evento": "pesquisa_consultada", "searchId": search_id}))
    return resposta(200, item)
