import os
import django
import sys

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_contratos.settings')
django.setup()

from contratos.models import Contract

print(f"{'ID':<5} {'Contract No':<20} {'Days':<10} {'Alert':<15} {'Display':<15}")
print("-" * 70)

for c in Contract.objects.all():
    print(f"{c.id:<5} {c.numero_contrato:<20} {c.dias_restantes:<10} '{c.alerta}'{'':<8} '{c.get_alerta_display()}'")
