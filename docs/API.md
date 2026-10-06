# API první fáze

Všechny měny jsou Kč. JSON requesty používají `Content-Type: application/json`. Privátní endpointy vyžadují session z `/api/login` nebo `Authorization: Bearer <APP_ADMIN_TOKEN>`. Neposílejte token v URL. Příklady jsou **schémata s placeholdery**, nikoli skutečné obchodní výsledky.

| Endpoint | Účel |
|---|---|
| `GET /api/health` | Stav serveru |
| `POST /api/login` | `{ "token": "<spravcovsky-token>" }`, HttpOnly session |
| `POST /api/logout` | Odhlášení cookie session |
| `GET /api/state` | Produkty, experimenty, KPI, akce, audit a zjištění |
| `GET /api/integrations` | Pravdivý stav nepřipojených integrací |
| `POST /api/products` | Produkt a ekonomika |
| `POST /api/products/<id>/update` | Úprava interního profilu; historické objednávky se nemění |
| `POST /api/experiments` | Hypotéza, Creative ID a kreativní brief |
| `POST /api/import/orders` | Atomický import skutečných objednávek |
| `POST /api/import/ads` | Upsert denních metrik z exportu |
| `POST /api/track` | Browser události se souhlasem; jen povolený shop origin |
| `POST /api/actions` | Konkrétní návrh ke schválení |
| `POST /api/actions/<id>/decision` | approve / reject / edit / rollback |
| `POST /api/settings` | Interní cíle a limity |
| `POST /api/analyze` | Pravidlová analýza vlastních dat |
| `POST /api/leads` | Autentizovaná evidence skutečného opt-in |
| `POST /api/leads/confirm` | Jednorázové potvrzení tokenem |
| `POST /api/leads/<id>/delete` | Výmaz kontaktu |

Maximum requestu: 1 MB, maximum importu: 1000 řádků. Chyba kteréhokoli řádku vrací HTTP 400 a zruší celou transakci. Databázová ID jsou case-sensitive. Nečíselné hodnoty, NaN/Infinity a záporné částky se odmítají.

## Produkt

```json
{
  "name": "<skutecny-produkt>",
  "url": "https://<obchod>/<produkt>",
  "source": "<URL a datum overeni / vlastni produktovy podklad>",
  "facts": "<dolozene vlastnosti, benefity a omezeni; hypotezy oddelit>",
  "economics": {
    "sale_price": 0, "purchase_cost": 0, "vat_rate": 0,
    "shipping_cost": 0, "payment_percent": 0, "payment_fixed": 0,
    "returns_cost": 0, "other_cost": 0
  }
}
```

Placeholder prodejní ceny 0 je neplatný: při importu vždy vložte skutečnou cenu > 0. Všechny ekonomické hodnoty jsou na jednotku. Náklady jsou net; prodejní cena gross. Break-even CPA může být záporné: takový produkt už bez reklamy vychází ztrátově.

## Experiment

Vyžaduje `product_id`, `name`, `platform`, `angle`, `audience`, `hook`, `landing_page` (HTTPS), `hypothesis`, `success_metric`, `creative` (text obsahující vlastní script, shot list, on-screen text, ad copy, headline a CTA). Vrací unikátní `CR-…`, stav začíná `draft`.

## Skutečné objednávky

```json
{
  "orders": [{
    "id": "<unikatni-id-objednavky-z-platformy>",
    "source": "<platforma a identifikace exportu>",
    "creative_id": "<existujici-CR-id-nebo-null>",
    "session_id": null,
    "occurred_at": "2026-10-06T12:00:00+02:00",
    "items": [{"product_id": "<existujici-PROD-id>", "quantity": 1, "revenue": 0}]
  }]
}
```

Použijte JSON `null` místo textového placeholderu, není-li Creative ID známo. `revenue` je skutečná produktová tržba daného řádku vč. DPH, nikoli jednotková cena. `quantity` je kladné celé číslo. `session_id` je volitelné, smí pocházet jen z opravdového spárování s tracking session. Neukládejte osobní údaje zákazníka do ID ani atribuce. Timestamp vyžaduje časové pásmo.

Stejné ID a obsah = duplicate. Stejné ID a rozdílné řádky, source, creative, session nebo datum = odmítnutí. Pozdější změny modelových nákladů nemění původní ekonomický snapshot; reimport zachová původní příspěvek. Import nezjišťuje pravost exportu sám, vyžaduje ověřený podklad správce. Importujte pouze skutečné dokončené, nestornované a nerefundované objednávky; adaptér pro refundace zatím není implementován.

## Reklamní metriky

```json
{
  "metrics": [{
    "creative_id": "<existujici-CR-id>",
    "day": "2026-10-06", "spend": 0, "impressions": 0, "clicks": 0,
    "source": "<platforma a skutecny export>"
  }]
}
```

Řádek nahrazuje celodenní metriky stejného Creative ID; neposílejte inkrementální přírůstky. Jeden experiment označuje jedno umístění/jednu platformu; pro další účet/platformu použijte jiné Creative ID. Kliknutí a imprese jsou celá čísla, kliknutí ≤ imprese. Den používejte ve shodném reportovacím časovém pásmu; rozpočtový dashboard používá Europe/Prague.

## Akce a schválení

```json
{
  "title": "<konkretni-zmena>", "kind": "start_experiment",
  "target": "<existujici-CR-id>", "current_value": "draft", "proposed_value": "running",
  "reason": "<hypoteza a dukazy>", "expected_impact": "<overitelny-dopad>", "confidence": "Low"
}
```

Typy: `start_experiment`, `pause_experiment`, `external_change`, `budget_change`. Confidence: `Low`, `Medium`, `High`.

Interní start vyžaduje `proposed_value: running`, pause `paused`. `current_value` musí odpovídat aktuálnímu stavu. Editace nemění typ akce; nekonzistentní upravený payload nebude proveden. U externích zásahů se `change_scope` `ad_copy`, `landing_content` nebo `campaign_creative` klasifikuje YELLOW (nebo RED, pokud to správce požaduje). `product_price`, `payment`, `domain`, `legal`, `delete_campaign` a neznámý scope jsou RED. Rozpočet je vždy RED.

```json
{"decision": "approve", "confirmation": "<presne-ACT-id-pro-RED>"}
```

Externí schválení vrací `manual_action_required`. Interní schválení uloží `executed`, přesný původní a nový stav, správce a čas v jedné transakci. Druhé schválení se odmítá. Rollback je dostupný pouze u interní změny a pouze pokud se aktuální stav neliší od provedeného.

## Interní limity

`daily_limit`, `monthly_limit`, `max_cpa`, `target_cpa`, `min_roas`, `target_roas`, `minimum_purchases`. Všechna pole posílejte současně. Počet objednávek musí být celé číslo ≥ 1. Cílové CPA nesmí být větší než nenulové max CPA. Žádná integrace schopná utrácet není v MVP aktivní; změna interních limitů nezmění externí rozpočty.

## Opt-in

`POST /api/leads` vyžaduje `email`, `source` (HTTPS), `relevance`, `consent: true`, přesný `consent_text` a `consent_version`. Vrací jednorázový `confirmation_token`; token je v DB pouze jako SHA-256 hash. E-mail nebyl odeslán. `POST /api/leads/confirm` přijímá `{ "token": "…" }` v autentizované administraci; v MVP nejde o veřejný self-service formulář. Token nesmí být zaměněn za důkaz delivery nebo zákaznického kliknutí.
