# Architektura a další fáze

## Implementováno

| Vrstva | Umístění | Chování |
|---|---|---|
| Frontend | `app/static/` | České HTML/CSS/JS; formuláře, schvalování, výsledky |
| Backend / autentizace | `app/server.py` | JSON HTTP API, token správce, HMAC podepsaná session, same-origin kontrola |
| Databáze | `app/schema.sql`, `app/store.py` | SQLite WAL, foreign keys, atomické importy, audit |
| Ekonomika a analytika | `app/domain.py`, `Store.snapshot` | Jednotkové náklady, historické snapshoty, KPI bez dělení nulou |
| Approval engine | `Store.create_action`, `Store.decide` | GREEN interní analýza; YELLOW konkrétní schválení; RED ID potvrzení |
| Learning loop | `Store.analyze` | Hypotéza → vlastní importovaná data → doložené zjištění → další hypotéza |
| Scheduler | `server.main` | Každou hodinu při běhu procesu; ruční API trigger |
| Ingestion / integrace | `/api/import/*`, `/api/track` | Autentizované importy; browser události se souhlasem |

Žádný agent nemá přímou pravomoc měnit externí platformu. Stav `executed` vzniká pouze po úspěšné databázové transakci interní změny. Rollback porovná aktuální stav s aplikovaným stavem a odmítne přepsat pozdější změnu.

Interní experiment `running` je evidence testu, nikoli potvrzení aktivní kampaně. Pokud pravidla navrhnou jeho pozastavení, schválení zastaví pouze evidenci. Externí kampaně je třeba měnit ručně až do implementace příslušného adaptéru.

## Fáze 2: oficiální externí adaptéry

Po ověření aktuální dokumentace doplnit OAuth authorization-code flow se state/PKCE dle platformy, minimální scopes, secrets manager pro refresh/access tokeny, bezpečný callback a kontrolu identity účtu. Nevytvářet maketu připojení vydávanou za hotovou autorizaci.

Každý adaptér potřebuje explicitní capability registry: read orders, read ad metrics, update copy, pause campaign, budget change, rollback. Před zápisem získat aktuální stav, zkontrolovat schválený payload a limity, provést API request, uchovat potvrzení a následně read-back. Timeout znamená nejasný výsledek, vyžaduje reconcile; ne opakovaný slepý zápis. Externí fronta musí podporovat idempotency, souběh, retry a oddělené stavy approved/executing/executed/failed/unknown.

Shoptet nelze považovat za obecně zapisovatelné CMS. Oprávnění konkrétního doplňku a oficiální operace musí doložit každou změnu. Nepodporované zásahy zůstávají `manual_action_required`.

## Fáze 3: AI a kreativita

Oddělená AI vrstva má přijímat pouze ověřené produktové profily a vlastní výsledky. Výstup musí mít validované schema: concept, angle, audience, hook, script, shot list, on-screen text, copy, headline, CTA, landing page, hypothesis, success metric. U každé inspirace evidovat URL, datum, obecný princip a vlastní originální zpracování. Výkon cizí reklamy nesmí být tvrzen bez ověřitelných dat. Model nesmí mít přístup k publikačnímu adaptéru ani secretům.

## Fáze 4 / SaaS

PostgreSQL s tenant isolation, individuální uživatelé/role, managed auth, job queue, externí audit, šifrované credentials, observabilita, zálohy, retention a export/výmaz. Kontrolované experimenty, minimální vzorky, data o refunds/stornech a statistické vyhodnocení. Učení musí oddělovat pozorování a kauzální závěry.
