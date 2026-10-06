# Consent-aware tracking

SDK je připravené, ale **není nainstalované do vašeho e-shopu**. Nevkládejte ho bez schválení. Nejprve zjistěte existující CMP a tracking, aby nedošlo k duplicitnímu měření.

1. Nasaďte backend na vlastní HTTPS doméně a nastavte přesný `APP_PUBLIC_ORIGIN` a `SHOP_ORIGIN`.
2. Po schválení v podporovaném Shoptet custom-code umístění nastavte `window.KlimanwavesConfig = { endpoint: 'https://<vas-backend>/api/track' }` a načtěte `tracker.js`. Ověřte, že Shoptet skutečně umožňuje tento způsob vložení a že CSP obchodu dovoluje skript i HTTPS requesty.
3. Z callbacku skutečné cookie consent platformy volejte `Klimanwaves.setConsent(true)` pouze při uděleném analytickém souhlasu. Při odvolání volejte `setConsent(false)`; vlastní sessionStorage se vymaže. SDK nečte ani neukládá tracking identifikátory před souhlasem.
4. Na produktové stránce volejte `Klimanwaves.track('product_view')`, po **potvrzeném** přidání produktu `track('add_to_cart')`, při skutečném zahájení checkoutu `track('checkout')`. Nenavazujte košík pouze na click tlačítka, který může selhat.
5. Přidávejte UTM parametry, zejména `utm_content=<CR-id>`. ID musí existovat. Při změně UTM se atribuce aktualizuje; nejde o multi-touch attribution. Session je sessionStorage identifikátor v rámci tabu prohlížeče, nikoli GA4 session.
6. Události zakupování a tržeb potvrzujte pouze autentizovaným importem skutečných objednávek. Pokud lze skutečně uchovat a přenést session_id do objednávky, přidejte je do importu; jinak CVR nepovažujte za známé.

Browser endpoint kontroluje origin a rate limit, ale CORS nebrání falšování requestů mimo prohlížeč. Události proto nesmějí být jediným zdrojem finančního rozhodnutí. SDK má event ID pro deduplikaci; síťové chyby nepotvrzuje jako úspěch. Offline fronta/retry delivery není implementována.

Impressions/clicks/spend pocházejí z denních exportů reklamních platforem. Funnel zobrazuje počty různých zdrojů, nikoli zaručený cohort. Propojení s GA4, Google Ads a Meta CAPI vyžaduje další implementaci, souhlasové signály a oprávnění.

Do browser SDK nevkládejte API secrets, admin token, e-maily, telefonní čísla ani jiná osobní data. Před produkčním provozem nastavte účel, souhlasové texty, retention a odpovídající informační povinnosti.
