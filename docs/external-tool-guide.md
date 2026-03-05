# External Tool Entegrasyon Rehberi

Farklı ekiplerden gelen kodların bu projeye tool olarak entegre edilmesi için kod teslim standardı.

---

## 1. Dosya Yapısı ve Adlandırma

### Tek Dosya (< 150 satır)

Basit tool'lar tek dosya olarak teslim edilir:

```
src/tools/
├── subscription_tools.py     ← mevcut örnek
├── billing_tools.py          ← mevcut örnek
├── technical_tools.py        ← mevcut örnek
└── fraud_detection_tool.py   ← yeni harici tool
```

Dosya adı: `<domain>_tool.py` veya `<domain>_tools.py` (birden fazla fonksiyon varsa).

### Modüler Yapı (> 150-200 satır)

150-200 satırı aşan kodlar birden fazla dosyaya bölünür. Orchestration dosyası `<domain>_pipeline.py` olarak adlandırılır:

```
src/tools/
└── fraud_detection/
    ├── __init__.py
    ├── fraud_detection_pipeline.py   ← orchestrator, @tool ile sarılacak fonksiyonlar burada
    ├── rule_engine.py                ← kural motoru
    ├── feature_extractor.py          ← feature engineering
    └── scorer.py                     ← skor hesaplama
```

- Agent dosyası yalnızca `fraud_detection_pipeline.py`'den import yapar
- Alt modüller (`rule_engine.py`, `scorer.py` vb.) doğrudan agent tarafından import edilmez
- `__init__.py` ile dışa açılan fonksiyonları tanımla

---

## 2. Fonksiyon İmza Standardı

Teslim edilen her fonksiyon LangChain `@tool` decorator'ı ile sarılabilecek formatta olmalıdır.

### Zorunlu Unsurlar

| Unsur | Gereklilik | Açıklama |
|---|---|---|
| Docstring | Zorunlu | Fonksiyonun ne yaptığını açıklar. `@tool` bunu LLM'e description olarak sunar |
| Type hint | Zorunlu | Tüm parametreler ve return tipi type hint'li olmalı |
| Args docstring | Zorunlu | Her parametre `Args:` bloğunda açıklanmalı |
| Parametre adları | Zorunlu | Açıklayıcı isimler (LLM parametre adını okuyarak karar verir) |

### Doğru Örnek

Projeden gerçek referans — `src/tools/technical_tools.py:65-84`:

```python
@tool
def create_trouble_ticket(msisdn: str, issue_type: str, description: str) -> str:
    """Create a trouble ticket for unresolved technical issues.

    Args:
        msisdn: Customer phone number.
        issue_type: Issue category, e.g. 'no-signal', 'slow-data', 'call-drops', 'sms-failure'.
        description: Detailed description of the problem from the customer.
    """
    # ... implementasyon
    return "Trouble ticket created: ..."
```

Neden doğru:
- Docstring'in ilk satırı kısa ve net (LLM bunu tool seçiminde kullanır)
- Her parametre `Args:` bloğunda açıklanmış
- Parametre adları açıklayıcı (`issue_type`, `description` — ne beklendiği anlaşılır)
- Örnek değerler verilmiş (`'no-signal', 'slow-data'`)
- Return tipi `str`

### Yanlış Örnek

```python
def process(data, flag=True):
    result = do_something(data)
    return result
```

Sorunlar:
- Docstring yok — LLM fonksiyonun ne yaptığını bilemez
- Type hint yok — `@tool` parametre şemasını çıkaramaz
- Parametre adları belirsiz (`data`, `flag`)
- `Args:` bloğu yok

### Opsiyonel Parametreler

Projeden referans — `src/tools/billing_tools.py:6-27`:

```python
@tool
def get_invoice(msisdn: str, period: str = "") -> str:
    """Get the invoice for a specific billing period.

    Args:
        msisdn: Customer phone number, e.g. '05321234567'.
        period: Billing period, e.g. '2026-02', 'last'. Defaults to current period.
    """
```

Default değerli parametreler discovery API'de `?` ile gösterilir (ör. `period?:string`).

---

## 3. Input Parametreleri

### Tasarım İlkeleri

- **Esnek ama tipli:** Farklı senaryoları handle edebilecek parametreler tanımla, ancak her birinin tipi belli olsun
- **Açık örnekler:** Args docstring'de olası değerleri listele — LLM bu örneklerden öğrenir
- **Basit tipler:** `str`, `int`, `float`, `bool` tercih et. Karmaşık nested objeler yerine virgülle ayrılmış string'ler kullan

Projeden referans — `src/tools/subscription_tools.py:25-41`:

```python
@tool
def search_plans(usage_type: str, budget: str = "") -> str:
    """Search available plans by usage type and optional budget.

    Args:
        usage_type: Usage profile, e.g. 'high-data', 'balanced', 'voice-heavy', 'budget'.
        budget: Optional max monthly price, e.g. 'under 300', '200-400'.
    """
```

