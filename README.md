# AKÉP
A mostani mayor verzióváltást követően a readme.md frissítése szükséges
 
## Rövid leírás:
AKÉP=Automatikus kiértékelő és pontozó rendszer.

Az AKÉP egy olyan nyílt forráskódú pythonban készült támogató keretrendszer, mely segíti a javítókat abban, hogy a hallgatók munkáját önműködően javítja és értékeli. A javítók lényegében a saját javítási mechanizmusukat ültethetik át könnyen egy technológia független\* környezetbe, tetszőleges értékelési eljárásokkal. Az AKÉP akár egy beadó rendszer mögé is helyezhető és minden egyes feladatbeadás után értékelheti és továbbíthatja az eredményeket, kapcsolatot teremtve a környezetével. A részletek lentebb olvashatóak.

### A technológia független környezet:
Az AKÉP keretrendszere már csak szöveg alapú környezetben dolgozik, így a különböző forrásokból (pl. Java program, egy egyedi script, stb.) származó eredmény előállításáért úgynevezett előfeldolgozók \(preprocesszorok\) felelősek. Az AKÉP ezeket futtatva, vezérelve érheti el az adott technológiában készült feladatsorok kimenetét \(a kimenetben elválasztva a feladatokat\). Az előfeldolgozók segítségével a javítási és értékelési logika leírása technológia független tud maradni.

## Futtatás:

```shell
python3 main.py -p CONF_PATH - l LOG_PATH -s ECERCISE_SCHEMA_PATH -c CHANNEL_INPUT_SCHEMA_PATH
```

**CONF_PATH**: Itt keresi a lokális konfigurációs fájlt. \(str, opt, def='./akep.local.cfg'\)

**LOG_PATH**: A logolást ide fogja írni egy fájlba. \(str, req, def='./akep.log'\)

**ECERCISE_SCHEMA_PATH**: Itt keresi a feladatleíró xml-ek megkövetelt sémáját \(str,req,def='../schema/akep-exercises.xsd'\)

**CHANNEL_INPUT_SCHEMA_PATH**: Itt keresi a csatornák bemenetének megkövetelt sémáját (amennyiben az adott csatona így van konfigurálva)\(str, opt, def: '../schema/akep-XMLChannel.xsd'\)

### Futtatás menete:
1.	Elindítás a fent megadott módon. Amennyiben nem talál maga mellett akep.cfg-t a main.py hibával kilép. (részletek lejjebb)
2.	Az AKÉP a meghatározott porton és interfészen várja a parancsokat (lejjebb található)
3.	Párhuzamosan hajtja végre a kapott parancsokat, az eredményt pedig a parancsot adó socketen küldi vissza.

### AKEP.cfg
Minimális meg kell adni a következő kulcs érték párokat: Ezek a kulcsok egyébként foglaltak a configurációs hierarchiában nem írhatók felül
"host":"a cím amin figyel",
"port":a port amin figyel (int),
"exercisesPath":"a feladatleírók elérési helye",
Ez itt opcionális de ugyenúgy a beépített kezelt kulcsok közé tartozik
"notCopyFromDescrtiption":["script","info","exerciseKeys"] -> ezeket a tag-eket nem teszi bele az értékelés utáni kimenetbe a feladatleíróból
}

## Parancsok (socket csatlakozása után):
-	Feladat beadása JSON objektumban történik:
	`{"ownerID":"user","exerciseID":"id","runUserGroup":"normal","solutionDir":"./sol"}`
	Ebből az objektmból az ownerID és az exerciseID meghatározása kötelező is lehetne, de igazából az akép a konfigurációs láncon végigmegy amikor lekér egy kulcshoz tartozó értéket, így ha az ott van pl. az akep.local.cfg-ben akkor nincs gond (bár ez elég értelmetlen eset)
-	Socket lezárása: Az AKÉP automatikusan lezárja a socketet és visszaküldi a kiértékelést

## Feladatleírók (feladatsorok/feladatlapok) felépítése:
`akep-exercise.xsd`

**Megjegyzés**: Az opcionális paraméterek (pl. tasktext, description) belekerülnek a feladatstruktúrának megfelelően a kimenetbe is, így azok felhasználhatók egy a javítóknak szánt áttekintő felületen megjelenített tartalomba az értékelés eredménye és mechanizmusa mellett. Javasolt itt leírni a feladatokat emberi megfogalmazásban a javítási mechanizmust is, hogy az tetszőleges feladatlap generálására is felhasználható legyen (javítónak, hallgatónak, stb.).

## AKÉP feldolgozási folyamat
TODO

## Csatornába érkező adat konfigurálása:

### INLINE típusú csatornánál:
TODO

