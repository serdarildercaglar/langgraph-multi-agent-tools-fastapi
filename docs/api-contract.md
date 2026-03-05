# API Contract — Request & Response Payload

API kontratı `src/models/schemas.py` dosyasında tanımlıdır. Mevcut alanlar geriye uyumludur — yeni alan eklemek gerekirse sadece optional alan eklenir, mevcut alanların tipi değiştirilmez.

---

## 1. Endpoints

| Endpoint | Method | Content-Type | Açıklama |
|---|---|---|---|
| `/chat` | POST | `application/json` | Sync agent çağrısı — tam yanıt döner |
| `/chat/stream` | POST | `text/event-stream` (SSE) | Token token yanıt döner |
| `/agents` | GET | `text/toon` veya `application/json` | Kayıtlı agent'ları listeler (discovery) |

---

## 2. ChatRequest

**Dosya:** `src/models/schemas.py:33-54`

| Alan | Tip | Zorunlu | Default | Açıklama |
|---|---|---|---|---|
| `app_id` | `str` | Evet | — | Uygulamayı tanımlayan benzersiz ID. `min_length=1` |
| `user_id` | `str` | Evet | — | Kullanıcıyı tanımlayan benzersiz ID. `min_length=1` |
| `agent_name` | `str` | Hayır | `"main"` | Hedef agent adı. `min_length=1` |
| `session_id` | `str \| null` | Hayır | `null` | Oturum ID'si. `null` → stateless (chat history tutulmaz) |
| `messages` | `list[Message]` | Evet | — | Konuşma mesajları (OpenAI formatı). `min_length=1` |
| `metadata` | `dict \| null` | Hayır | `null` | Custom key-value çiftleri (department, priority, vb.) |

### Message

**Dosya:** `src/models/schemas.py:20-28`

| Alan | Tip | Açıklama |
|---|---|---|
| `role` | `Literal["user", "assistant", "system", "tool"]` | Mesaj rolü |
| `content` | `str \| list[dict]` | Metin veya multimodal içerik listesi (OpenAI formatı) |

### Örnek: Minimal Request

```json
{
  "app_id": "mobile-app",
  "user_id": "user-42",
  "messages": [
    {"role": "user", "content": "Mevcut tarifem nedir?"}
  ]
}
```

`agent_name` verilmediğinde default `"main"` agent'ı kullanılır. `session_id` verilmediğinde agent stateless çalışır.

### Örnek: Stateful Request (Chat History)

```json
{
  "app_id": "web-portal",
  "user_id": "user-42",
  "agent_name": "billing",
  "session_id": "sess-abc-123",
  "messages": [
    {"role": "user", "content": "Son faturamı göster"}
  ]
}
```

`session_id` verildiğinde `thread_id = "web-portal:user-42:sess-abc-123"` oluşturulur. Bu ID ile önceki mesajlar checkpointer'dan yüklenir.

### Örnek: Multimodal Request

```json
{
  "app_id": "mobile-app",
  "user_id": "user-42",
  "session_id": "sess-xyz-789",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "Bu faturadaki ek ücret nedir?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBOR..."}}
      ]
    }
  ]
}
```

### Örnek: Metadata ile Request

```json
{
  "app_id": "call-center",
  "user_id": "user-99",
  "agent_name": "technical",
  "session_id": "sess-call-001",
  "messages": [
    {"role": "user", "content": "Internet cok yavas"}
  ],
  "metadata": {
    "department": "retention",
    "priority": "high",
    "channel": "phone"
  }
}
```

---

## 3. ChatResponse

**Dosya:** `src/models/schemas.py:80-110`

| Alan | Tip | Açıklama |
|---|---|---|
| `id` | `str` | Benzersiz yanıt ID'si (UUID) |
| `success` | `bool` | İsteğin başarılı olup olmadığı |
| `message` | `Message \| null` | Agent yanıtı. Hata durumunda `null` |
| `error` | `ErrorDetail \| null` | Hata detayı. Başarılı durumda `null` |
| `usage` | `Usage \| null` | Token kullanım istatistikleri |
| `agent_name` | `str \| null` | İsteği işleyen agent'ın adı |
| `app_id` | `str` | Request'teki `app_id`'nin echo'su |
| `user_id` | `str` | Request'teki `user_id`'nin echo'su |
| `session_id` | `str \| null` | Request'teki `session_id`'nin echo'su |
| `created_at` | `datetime` | Yanıt zaman damgası (UTC, otomatik) |

