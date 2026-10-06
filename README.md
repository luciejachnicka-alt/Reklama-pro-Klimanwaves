# Klimanwaves Growth Studio

Funkční MVP první fáze marketingového a sales agenta pro český Shoptet obchod. Priorita: objednávky se zdravou ekonomikou. Aplikace je API-first, bez placených runtime závislostí: Python 3.12+, SQLite a české responzivní webové rozhraní.

## Co funguje

- Produktové profily s doloženým zdrojem a nastavením nákladů; úprava interní ekonomiky bez změny ceny v e-shopu.
- Výpočet příspěvku, break-even CPA, reklamních CPA, ROAS, CPC, CTR a konverze. Historické objednávky uchovávají původní náklady.
- Experimenty s unikátním Creative ID, hypotézou, publikem, hookem, kreativním briefem a metrikou úspěchu.
- Atomický import skutečných objednávek a denních reklamních metrik. Deduplikace objednávek; konfliktní ID import odmítne.
- Consent-aware first-party tracker pro landing page, produkt, košík a checkout. Nákupy a tržby se nepřijímají z veřejného browser endpointu.
- Action Center: upravit, schválit, zamítnout; zásadní změny vyžadují explicitní potvrzení ID. Interní změny mají rollback se zjišťováním konfliktu.
- Audit původního a nového stavu, času a autentizovaného správce.
- Pravidlová analýza vlastních výsledků, znalostní báze s doloženými metrikami a návrhy pozastavení ztrátových interních testů. Analýza běží ručně a každou hodinu během provozu serveru.
- Evidence opt-in kontaktů, jednorázové potvrzení tokenem, výmaz. Žádné automatické odesílání e-mailů.

## Spuštění

Použijte existující checkout; cloudová úloha je již izolovaná, nevytvářejte další Git worktree.

```sh
cd /workspace/Reklama-pro-Klimanwaves
python3 -m unittest discover -s tests -v
python3 -m app.server --port 8000
```

Server standardně naslouchá jen na loopbacku. Přihlašovací obrazovka vyžaduje náhodný správcovský token z `.local/admin-token`; otevřete jej pouze v důvěryhodném terminálu a vložte do přihlašovacího pole. Token neposílejte do chatu ani nevkládejte do e-shopového JavaScriptu. Pokud je nastaveno `APP_ADMIN_TOKEN` (alespoň 32 znaků), použije se tento secret místo souboru. Hodnoty tokenů nejsou v repozitáři ani v logu.

První spuštění vytvoří prázdnou SQLite databázi `.local/marketing.sqlite3` a privátní adresář s oprávněním 0700. Server neposkytuje testovací marketingové výsledky. Testy pracují s oddělenými dočasnými databázemi.

Pro interní readiness kontrolu použijte `GET /api/health`; ověřte také přihlášení a `GET /api/state`, nikoli jen otevřený port. Instalační krok pro běh nepotřebuje síť ani pip/npm.

Volitelné ověření UI v prostředí s Playwright a Chromium:

```sh
python3 scripts/browser_check.py
```

## První skutečný experiment

1. V **Produkty a ekonomika** přidejte skutečný produkt, zdroj ověřených informací a náklady.
2. V **Experimenty** zapište hypotézu a originální kreativní brief. V detailu získáte odkaz s Creative ID v `utm_content`.
3. Navrhněte spuštění interního testu a schvalte jej v **Action Center**. To nepublikuje reklamu ani nemění e-shop.
4. V **Data a integrace** importujte skutečné dokončené objednávky a reklamní export podle [API schémat](docs/API.md).
5. Spusťte analýzu. Znalostní báze vyžaduje nastavené minimum přiřazených objednávek; nula objednávek není důkaz vítězného konceptu.

## Jednodušší rozhraní

Na přehledu vás provede trojice kroků: **přidat produkt → doplnit výsledky → vyhodnotit**. Při chybějících datech vidíte pomlčku, ne vymyšlené nulové výsledky. Rozpočty a metriky jsou popsané běžnou češtinou; vysvětlivky najdete pod výsledky.

Obrazovka **Odkud jsou data** ukazuje počty vložených produktů, objednávek a denních reklamních výsledků a pravdivý stav propojení. Jednu objednávku nebo denní výsledky reklamy můžete zapsat běžným formulářem. Hromadný JSON import zůstává dostupný jako pokročilá možnost. Datum objednávky v jednoduchém formuláři se převádí z časového pásma vašeho prohlížeče do UTC.

**Návrhy ke schválení** jsou původní Action Center a **Reklamní testy** původní Experimenty. Výpočetní pravidla a finanční ochrany se nemění. Přístupový klíč aplikace není přihlášení do Shoptetu. Aplikace nikdy nežádá e-mail a heslo k Shoptet administraci.

## Stav a hranice MVP

Veřejný e-shop `https://819636.myshoptet.com` ani oficiální dokumentace API se při vývoji nedaly načíst: síťový proxy vrátil HTTP 403. Struktura, produkty, ceny, košík, doprava, mobilní UX a dostupné zapisovací operace proto **nejsou ověřeny**. Podrobnosti jsou v [analýze a integračním plánu](docs/RESEARCH.md). Po zpřístupnění domén je nutné audit doplnit z konkrétních zdrojů.

