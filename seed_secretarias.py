import os
import django
from django.utils.text import slugify

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_contratos.settings')
django.setup()

from admin_panel.models import Secretaria

secretarias = [
    "TRANSPORTE", "COMUNICAÇÃO", "EDUCAÇÃO", "FAZENDA", "OBRAS", "SAÚDE", 
    "DESENVOLVIMENTO", "SEGURANÇA PUBLICA", "TURISMO E LAZER", "CULTURA", 
    "MEIO AMBIENTE", "ASSISTENCIA SOCIAL", "ADMINISTRAÇÃO", "PESCA", 
    "ESPORTE", "GABINETE", "AGRICULTURA", "PROCURADORIA GERAL", 
    "CONTROLE INTERNO", "SJB PREV", "SERVIÇO PUBLICO"
]

def seed_secretarias():
    for nome in secretarias:
        obj, created = Secretaria.objects.get_or_create(
            nome=nome,
            defaults={'slug': slugify(nome)}
        )
        if created:
            print(f"Secretaria {nome} criada com sucesso.")
        else:
            print(f"Secretaria {nome} já existe.")

if __name__ == "__main__":
    seed_secretarias()