### Örnek: Başarılı Response

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "success": true,
  "message": {
    "role": "assistant",
    "content": "Mevcut tarifeniniz Platinum 50 GB: 50 GB data, sinirsiz arama, 1000 SMS — aylik 449 TL. Sozlesme bitis tarihi: 2026-09-15."
  },
  "error": null,
  "usage": {
    "prompt_tokens": 245,
    "completion_tokens": 58,
    "total_tokens": 303
  },
  "agent_name": "main",
  "app_id": "mobile-app",
  "user_id": "user-42",
  "session_id": "sess-abc-123",
  "created_at": "2026-03-05T14:32:10.123456Z"
}
```

### Örnek: Hatalı Response

```json
{
  "id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
  "success": false,
  "message": null,
  "error": {
    "code": "agent_not_found",
    "message": "Unknown agent_name: 'invalid_agent'. Choose from ['main', 'subscription', 'billing', 'technical']",
    "details": null
  },
  "usage": null,
  "agent_name": null,
  "app_id": "mobile-app",
  "user_id": "user-42",
  "session_id": null,
  "created_at": "2026-03-05T14:32:10.456789Z"
}
```

---

## 4. ErrorCode ve ErrorDetail

### ErrorCode

**Dosya:** `src/models/schemas.py:8-15`

```python
ErrorCode = Literal[
    "agent_not_found",
    "invalid_request",
    "llm_error",
    "rate_limit",
    "timeout",
    "internal_error",
]
```

| Kod | Açıklama | Tetikleyen Durum |
|---|---|---|
| `agent_not_found` | İstenen agent kayıtlı değil | `get_agent()` → `ValueError` (`router.py:71-80`) |
| `invalid_request` | Geçersiz request body | Pydantic validation hatası (FastAPI otomatik) |
| `llm_error` | LLM çağrısı başarısız | `agent.ainvoke()` / `agent.astream()` exception (`router.py:99-109`) |
| `rate_limit` | Rate limit aşıldı | LLM veya harici API rate limit |
| `timeout` | Zaman aşımı | LLM yanıt süresi aşıldı |
| `internal_error` | Beklenmeyen dahili hata | Yakalanmayan exception |

> **Kural:** Yeni hata kodu eklemek gerektiğinde `ErrorCode` Literal'e eklenir. Router'da serbest string kullanılmaz.

### ErrorDetail

**Dosya:** `src/models/schemas.py:67-77`

| Alan | Tip | Açıklama |
|---|---|---|
| `code` | `ErrorCode` | Makine tarafından okunabilir hata kodu |
| `message` | `str` | İnsan tarafından okunabilir hata mesajı |
| `details` | `dict \| null` | Ek bağlam bilgisi (validation hataları vb.) |

---

## 5. Usage (Token İstatistikleri)

**Dosya:** `src/models/schemas.py:59-64`

| Alan | Tip | Açıklama |
|---|---|---|
| `prompt_tokens` | `int` | Gönderilen token sayısı. `ge=0` |
| `completion_tokens` | `int` | Üretilen token sayısı. `ge=0` |
| `total_tokens` | `int` | Toplam token sayısı. `ge=0` |

Token bilgileri LLM yanıtındaki `usage_metadata`'dan çıkarılır (`router.py:52-62`). LLM metadata döndürmezse `usage` alanı `null` olur.

---

## 6. SSE Stream Formatı — POST /chat/stream

**Dosya:** `src/api/router.py:112-148`

`/chat/stream` endpoint'i `EventSourceResponse` ile Server-Sent Events formatında yanıt döner. Request body `/chat` ile aynıdır (`ChatRequest`).

### Event Tipleri

| Event | Data (JSON) | Açıklama |
|---|---|---|
| `token` | `{"content": "..."}` | LLM'den gelen bir token parçası |
| `done` | `{}` | Stream başarıyla tamamlandı |
| `error` | `{"code": "...", "message": "..."}` | Hata oluştu |

### Stream Akışı — Başarılı Oturum

```
event: token
data: {"content": "Mevcut"}

event: token
data: {"content": " tarifeniniz"}

event: token
data: {"content": " Platinum"}

event: token
data: {"content": " 50 GB"}

event: token
data: {"content": ": aylik"}

event: token
data: {"content": " 449 TL."}

event: done
data: {}
```

### Stream Akışı — Agent Bulunamadı

Agent registry'de bulunamayan bir agent istendiğinde (`router.py:115-124`):

```
event: error
data: {"code": "agent_not_found", "message": "Unknown agent_name: 'invalid'. Choose from ['main', 'subscription', 'billing', 'technical']"}
```

### Stream Akışı — LLM Hatası

Stream sırasında LLM hatası oluşursa (`router.py:141-146`):

```
event: token
data: {"content": "Faturanizi"}

event: token
data: {"content": " kontrol"}

event: error
data: {"code": "llm_error", "message": "Connection timeout to vLLM endpoint"}
```

### Client Tarafı Kullanım (JavaScript)

```javascript
const eventSource = new EventSource("/chat/stream", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    app_id: "web-portal",
    user_id: "user-42",
    session_id: "sess-abc-123",
    messages: [{ role: "user", content: "Faturami goster" }]
  })
});

eventSource.addEventListener("token", (e) => {
  const { content } = JSON.parse(e.data);
  // content'i UI'a ekle
});

