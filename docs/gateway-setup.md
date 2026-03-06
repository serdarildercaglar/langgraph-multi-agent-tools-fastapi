# API Gateway Setup

Bu API'ye doğrudan erişimi engellemek ve sadece gateway üzerinden gelen istekleri kabul etmek için **shared secret** mekanizması kullanılır.

---

## Nasıl Çalışır

```
Client → API Gateway → FastAPI (X-Gateway-Secret kontrol) → Agent
Client → FastAPI (header yok) → 403 Forbidden
```

1. `.env`'de `GATEWAY_SECRET` tanımlanır
2. FastAPI her istekte `X-Gateway-Secret` header'ını kontrol eder
3. Gateway, proxy yaparken bu header'ı otomatik ekler
4. Direkt erişimde header olmadığı için istek reddedilir

Secret boşsa middleware eklenmez — development'ta kısıtlama olmadan çalışırsın.

---

## Konfigürasyon

### 1. Secret Oluştur

```bash
# Rastgele 32 karakter secret üret
openssl rand -hex 32
# Örnek çıktı: a3f8b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1
```

### 2. .env'ye Ekle

```env
GATEWAY_SECRET=a3f8b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1
```

### 3. Gateway'i Yapılandır

Aşağıdaki örneklerden ortamına uygun olanı seç.

---

## Nginx

```nginx
upstream agent_api {
    server 127.0.0.1:8080;
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://agent_api;
        proxy_set_header X-Gateway-Secret "a3f8b2c1d4e5...";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## Traefik (docker-compose labels)

```yaml
services:
  agent-api:
    build: .
    env_file: .env
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.agent-api.rule=Host(`api.example.com`)"
      - "traefik.http.middlewares.gateway-secret.headers.customrequestheaders.X-Gateway-Secret=a3f8b2c1d4e5..."
      - "traefik.http.routers.agent-api.middlewares=gateway-secret"
```

---

## Traefik (file provider)

```yaml
# traefik/dynamic.yml
http:
  middlewares:
    gateway-secret:
      headers:
        customRequestHeaders:
          X-Gateway-Secret: "a3f8b2c1d4e5..."

  routers:
    agent-api:
      rule: "Host(`api.example.com`)"
      service: agent-api
      middlewares:
        - gateway-secret

  services:
    agent-api:
      loadBalancer:
        servers:
          - url: "http://127.0.0.1:8080"
```

---

## Caddy

```
api.example.com {
    reverse_proxy 127.0.0.1:8080 {
        header_up X-Gateway-Secret "a3f8b2c1d4e5..."
    }
}
```

---

## HAProxy

```
frontend http_front
    bind *:80
    default_backend agent_api

backend agent_api
    http-request set-header X-Gateway-Secret "a3f8b2c1d4e5..."
    server api1 127.0.0.1:8080
```

---

## Başka Bir FastAPI (Python Gateway)

Gateway'in kendisi de FastAPI ise, `httpx` ile proxy yaparken header eklersin:

```python
import httpx

AGENT_API_URL = "http://127.0.0.1:8080"
GATEWAY_SECRET = "a3f8b2c1d4e5..."

async def proxy_to_agent(path: str, body: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{AGENT_API_URL}{path}",
            json=body,
            headers={"X-Gateway-Secret": GATEWAY_SECRET},
        )
        return response.json()
```

---

## Test Etme

### Secret aktifken — header ile (geçer)

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -H "X-Gateway-Secret: a3f8b2c1d4e5..." \
  -d '{
    "app_id": "test",
    "user_id": "user-1",
    "messages": [{"role": "user", "content": "merhaba"}]
  }'
# → 200 {"success": true, "message": {...}}
```

### Secret aktifken — header olmadan (reddedilir)

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "app_id": "test",
    "user_id": "user-1",
    "messages": [{"role": "user", "content": "merhaba"}]
  }'
# → 403 {"detail": "Forbidden"}
```

### Secret aktifken — yanlış header (reddedilir)

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -H "X-Gateway-Secret: yanlis-secret" \
  -d '{
    "app_id": "test",
    "user_id": "user-1",
    "messages": [{"role": "user", "content": "merhaba"}]
  }'
# → 403 {"detail": "Forbidden"}
```

### Secret boşken (middleware yok, herkes erişir)

```env
GATEWAY_SECRET=
```

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "app_id": "test",
    "user_id": "user-1",
    "messages": [{"role": "user", "content": "merhaba"}]
  }'
# → 200 {"success": true, "message": {...}}
```

---

## Tüm Endpoint'ler Korunur

Gateway secret aktifken **tüm endpoint'ler** korunur:

| Endpoint | Header Yoksa |
|---|---|
| `POST /chat` | 403 Forbidden |
| `POST /chat/stream` | 403 Forbidden |
| `GET /agents` | 403 Forbidden |
| `/ui/*` (static files) | 403 Forbidden |

UI de dahil korunur. Gateway üzerinden `/ui/` erişilebilir, direkt erişimde 403 döner.

---

## Güvenlik Notları

- Secret'ı `.env` dosyasında tutun, koda yazmayın
- Secret en az 32 karakter olmalı (`openssl rand -hex 32`)
- Production'da HTTPS kullanın — HTTP üzerinde header'lar plaintext iletilir
- Secret'ı periyodik olarak rotate edin (gateway ve `.env`'de aynı anda güncelleyin)
- `.env` dosyası `.gitignore`'da olmalı — secret'ı repo'ya commit etmeyin
