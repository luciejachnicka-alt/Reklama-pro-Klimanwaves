# Bez placeného hostingu: PythonAnywhere

Pro malý pilot je připravena WSGI varianta pro **bezplatný účet PythonAnywhere (Beginner)**. Ukládá SQLite databázi do vašeho uživatelského adresáře, ne do dočasného disku Render Free. PythonAnywhere zajišťuje webový server a HTTPS na přidělené subdoméně.

**Žádný účet ani veřejná aplikace zatím nebyly vytvořeny.** Aktuální cenovou stránku a podmínky poskytovatele se zde nepodařilo načíst kvůli HTTP 403 ze síťového proxy. Při registraci ověřte, že vybíráte skutečně bezplatný tarif a jaké má aktuální limity. Pokud vám poskytovatel nabízí jen placený plán, nepokračujte s platbou.

## Co udělat

1. Na **https://www.pythonanywhere.com/** si založte bezplatný účet. Heslo zadávejte pouze u poskytovatele. Není potřeba posílat ho do chatu.
2. V **Consoles → Bash** načtěte veřejný repozitář:

```sh
git clone https://github.com/luciejachnicka-alt/Reklama-pro-Klimanwaves.git
cd Reklama-pro-Klimanwaves
python3 -m unittest discover -s tests -v
```

3. Na kartě **Web** vytvořte webovou aplikaci: **Add a new web app → Manual configuration → Python 3.12**, pokud je tato verze ve vašem účtu dostupná. Projekt nepotřebuje Flask/Django ani pip balíčky. Použijte skutečnou HTTPS adresu zobrazenou na kartě Web, nikoli doménu odhadnutou podle jména. Regionální varianta poskytovatele může používat jinou subdoménu.
4. V Bash konzoli v adresáři projektu vygenerujte konfiguraci. Následující URL nahraďte skutečnou adresou vašeho webu:

```sh
python3 scripts/pythonanywhere_setup.py --origin https://VASE-ADRESA.pythonanywhere.com --output /tmp/klimanwaves-wsgi.py
cat /tmp/klimanwaves-wsgi.py
```

Výstup neobsahuje hesla ani přístupové klíče. Pokud konfiguraci vytváříte podruhé, použijte nový název souboru; pomocník existující soubor nepřepíše.

5. Na kartě **Web** otevřete poskytovatelem vytvořený **WSGI configuration file**. Před úpravou si uschovejte jeho původní obsah. Nahraďte jej vygenerovanou konfigurací a uložte. Pro tento nový samostatný web je to vstupní soubor aplikace; neupravujte konfiguraci jiné existující aplikace.
6. Klikněte **Reload** a otevřete přidělenou HTTPS adresu. První úspěšné načtení vytvoří adresář `/home/VASE-JMENO/.klimanwaves` s databází a soukromými klíči. Přístupový klíč aplikace najdete ve své konzoli:

```sh
cat ~/.klimanwaves/admin-token
```

Tento druhý výstup **je tajný**: pouze ho vložte do přihlašovacího pole aplikace. Nekopírujte ho do chatu, GitHubu nebo veřejného WSGI souboru. Jde o klíč aplikace, nikoli heslo k Shoptetu. Alternativně lze správcovský token injektovat prostřednictvím `APP_ADMIN_TOKEN`, pokud váš hosting umožňuje bezpečné environment secrets.

## Co ověřit

- Přidělená HTTPS adresa zobrazí přihlášení; `/api/health` vrací `status: ok`.
- Bez přihlášení vrací `/api/state` HTTP 401. Přihlášení má cookie Secure, HttpOnly a SameSite=Strict.
- Po opětovném **Reload** se zachovají uložené produkty a data. Nevyměňujte ani nemažte adresář `.klimanwaves` při aktualizaci zdrojů.
- Pro aktualizaci zkontrolujte vlastní změny, aktualizujte zdrojový kód a použijte Reload. Přístupový klíč neukládejte do repozitáře.
- Zálohujte databázi konzistentně pomocí SQLite backup API. Trvalý uživatelský adresář není sám o sobě záloha.

## Omezení varianty zdarma

- Limity úložiště, výkonu, odchozí sítě a doby platnosti webové aplikace určuje poskytovatel. Bezplatný web může vyžadovat pravidelné ruční prodloužení; řiďte se upozorněním na kartě Web. Nejde o garantovaný nepřetržitý provoz.
- **WSGI varianta nespouští hodinový scheduler.** Vyhodnocení spouštíte tlačítkem v aplikaci. Bezplatné background workers/always-on jobs nepředpokládáme.
- Dosažitelnost Shoptet/Google/Meta API z bezplatného hostingu není ověřena. Bezplatné účty mohou omezovat odchozí HTTPS. Ruční vložení produktů, objednávek a reklamních výsledků funguje bez externích API.
- Shoptet, reklamní účty a AI model stále nejsou připojené. Hosting je nezapojí automaticky.
- Reklamní útrata a případné pozdější placené AI API nejsou součástí bezplatného hostingu.
- Varianta je pro malý pilot s jedním správcem. Při vyšší návštěvnosti, zpracování většího množství osobních údajů nebo více uživatelích bude potřeba odpovídající hosting, zálohy a autentizace.

## Stav ověření

Lokálně prošlo 33 testů: stávající API testy a nové kontroly WSGI kompatibility, přihlášení, bezpečnostních hlaviček, měření a zachování dat/session po opětovném vytvoření WSGI aplikace. Nasazení na skutečný PythonAnywhere účet ani aktuální dostupnost bezplatného tarifu zatím ověřeny nejsou. Definitivní veřejný odkaz poskytne až váš vytvořený a otestovaný web.