eventSource.addEventListener("done", () => {
  eventSource.close();
});

eventSource.addEventListener("error", (e) => {
  const { code, message } = JSON.parse(e.data);
  // Hatayı kullanıcıya göster
  eventSource.close();
});
```

---

## 7. Discovery API — GET /agents

**Dosya:** `src/api/router.py:151-161`, `src/providers.py:50-91`

### Query Parameters

| Param | Default | Açıklama |
|---|---|---|
| `format` | `toon` | Yanıt formatı: `toon` (LLM-friendly) veya `json` |

### Response Yapısı

Her agent için:

| Alan | Kaynak | Açıklama |
|---|---|---|
| `name` | `AGENTS` dict key | Agent adı |
| `description` | `AGENTS[name]["description"]` | Agent açıklaması |
| `endpoint` | Sabit `"/chat"` | Çağrı endpoint'i |
| `tools` | Runtime — agent'ın compiled graph'ından çıkarılır | Tool listesi |

Her tool için:

| Alan | Kaynak | Açıklama |
|---|---|---|
| `name` | `tool_obj.name` | Tool adı |
| `description` | `tool_obj.description` (ilk satır) | Tool açıklaması |
| `parameters` | `tool_obj.args_schema` | Parametreler (`name:type` formatında, opsiyoneller `?` ile) |

### Örnek: JSON Response (`GET /agents?format=json`)

```json
{
  "agents": [
    {
      "name": "main",
      "description": "Customer support manager. Routes to subscription/billing/technical specialists.",
      "endpoint": "/chat",
      "tools": [
        {
          "name": "ask_subscription_specialist",
          "description": "Delegate subscription and plan questions to the subscription specialist.",
          "parameters": "question:string"
        },
        {
          "name": "ask_billing_specialist",
          "description": "Delegate billing and payment questions to the billing specialist.",
          "parameters": "question:string"
        },
        {
          "name": "ask_technical_specialist",
          "description": "Delegate technical issues to the technical support specialist.",
          "parameters": "question:string"
        }
      ]
    },
    {
      "name": "subscription",
      "description": "Subscription specialist. Plan info, upgrades, comparisons, packages.",
      "endpoint": "/chat",
      "tools": [
        {
          "name": "get_current_plan",
          "description": "Get the customer's current subscription plan details.",
          "parameters": "msisdn:string"
        },
        {
          "name": "search_plans",
          "description": "Search available plans by usage type and optional budget.",
          "parameters": "usage_type:string,budget?:string"
        },
        {
          "name": "compare_plans",
          "description": "Compare two or more plans side by side.",
          "parameters": "plan_ids:string"
        },
        {
          "name": "change_plan",
          "description": "Initiate a plan change for the customer.",
          "parameters": "msisdn:string,plan_id:string"
        },
        {
          "name": "add_package",
          "description": "Add an extra package to the customer's line.",
          "parameters": "msisdn:string,package_type:string"
        }
      ]
    },
    {
      "name": "billing",
      "description": "Billing specialist. Invoices, charges, payments, installment plans.",
      "endpoint": "/chat",
      "tools": [
        {
          "name": "get_invoice",
          "description": "Get the invoice for a specific billing period.",
          "parameters": "msisdn:string,period?:string"
        },
        {
          "name": "get_payment_history",
          "description": "Get the payment history for a customer.",
          "parameters": "msisdn:string"
        },
        {
          "name": "explain_charges",
          "description": "Explain invoice charges in detail (overages, extra services, etc.).",
          "parameters": "msisdn:string,period?:string"
        },
        {
          "name": "initiate_payment_plan",
          "description": "Start an installment payment plan for outstanding balance.",
          "parameters": "msisdn:string,amount:string"
        },
        {
          "name": "suggest_plan_change",
          "description": "Suggest a better plan when the customer has frequent overages.",
          "parameters": "msisdn:string"
        }
      ]
    },
    {
      "name": "technical",
      "description": "Technical support specialist. Network, diagnostics, device compatibility, trouble tickets.",
      "endpoint": "/chat",
      "tools": [
        {
          "name": "check_network_status",
          "description": "Check network/coverage status for a specific area.",
          "parameters": "location:string"
        },
        {
          "name": "run_line_diagnostic",
          "description": "Run a diagnostic check on the customer's line.",
          "parameters": "msisdn:string"
        },
        {
          "name": "check_device_compatibility",
          "description": "Check device compatibility with network features (5G, VoLTE, etc.).",
          "parameters": "imei:string"
        },
        {
          "name": "create_trouble_ticket",
          "description": "Create a trouble ticket for unresolved technical issues.",
          "parameters": "msisdn:string,issue_type:string,description:string"
        }
      ]
    }
  ]
}
```

> **Not:** Tool metadata manuel yazılmaz. `@tool` decorator'daki docstring ve type hint'lerden otomatik çıkarılır (`providers.py:50-74`).
