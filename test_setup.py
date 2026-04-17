import os
import django
from django.urls import reverse
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_contratos.settings')
django.setup()

try:
    print(f"Testing root reverse: {reverse('contratos:home')}")
    print(f"Testing dashboard reverse: {reverse('contratos:dashboard')}")
    print(f"Testing login reverse: {reverse('login')}")
    print("All good!")
except Exception as e:
    print(f"Error caught: {e}")