### EXTARNAL típusú csatornánál:
TODO

### CHANNELOUTPUT típusú csatornánál:
TODO

## A keretrendszer által adott kimenet:
Megegyezik a feladatleíró tartalmával a következőket kivéve:
- Minden solution tag parent task tagjébe bekerül a hivatkozott channel kimenete az adott taskra output tag-be
- Errorok bekerülnek az adott solution-be vagy taskba error attribútumba/output tag-be

## Javítási mechanizmus leírása:
Az AKÉP mielőtt nekiállna a kapott feladat javításához lefuttatja hozzá az összes csatornán meghatározott előfeldolgozókat. Az előfeldolgozók által nyert kimenetet elmenti, majd megkezdi a javítást. 

**Csatorna**: egy nevével azonosított csomagba foglalja a futtatandó program útvonalát (előfeldolgozót/preprocesszort) az annak átadott argumentumokat, a CLI-re adott inputokat valamint a futtatás időpontját, mely a következő lehet:
-	`pre`: A fő előfeldolgozó előtt futtatja.
-	`post`: A fő elődolgozó után futtatja.
-	`con`: A fő elődolgozóval párhuzamosan futtatja.
-	`main`: A fő dolgozó.

Pl:
```xml
<script entry="pre" name="Source" scriptPath="$workdir$/getSomething.py" arguments="-E $sol$">
	<inputstream>Opcionális üzenet a csatorna STDIN-jére: 1. sor</inputstream>
	<inputstream>2. sor</inputstream>
</script>
```

A `scriptPath`-ban meghatározott útvonalon lévő programot elindítja, majd argumentumként utána helyezi a `$sol$`-t, amit helyettesít a keretrendszer a parancsban kapott útvonallal. Mindezt még az előtt (`entry=”pre”`) lefuttatja mielőtt az `<exercise>`-ban meghatározott fő előfeldolgozót végrehajtaná. A kapott kimenetet ezek után egy tesztnél a `name`-ben meghatározott név alapján lehet elérni (lentebb található példa). 

A következő példatöredék írja le a fő dolgozót:
```xml
<exercise n="2" ... >
	<script entry="main" name="Main" scriptPath="$workdir$/mainPreprocessorForLab2.py" arguments="-E $sol$">
		<inputstream>Opcionális üzenet a csatorna STDIN-jére: 1. sor</inputstream>
		<inputstream>2. sor</inputstream>
	</script>
	<!-- ... -->
</exercise>
```

Több a `$sol$`-hoz hasonló joker helyezhető el a feladatleíróban. Ezek a konfigurációs hierarchiából keresődnek ki.

### Konfigurációs hierarchia
A következő: akep.cfg > akep.local.cfg > adott exercise.xml-ben definiált `exerciseKeys`-ben ```xml <Key key="key">value</Key>``` formában > az akép sosketServernek adott JSON objektumban szintén key:value formában.
A hierarhia jobbról balra haladva csökken. Ha egy key-hez nincs value, akkor exeption dobódik, a végrehajtás befejeződik.
Azon value-mely @-al kezdődik a python eval függvénnyel értékelődik ki és ennek eredménye kerül az adott key joker helyére.

A már szöveges formában lévő eredmény javításához számos javítási algoritmus érhető el. Ezek az evaluateMode.py-ban találhatóak meg és bővíthetőek. Az itt meghatározott, javításnál felhasználható függvények mindegyike három paraméterrel rendelkezik:
-	`input`: Az előfeldolgozóból megkapott eredmény az adott feladathoz.
-	`param`: Az adott tesztnél meghatározott adott javítási algoritmusnak megfelelő szintaxissal leírt javítási bemenet.
-	`args`: Egyéb átadható paraméterlista (dictionary formátum) (pl: `fromLog:true`, stb.)

Az adott teszthez pl. a következőképp határozható meg a futtatandó javító függvényt:
```xml
<task n="2.2" >
<solution evaluateMode="regexpToInput" score="1" channelName="Source" >
<![CDATA[
param
]]>
</solution>
</task>
```

Ez a példa a 2.2 jelölésű feladatblokkban lévő Source csatorna kimenetét küldi el a `regexpToInput` függvénynek. A kimenet lesz a `evaluateMode`-al meghatározott függvény input paramétere és a `<solution>` tagek között meghatározott tartalom pedig a param paramétere.

A teszteknél lehetőség van csatornát választani. A `channelName` egy mutató arra a csatornára, amit exercise/script-ban határoztunk meg. Ennek meghatározása kötelező, amennyiben ezt nem tesszük meg az adott solution csoportként kezelődik

## Értékelési kifejezések leírása az AKÉP formális nyelvében:
TODO
