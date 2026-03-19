import httpx
import asyncio

async def configure_webhook():
    url = "http://localhost:8080/webhook/set/MainInstance"
    headers = {
        "apikey": "pa7dQpoEfuuowjYU",
        "Content-Type": "application/json"
    }
    payload = {
        "webhook": {
            "enabled": True,
            "url": "http://app:8000/webhook/evolution",
            "byEvents": False,
            "base64": False,
            "events": [
                "MESSAGES_UPSERT",
                "MESSAGES_UPDATE",
                "SEND_MESSAGE",
                "CONNECTION_UPDATE"
            ]
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    asyncio.run(configure_webhook())
