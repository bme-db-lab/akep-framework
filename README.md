# AKÉP

## Rövid leírás:
AKÉP=Automatikus kiértékelő és pontozó rendszer.

Az AKÉP egy olyan nyílt forráskódú pythonban készült támogató keretrendszer, mely segíti a javítókat abban, hogy a hallgatók munkáját önműködően javítja és értékeli. A javítók lényegében a saját javítási mechanizmusukat ültethetik át könnyen egy technológia független\* környezetbe, tetszőleges értékelési eljárásokkal. Az AKÉP akár egy beadó rendszer mögé is helyezhető és minden egyes feladatbeadás után értékelheti és továbbíthatja az eredményeket, kapcsolatot teremtve a környezetével. A részletek lentebb olvashatóak.

### A technológia független környezet:
Az AKÉP keretrendszere már csak szöveg alapú környezetben dolgozik, így a különböző forrásokból (pl. Java program, egy egyedi script, stb.) származó eredmény előállításáért úgynevezett előfeldolgozók \(preprocesszorok\) felelősek. Az AKÉP ezeket futtatva, vezérelve érheti el az adott technológiában készült feladatsorok kimenetét \(a kimenetben elválasztva a feladatokat\). Az előfeldolgozók segítségével a javítási és értékelési logika leírása technológia független tud maradni.

## Futtatás:

```shell
python3 MainSystem.py -p PORT -E EXERCISE_XML_PATH [-L MAX_OUT_SIZE -a]
```

**PORT**: Ezen a porton hallgatózik. \(int, req, def=5555\)

**EXERCISE_XML_PATH**: A feladatleírókat tartalmazó könyvtár relatív útvonala. \(str, req, def=’.’\)

**MAX_OUT_SIZE**: Az adott teszt kimenetének vágása a megadott hosszra \(int, def=2000\)

**-a kapcsoló**: Összes interfészen hallgatózik. \(def: false\)

### Egyéb konfigurációs paraméterek:
**workQueue**: Feldolgozási sor maximális hossza.

**threadNumber**: Munkaszálak maximális száma.

**userNumber**: Más rendszerbe beléptethető felhasználók maximális száma.

### Futtatás menete:
1.	Elindítás a fent megadott módon. Indulásnál kérni fog egy mesterjelszót (más rendszerek, pl. adatbázishoz) és felhasználó előtagot (melyet más rendszerekbe való belépéseknél kiegészít egy számmal is, ami maximum a userNumber-1-et éri el).
2.	Az AKÉP a meghatározott porton és interfészen várja a parancsokat (lejjebb található)
3.	Párhuzamosan hajtja végre a kapott parancsokat, az eredményt pedig a parancsot adó socketen küldi vissza.

## Parancsok (socket csatlakozása után):
-	Feladat beadása:
	`<feladatlap azonosító>,<labor azonosító>,<vizsgálandó hallgató azonosítója>[,<hallgató forráskódjának elérhetősége>]`
-	Socket lezárása: `exit`
-	Feladatleírók újra töltése: `reload`

## Feladatleírók (feladatsorok/feladatlapok) felépítése:
TODO XSD

**Megjegyzés**: Az opcionális paraméterek (pl. tasktext, description) belekerülnek a feladatstruktúrának megfelelően a kimenetbe is, így azok felhasználhatók egy a javítóknak szánt áttekintő felületen megjelenített tartalomba az értékelés eredménye és mechanizmusa mellett. Javasolt itt leírni a feladatokat és emberi megfogalmazásban a javítási mechanizmust is, hogy az tetszőleges feladatlap generálására is felhasználható legyen (javítónak, hallgatónak, stb.).

## Kimenet felépítése:
Példa XML: TODO

## Javítási mechanizmus leírása:
Az AKÉP mielőtt nekiállna a kapott feladat javításához lefuttatja hozzá az összes csatornán meghatározott előfeldolgozókat. Az előfeldolgozók által nyert kimenetet elmenti, majd megkezdi a javítást. 

**Csatorna**: egy nevével azonosított csomagba foglalja a futtatandó program útvonalát (előfeldolgozót/preprocesszort) az annak átadott argumentumokat, a CLI-re adott inputokat valamint a futtatás időpontját, mely a következő lehet:
-	`pre`: A fő előfeldolgozó előtt futtatja.
-	`post`: A fő elődolgozó után futtatja.
-	`con`: A fő elődolgozóval párhuzamosan futtatja.
-	`main`: A fő elődolgozó. Csak egy definiálható, és a neve mindig Main (a channelName argumentum lététől és értékétől függetlenül).
	- Megadható közvetlenül az `<exercise>` TAG argumentumaként is, de ez a megadási mód deprecated.

Pl:
```xml
<script entry="pre" channelName="Source" scriptPath="$workdir/getSomething.py" arguments="-E=$sol">
	<inputstream>Opcionális üzenet a csatorna STDIN-jére: 1. sor</inputstream>
	<inputstream>2. sor</inputstream>
</script>
```

A `scriptPath`-ban meghatározott útvonalon lévő programot elindítja, majd argumentumként utána helyezi a `$sol`-t, amit helyettesít a keretrendszer a parancsban kapott útvonallal. Mindezt még az előtt (`entry=”pre”`) lefuttatja mielőtt az `<exercise>`-ban meghatározott fő előfeldolgozót végrehajtaná. A kapott kimenetet ezek után egy tesztnél a `channelName`-ben meghatározott név alapján lehet elérni (lentebb található példa). Az itt nem szereplő `channelFormat` meghatározza, hogy a kimenetnek milyen formai tulajdonságoknak kell megfelelnie (pl. xml), ha ennek nem felel meg, a végrehajtás már itt megszakad.

A következő két példatöredék ekvivalensen írja le a fő előfeldolgozót (Main csatornát):
```xml
<exercise n="2" ... >
	<script entry="main" channelName="Main" scriptPath="$workdir/mainPreprocessorForLab2.py" arguments="-E=$sol">
		<inputstream>Opcionális üzenet a csatorna STDIN-jére: 1. sor</inputstream>
		<inputstream>2. sor</inputstream>
	</script>
	<!-- ... -->
</exercise>

<!-- ez a változat deprecated -->
<exercise n="2" scriptPath="$workdir/mainPreprocessorForLab2.py" arguments="-E=$sol">
	<inputstream>Opcionális üzenet a csatorna STDIN-jére: 1. sor</inputstream>
	<inputstream>2. sor</inputstream>
	<!-- ... -->
</exercise>
```

Több a `$sol`-hoz hasonló joker helyezhető el a feladatleíróban:
-	`$passw`: Az AKÉP futtatásnál megadott mesterjelszó.
-	`$workdir`: Az AKÉP futtatásnál megadott feladatleírókat tartalmazó munkakönyvtár.
-	`$sol`: A socketen kapott parancsban megadott elérési útvonal.
-	`$eid`: Feladatsor azonosító.

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

Ez a példa a 2.2 jelölésű feladatblokkban lévő kimenetet küldi el a `regexpToInput` függvénynek. A kimenet lesz a függvény input paramétere és a `<solution>` tagek között meghatározott tartalom pedig a param paramétere.

A teszteknél lehetőség van csatornát választani. A `channelName` egy mutató arra a csatornára, amit exercise/script-ban határoztunk meg. Amennyiben ezt nem határozzuk meg, úgy az adott teszt az exercise-ban meghatározott konfigurációjú fő előfeldolgozó kimenetét nézi.
