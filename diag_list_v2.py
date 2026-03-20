import httpx
import os
import json

def test_list():
    base_url = os.environ.get("EVOLUTION_BASE_URL", "http://evolution:8080")
    instance = os.environ.get("EVOLUTION_INSTANCE", "MainInstance")
    api_key = os.environ.get("EVOLUTION_API_KEY")
    
    url = f"{base_url}/message/sendList/{instance}"
    headers = {
        "apikey": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "number": "5511961605602@s.whatsapp.net",
        "title": "🤖 Menu Financeiro",
        "description": "Escolha uma ação para continuarmos:",
        "buttonText": "Abrir Opções",
        "footerText": "Senior Bot v2.0",
        "sections": [
            {
                "title": "Configurações",
                "rows": [
                    {
                        "title": "📥 Gerar PDF",
                        "description": "Relatório mensal detalhado",
                        "rowId": "G_PDF"
                    },
                    {
                        "title": "🎯 Listar Objetivos",
                        "description": "Ver suas metas ativas",
                        "rowId": "LIST_OBJ"
                    }
                ]
            }
        ]
    }
    
    print(f"URL: {url}")
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_list()