MVP **nemá připojený Shoptet, GA4, Google Ads, Merchant API ani Meta Ads**. Nemá hotový OAuth flow ani externí zapisovací adaptér. Schválené externí změny mají stav `manual_action_required`, nikdy `executed`. Neutrácejí peníze a nedeklarují úspěšnou publikaci. Skutečné publikační a reklamní integrace jsou druhá fáze a vyžadují ověření aktuální dokumentace a oprávnění.

MVP používá transparentní analytická pravidla. **AI model, Creative Intelligence a automatická Creative Factory nejsou připojeny**; patří do třetí fáze. Znalostní báze ukládá pozorování, nikoli kauzální závěry. Následné pokročilé testování a optimalizace patří do čtvrté fáze.

Tracking SDK je implementováno a otestováno lokálně, ale **není instalováno do vašeho Shoptetu**. Instalace vyžaduje HTTPS hosting, schválení a skutečné napojení CMP a e-shopových událostí. Nikdy automaticky nepředpokládá analytický souhlas.

## Nasazení a bezpečnost

**Varianta bez placeného hostingu:** připravena WSGI aplikace pro PythonAnywhere. Viz [postup pro bezplatný účet](docs/FREE_HOSTING.md). V této variantě se výsledky vyhodnocují ručně tlačítkem; hodinové background jobs neběží. Aktuální dostupnost a podmínky bezplatného tarifu je nutné ověřit u poskytovatele. Veřejná aplikace zatím není nasazena.

Jako alternativní **placená** varianta je připravena Docker konfigurace a Render Blueprint s trvalým diskem. Viz [postup Renderu](docs/HOSTING.md). Nepoužívejte tuto alternativu, pokud chcete provoz zdarma. Připravený balíček sám neznamená, že aplikace má veřejnou adresu.

- Jediný správce v této fázi; audit rozlišuje autentizovaného správce, nikoli více osob. Nejde o hotové víceklientské SaaS. Pro SaaS budou potřeba tenant isolation, individuální role, spravovaná autentizace a externí audit.
- Pro veřejný provoz nastavte `APP_PUBLIC_ORIGIN=https://vase-domena`, nasaďte ověřenou HTTPS reverse proxy a případně spusťte `--host 0.0.0.0`. Cookie pak dostane `Secure`, vždy má `HttpOnly` a `SameSite=Strict`. Nepoužívejte samotný standard-library HTTP server jako veřejnou produkční infrastrukturu.
- API token lze použít v `Authorization: Bearer …`. Chraňte jej v secrets manageru, ne v URL. Přihlášení je rate-limited; session platí osm hodin.
- `SHOP_ORIGIN` určuje jediný povolený browser tracking origin. CORS **není důkaz pravosti události**; prohlížečové metriky mohou být zfalšovány, proto nedokládají nákupy a příspěvek.
- Consent, retention, výmaz, texty souhlasu a ověřený double-opt-in delivery flow je třeba nastavit před produkčním lead sběrem. MVP pouze eviduje kontakty vložené přihlášeným správcem. Potvrzovací token se doručuje ručně, e-mail se neposílá.
- SQLite a audit nejsou zašifrované na úrovni aplikace; pro produkci použijte šifrovaný disk/managed DB, zálohy a oddělený audit. Adresář `.local/` uchovává obchodní data; necommitujte jej.
- Rozpočtové limity kontrolují importované náklady a doporučení. Bez externích API **neomezují útratu na reklamních platformách**.

## Ekonomické předpoklady

Prodejní cena i importované produktové tržby obsahují DPH. Nákupní a další náklady jsou **bez odpočitatelné DPH**. Neplátce nastaví DPH na 0 a náklady na skutečnou hrazenou částku. Náklady jsou v této verzi alokované na jednotku, včetně fixního platebního poplatku a dopravy. Příjmy z dopravy nejsou modelovány; náklad dopravy zadejte jako čistý náklad obchodu po jejím příjmu. Fixní náklady, mzdy a daň z příjmu nejsou zahrnuty.

Importujte pouze dokončené, nezrušené objednávky bez refundací. Zpracování skutečných refundací, storna a změn objednávek vyžaduje další datový adaptér; aktuálně je lze promítnout jen konzervativním odhadem nákladů vratek. Nepoužívejte odhad příspěvku jako účetní výsledek.

Dashboard zobrazuje celé dostupné období. Celkové CPA/ROAS jsou smíšené poměry všech objednávek a importované útraty. Reklamní experimenty používají pouze objednávky s vlastním Creative ID. CVR se počítá z unikátních měřených sessions, které lze spárovat s importovaným `session_id`; bez vazby je neznámé. Počty jednotlivých stupňů funnelu nejsou uzavřený cohort funnel.

## Struktura

Viz [architektura](docs/ARCHITECTURE.md), [API](docs/API.md) a [tracking](docs/TRACKING.md).

### Přihlášení vlastním heslem
Při prvním přihlášení použijte soukromý přístupový klíč a nastavte heslo přímo v aplikaci (alespoň 12 znaků). Další přihlášení funguje heslem i na telefonu. Změna hesla je v Rozpočtu a cílech. Původní klíč uchovejte pro obnovu; nezveřejňujte jej. Heslo se ukládá jako scrypt otisk, změna odhlásí ostatní relace. Kódy přes e-mail nejsou zapojené. Přihlášení nepropojuje Shoptet: data se zatím vkládají ručně.
