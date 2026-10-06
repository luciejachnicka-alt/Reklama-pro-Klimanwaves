# Ověření e-shopu a integrací

Datum: 6. října 2026. Použita standardní HTTPS cesta prostředí; TLS ověření nebylo vypnuto.

| Zdroj | Výsledek |
|---|---|
| `https://819636.myshoptet.com` | Proxy CONNECT odmítnut: HTTP 403 |
| `https://developers.shoptet.com/api/` | Proxy CONNECT odmítnut: HTTP 403 |
| `https://developers.google.com/analytics/devguides/collection/protocol/ga4` | Proxy CONNECT odmítnut: HTTP 403 |
| `https://developers.google.com/google-ads/api/docs/oauth/overview` | Proxy CONNECT odmítnut: HTTP 403 |
| `https://developers.google.com/merchant/api/overview` | Proxy CONNECT odmítnut: HTTP 403 |
| `https://developers.facebook.com/docs/marketing-apis/` | Proxy CONNECT odmítnut: HTTP 403 |

Repozitář na GitHubu byl původně prázdný; HTTPS Git přístup fungoval. Nebyl požadován další GitHub token. V runtime nebyly přítomny potřebné Shoptet, Google, Meta ani AI credentials. Hodnoty existujících proměnných se nevypisovaly.

Do návrhu síťové konfigurace byly přidány domény `819636.myshoptet.com`, `developers.shoptet.com`, `developers.google.com`, `developers.facebook.com`. Existující preset pro package managers byl zachován. Uložení návrhu samo neaktivuje runtime síťovou konfiguraci.

## Co zatím nelze tvrdit

Nejsou ověřeny produkty, ceny, benefity, doprava, recenze, důvěryhodnost, košík, checkout, mobilní UX ani konverzní překážky. Produktová databáze proto nezačíná vymyšleným katalogem. Není ověřena aktuální dostupnost oficiálních API operací, scopes, endpointů, platebních plánů ani zápisových práv.

## Po zpřístupnění webu

1. Načíst homepage a veřejné produktové a informační stránky. Evidovat URL, datum a konkrétní pozorování.
2. Ověřit produktové parametry, varianty a ceny; odlišit fakta od hypotéz cílových skupin a námitek.
3. Prověřit mobilní viewport, CTA, skutečný košík a kroky checkoutu bez dokončení nákupu. Netvořit objednávku bez konkrétního schválení.
4. Ověřit současnou cookie consent implementaci a existující tracking. Nepřidávat duplicitní měření.
5. Z aktuální dokumentace sestavit capability matrix a požádat pouze o nutná oprávnění přes bezpečný connection flow. Přihlášení do administrace ani heslo se nevyžaduje v chatu.

## Integrační požadavky k ověření ve fázi 2

- **Shoptet:** přístup k oficiálnímu API pro konkrétní e-shop/doplněk, čtení objednávek a produktů. Možnost zápisu obsahu ověřit, nepředpokládat.
- **GA4:** property identity, consent konfigurace a oprávnění číst analytická data. Measurement Protocol pro odesílání serverových událostí není zdrojem reportů; reporting vyžaduje samostatný přístup.
- **Google Ads:** autorizace účtu, developer access a oficiální scopes. Reporting a zápisy implementovat odděleně; budget mutation musí podléhat RED schválení a limitům.
- **Merchant:** používat aktuální Merchant API, ověřit account a produktový feed. Stav feedu není důkaz výkonu reklamy.
- **Meta:** oprávnění reklamního účtu a token získaný oficiálním flow. Ověřit oprávnění, API verzi a app-review požadavky.

Tento seznam je plán integrací, nikoli tvrzení, že aktuální API možnosti byly ověřeny.

## Aktualizace ověření
Dne 6. října 2026 po aplikaci síťové konfigurace odpověděla homepage e-shopu a dokumentace Shoptetu HTTP 200. Dřívější síťový blok už pro tyto adresy neplatí. Výsledky a zbývající překážky propojení jsou v SHOPTET.md. Kompletní audit e-shopu nebyl proveden.
