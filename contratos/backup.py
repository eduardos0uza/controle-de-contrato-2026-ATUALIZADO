import json
import os
from datetime import datetime
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict
from django.conf import settings

def realizar_backup_contrato(contrato):
    """
    Realiza o backup de um contrato e seus itens para um arquivo JSON.
    Salva em backups/contratos/YYYY-MM-DD/contrato_{id}_{timestamp}.json
    """
    try:
        # 1. Preparar dados do contrato
        data = model_to_dict(contrato)
        
        # Converter campos de data/hora para string isoformat
        for key, value in data.items():
            if hasattr(value, 'isoformat'):
                data[key] = value.isoformat()
            elif hasattr(value, 'name'):  # FileField
                data[key] = value.name
            elif value is None:
                data[key] = ""

        # 2. Preparar dados dos itens
        itens = []
        for item in contrato.itens.all():
            item_dict = model_to_dict(item)
            # Remover chave estrangeira circular se houver (geralmente model_to_dict lida bem)
            if 'contrato' in item_dict:
                del item_dict['contrato']
            
            # Converter campos
            for key, value in item_dict.items():
                if hasattr(value, 'isoformat'):
                    item_dict[key] = value.isoformat()
                elif value is None:
                    item_dict[key] = ""
            
            itens.append(item_dict)
        
        data['itens'] = itens
        data['backup_timestamp'] = datetime.now().isoformat()

        # 3. Definir caminho do arquivo
        base_dir = getattr(settings, 'BASE_DIR', os.getcwd())
        hoje = datetime.now().strftime('%Y-%m-%d')
        backup_dir = os.path.join(base_dir, 'backups', 'contratos', hoje)
        
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp_str = datetime.now().strftime('%H%M%S')
        filename = f"contrato_{contrato.id}_{timestamp_str}.json"
        filepath = os.path.join(backup_dir, filename)

        # 4. Salvar arquivo
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False, cls=DjangoJSONEncoder)
            
        return filepath

    except Exception as e:
        print(f"Erro ao realizar backup do contrato {contrato.id}: {str(e)}")
        return None
