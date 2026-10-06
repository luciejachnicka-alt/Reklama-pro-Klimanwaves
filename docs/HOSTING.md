# Jak získat veřejný odkaz na aplikaci

Doporučená první varianta: **Render, jedna Docker webová služba a trvalý disk**. Render poskytne HTTPS adresu; vlastní doménu zatím nepotřebujete. Jde o placenou variantu — službu nevytvářejte bez kontroly aktuální ceny a platebních podmínek. Žádný účet, placená služba ani veřejná adresa nebyly tímto projektem automaticky vytvořeny.

## Co je již připraveno

- `Dockerfile` bez dodatečných Python balíčků.
- `render.yaml`: jedna služba, evropský region, trvalá SQLite databáze na `/data`, health check a automaticky generovaný správcovský secret.
- Spuštění odmítne chybějící secret nebo neplatnou HTTPS adresu. Aplikace běží pod neprivilegovaným uživatelem; cookies mají při HTTPS adresaci příznak Secure.
- Lokální databáze, tokeny, `.env` a Git metadata se nekopírují do obrazu ani do předávacího archivu.

To je připravená konfigurace, nikoli důkaz úspěšného nasazení na Renderu. Provozní test veřejného HTTPS musí následovat po vytvoření služby.

Lokální ověření kontejneru:

```sh
docker --config /tmp/klimanwaves-docker-config build --tag klimanwaves-pilot:local .
python3 scripts/container_check.py
```

Test používá náhodný testovací secret, vlastní dočasný Docker volume a testovací produkt; po dokončení kontejner i volume odstraní. Nedotýká se obchodních dat v `.local/`.

Ověřeno lokálně: 28 unit/integration testů, sestavení Docker obrazu, skutečné HTTP přihlášení v kontejneru, ochrana nepřihlášených požadavků, cookie flags, odmítnutí cizího originu, neprivilegovaný serverový proces a zachování databáze i session po restartu. Vzdálený Render deployment dosud neproběhl.

Blueprint má připravené běžné konfigurační položky, ale aktuální oficiální specifikaci Renderu se v tomto prostředí nepodařilo načíst (proxy HTTP 403). Jeho validaci i cenu ověří poskytovatel při vytváření služby. Lokální kontejnerový test neprokazuje validaci Blueprintu nebo dosažitelnost veřejného HTTPS.

## Postup pro první nasazení

1. Vytvořte si účet na **https://dashboard.render.com/**. Přihlášení provádějte přímo u poskytovatele; heslo neposílejte do chatu.
2. Do svého GitHub repozitáře `luciejachnicka-alt/Reklama-pro-Klimanwaves` nahrajte zdrojové soubory tohoto projektu včetně `Dockerfile`, `render.yaml`, složek `app/` a `scripts/hosting_start.py`. V GitHubu použijte **Add file → Upload files**, nebo standardní Git push. Nikdy nenahrávejte `.local/`, `.env` nebo přístupové klíče. Samotné vložení ZIPu do repozitáře nestačí; zdroje musí být rozbalené v kořeni.
3. V Renderu zvolte **New → Blueprint**, propojte svůj GitHub účet a vyberte tento repozitář a větev se zdrojovým kódem. Oprávnění GitHubu udělte přes oficiální autorizační obrazovku.
4. Projděte navrženou službu a trvalý disk. Ověřte aktuální cenu, region a velikost disku. Konfigurace používá placený plán `starter`, není to bezplatný hosting. Teprve potom potvrďte vytvoření služby.
5. Po úspěšném buildu otevřete skutečnou HTTPS adresu, kterou Render zobrazí u služby. Neodhadujte adresu podle názvu služby. Aplikace si tuto adresu načte z `RENDER_EXTERNAL_URL`; pro vlastní doménu nastavte `APP_PUBLIC_ORIGIN` na její přesnou HTTPS adresu.
6. V prostředí služby najděte bezpečně generovaný `APP_ADMIN_TOKEN` a vložte jej do pole **Přístupový klíč aplikace**. Hodnotu nepište do chatu ani do GitHubu. Nové nasazení začíná prázdnou databází.

Pokud chcete zdroje nahrát z připraveného archivu, nejprve jej lokálně rozbalte. Obsahuje jen soubory potřebné pro aplikaci a dokumentaci, žádná obchodní data ani tajné klíče.

## Kontrola po nasazení

- Veřejný `/api/health` vrací `status: ok`, hlavní stránka zobrazí přihlášení.
- Nepřihlášený `/api/state` vrací HTTP 401. Po přihlášení funguje přehled a pole tokenu se vymaže.
- Přihlášení z cizího originu se odmítá. Session cookie má HttpOnly, SameSite=Strict a Secure.
- Restartujte pouze vlastní službu a ověřte, že existující data zůstala. SQLite disk je nutný; bez něj by aktualizace aplikace ztratila data.
- Nezadávejte reálné zákaznické kontakty před kontrolou účelu, retention a souhlasů. Shoptet, reklamní platformy a AI model zůstávají nepřipojené; nasazení samo je neaktivuje.

Tato konfigurace je pro malý pilot s jedním správcem, za spravovanou HTTPS proxy. Standard-library HTTP server není určen pro velkou návštěvnost. Horizontální škálování SQLite a více replik nejsou podporovány; pro větší provoz je potřeba produkční aplikační server, databáze a oddělené jobs.

## Databázové zálohy

Vytvářejte konzistentní zálohy přes SQLite backup API na připojeném disku a přenášejte je do zabezpečeného úložiště. Nekopírujte živý `.sqlite3` soubor samostatně bez jeho WAL stavu. Secret správce není potřeba zálohovat v souboru: jeho platná hodnota je v secrets hostingu. `session-key` ponechte na trvalém disku; při jeho změně budou uživatelé potřebovat nové přihlášení.