- `usage_type` olası değerleri docstring'de listelenmiş
- `budget` string formatında esnek girdi kabul eder (LLM doğal dilde üretebilir)
- İkisi birlikte farklı sorgu senaryolarını karşılar

### Kaçınılması Gerekenler

| Yapma | Yap |
|---|---|
| `data: dict` (tip belirsiz) | `msisdn: str, period: str` (her alan ayrı parametre) |
| `options: list[dict]` (nested) | `plan_ids: str` (virgülle ayrılmış) |
| `config: Any` | Gerekli alanları ayrı parametrelere çıkar |

---

## 4. Output Formatı

### Standart: String Return

Projedeki tüm tool'lar `str` döner. Bu LangChain `@tool` ile en uyumlu formattır — LLM sonucu direkt yorumlayabilir.

Projeden referans — `src/tools/billing_tools.py:69-86`:

```python
@tool
def initiate_payment_plan(msisdn: str, amount: str) -> str:
    """Start an installment payment plan for outstanding balance."""
    # ...
    return (
        f"Payment plan created for {msisdn}:\n"
        f"Total amount: {amount} TL\n"
        "Installments: 3 months\n"
        "Monthly payment: {:.2f} TL\n".format(float(amount) / 3) +
        "First payment: 2026-03-15\n"
        "Plan ID: PAY-2026-33091\n"
        "Note: No interest applied for 3-month plans."
    )
```

### Hata Durumunda Output

Tool içinde **exception fırlatılmamalı**. Hata durumunda da string olarak yapılandırılmış bir hata mesajı dönülmeli:

```python
@tool
def query_crm(msisdn: str) -> str:
    """Query CRM system for customer details.

    Args:
        msisdn: Customer phone number.
    """
    logger.info("Querying CRM for %s", msisdn)
    try:
        result = crm_client.get_customer(msisdn)
        return (
            f"Customer: {result.name}\n"
            f"Segment: {result.segment}\n"
            f"Status: {result.status}"
        )
    except ConnectionError:
        logger.error("CRM connection failed for %s", msisdn)
        return (
            "Error: CRM system is currently unavailable. "
            "Please try again later or escalate to a supervisor."
        )
    except Exception as e:
        logger.exception("Unexpected CRM error for %s", msisdn)
        return f"Error: Could not retrieve customer information. Details: {e}"
```

**Neden exception fırlatmıyoruz:**
- Exception fırlatılırsa agent framework hatayı yakalar ve LLM'e `ToolMessage(content="Error: ...")` olarak iletir — ama mesajın formatını kontrol edemezsiniz
- String olarak hata dönmek LLM'in hatayı anlamlı şekilde kullanıcıya açıklamasını sağlar

---

## 5. Logging

Python `logging` modülü kullanılmalıdır. `print()` kullanılmamalıdır.

### Logger Tanımı

```python
import logging

logger = logging.getLogger(__name__)
```

Projede tüm modüller bu pattern'i kullanır (ör. `src/api/router.py:24`, `src/middleware/prompt.py:8`).

### Log Level Rehberi

| Level | Kullanım |
|---|---|
| `DEBUG` | Detaylı debug bilgisi (parametre değerleri, ara sonuçlar) |
| `INFO` | Normal operasyon bilgisi (başarılı API çağrıları, cache hit) |
| `WARNING` | Beklenmeyen ama devam edilebilir durumlar (fallback kullanımı, yavaş yanıt) |
| `ERROR` | Başarısız operasyonlar (API hatası, timeout) |

### Örnek

```python
import logging

from langchain.tools import tool

logger = logging.getLogger(__name__)


@tool
def check_fraud_score(transaction_id: str) -> str:
    """Check fraud score for a transaction.

    Args:
        transaction_id: Unique transaction identifier.
    """
    logger.info("Checking fraud score for transaction %s", transaction_id)

    try:
        score = fraud_engine.calculate(transaction_id)
        logger.debug("Fraud score for %s: %.2f", transaction_id, score)
        return f"Transaction {transaction_id}: fraud score {score:.2f}/100 — {'high risk' if score > 70 else 'low risk'}"
    except TimeoutError:
        logger.warning("Fraud check timeout for %s, returning default", transaction_id)
        return f"Warning: Fraud check timed out for {transaction_id}. Manual review recommended."
    except Exception as e:
        logger.error("Fraud check failed for %s: %s", transaction_id, e)
        return f"Error: Could not calculate fraud score for {transaction_id}."
```

---

## 6. @tool Entegrasyonu — Agent'a Ekleme

Harici kod teslim edildikten sonra projeye entegrasyon 2 adımda yapılır.

### Adım 1: @tool ile Sarma

