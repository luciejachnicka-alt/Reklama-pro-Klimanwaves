# Propojení Klimanwaves se Shoptetem

Ověřeno 6. října 2026. Uživatel potvrdil běžný Shoptet, nikoli Premium.

Oficiální dokumentace:
- https://developers.shoptet.com/api/basic-information/ – API přes partnerské doplňky.
- https://developers.shoptet.com/api/documentation/creating-the-addon/ – partnerský účet po smlouvě; doplněk před instalací potřebuje schválení Shoptetu.
- https://developers.shoptet.com/home/premium/private-api/ – soukromé API pro Premium.
- https://developers.shoptet.com/shoptet-tools/data-export/ – produkty, zákazníci a objednávky lze exportovat. Produkty: Produkty → Export, XML/CSV/XLSX.

Veřejná homepage https://819636.myshoptet.com odpověděla HTTP 200 a má titul Klimanwaves. Standardní veřejný Heureka feed /heureka/export/products.xml vrátil HTTP 403; katalog nebyl stažen. Nejde o API autorizaci ani důkaz přístupu k objednávkám.

Aplikace není schválený Shoptet doplněk. Nebyl vytvořen partnerský účet, uzavřena smlouva ani získána OAuth oprávnění. Automatické propojení tedy není aktivní. Heslo k administraci toto omezení nenahrazuje.

Pro plné propojení je nutné získat partnerský přístup a schválení doplňku s minimálními oprávněními pro čtení produktů a objednávek, následně implementovat OAuth, obnovu API tokenů a synchronizaci. Vyhodnotit také omezení odchozího přístupu bezplatného hostingu. Žádný upgrade není autorizován.

Alternativou bez upgradu je import exportovaných souborů. Současná aplikace má vlastní JSON import objednávek, nikoli hotový parser exportů Shoptetu. Ten je třeba připravit proti skutečnému formátu. Před implementací získat anonymizovaný vzorek či hlavičky exportu bez zákaznických údajů; nepředstírat objednávkové stavy, DPH, storna, slevy, nákupní náklady nebo marži. Pravidelný exportní odkaz může obsahovat tajný přístupový klíč: patří do zabezpečeného nastavení, nikdy do chatu, logů či zdroje.
