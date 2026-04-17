from django.core.management.color import no_style
from django.db import connection

from .models import Contract, ContractHistory, ContractItem


SEQUENCE_ERROR_MARKERS = (
    'contratos_contract_pkey',
    'contratos_contractitem_pkey',
    'contratos_contracthistory_pkey',
)


def is_sequence_integrity_error(error) -> bool:
    message = str(error)
    return any(marker in message for marker in SEQUENCE_ERROR_MARKERS)


def reset_contract_sequences():
    sql_statements = connection.ops.sequence_reset_sql(
        no_style(),
        [Contract, ContractItem, ContractHistory],
    )
    if not sql_statements:
        return
    with connection.cursor() as cursor:
        for sql in sql_statements:
            cursor.execute(sql)