Teslim edilen fonksiyon zaten `@tool` formatındaysa direkt kullanılır. Değilse sarılır:

```python
# src/tools/fraud_detection_tool.py
import logging

from langchain.tools import tool

logger = logging.getLogger(__name__)


@tool
def check_fraud_score(transaction_id: str) -> str:
    """Check fraud score for a transaction.

    Args:
        transaction_id: Unique transaction identifier.
    """
    logger.info("Checking fraud score for transaction %s", transaction_id)
    # ... implementasyon
    return f"Transaction {transaction_id}: fraud score 23.5/100 — low risk"
```

**Import kuralı:** `from langchain.tools import tool` (proje convention'ı — `langchain_core` kullanılmaz).

### Adım 2: Agent'a Tool Ekleme

İlgili agent dosyasında tool'u import et ve `create_agent`'ın `tools` listesine ekle.

Projeden referans — `src/agents/billing_agent.py:16-21` ve `50-53`:

```python
# Import
from src.tools.billing_tools import (
    explain_charges,
    get_invoice,
    get_payment_history,
    initiate_payment_plan,
)

# create_agent'a ekle
agent = create_agent(
    model=llm,
    tools=[get_invoice, get_payment_history, explain_charges, initiate_payment_plan],
    ...
)
```

Yeni tool eklemek için sadece import'u ve `tools` listesini güncelle. `providers.py`'de değişiklik gerekmez — tool metadata'sı `@tool` decorator'dan otomatik çekilir ve discovery API'de görünür.

---

## 7. Tam Entegrasyon Örneği

Diyelim ki "fraud detection" ekibi bir tool teslim etti. Entegrasyon:

### 7.1 Tool dosyası oluştur

```python
# src/tools/fraud_detection_tool.py

import logging

from langchain.tools import tool

logger = logging.getLogger(__name__)


@tool
def check_fraud_score(transaction_id: str) -> str:
    """Check fraud risk score for a customer transaction.

    Args:
        transaction_id: Unique transaction identifier, e.g. 'TXN-2026-44821'.
    """
    logger.info("Checking fraud score for %s", transaction_id)
    try:
        # Harici fraud engine çağrısı
        score = _calculate_score(transaction_id)
        risk_level = "high risk" if score > 70 else "medium risk" if score > 40 else "low risk"
        return (
            f"Fraud check for {transaction_id}:\n"
            f"Score: {score:.1f}/100\n"
            f"Risk level: {risk_level}\n"
            f"Recommendation: {'Block transaction' if score > 70 else 'Allow transaction'}"
        )
    except Exception as e:
        logger.error("Fraud check failed for %s: %s", transaction_id, e)
        return f"Error: Could not check fraud score for {transaction_id}. Manual review required."


def _calculate_score(transaction_id: str) -> float:
    """Internal scoring logic."""
    # TODO: Gerçek fraud engine entegrasyonu
    return 23.5
```

### 7.2 Agent'a ekle

```python
# src/agents/billing_agent.py — mevcut import'lara ekle:

from src.tools.fraud_detection_tool import check_fraud_score

# create_agent tools listesine ekle:
agent = create_agent(
    model=llm,
    tools=[get_invoice, get_payment_history, explain_charges, initiate_payment_plan,
           suggest_plan_change, check_fraud_score],  # ← yeni tool eklendi
    ...
)
```

Başka bir değişiklik gerekmez. `GET /agents` endpoint'i yeni tool'u otomatik olarak listeler.

---

## 8. Checklist — Kod Teslim Öncesi

| # | Kontrol | Gereklilik |
|---|---|---|
| 1 | Fonksiyonda docstring var mı? (ilk satır kısa, net) | Zorunlu |
| 2 | `Args:` bloğunda tüm parametreler açıklanmış mı? | Zorunlu |
| 3 | Tüm parametrelerde type hint var mı? | Zorunlu |
| 4 | Return tipi `str` mi? | Zorunlu |
| 5 | Hata durumunda exception fırlatmak yerine string error dönülüyor mu? | Zorunlu |
| 6 | `logging` modülü kullanılıyor mu? (`print()` yok mu?) | Zorunlu |
| 7 | Logger `logging.getLogger(__name__)` ile tanımlı mı? | Zorunlu |
| 8 | Tek dosya 150-200 satırı aşıyorsa modüler yapıya bölünmüş mü? | Zorunlu |
| 9 | Parametre adları açıklayıcı mı? (LLM bunları okuyarak karar verir) | Zorunlu |
| 10 | Docstring'de örnek değerler var mı? (ör. `e.g. 'no-signal', 'slow-data'`) | Önerilen |
| 11 | Import: `from langchain.tools import tool` kullanılıyor mu? | Zorunlu |
| 12 | `@tool` decorator'ı uygulanmış mı? | Zorunlu |
