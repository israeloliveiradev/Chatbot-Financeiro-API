import httpx
import os
import json

def test():
    base_url = os.environ.get("EVOLUTION_BASE_URL", "http://evolution:8080")
    instance = os.environ.get("EVOLUTION_INSTANCE", "MainInstance")
    api_key = os.environ.get("EVOLUTION_API_KEY")
    
    url = f"{base_url}/message/sendButtons/{instance}"
    headers = {
        "apikey": api_key,
        "Content-Type": "application/json"
    }
    
    # Tentativa 2: Formato V2 sugerido pelo erro
    payload = {
        "number": "5511961605602@s.whatsapp.net",
        "title": "Teste Diagnóstico V2",
        "description": "Corpo da mensagem V2",
        "buttons": [
            {
                "type": "reply",
                "displayText": "Botão V2",
                "id": "1"
            }
        ],
        "footer": "Rodapé"
    }
    
    print(f"URL: {url}")
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
