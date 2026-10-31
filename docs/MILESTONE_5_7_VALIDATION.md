# Milestone 5.7 — accesibilitate, lifecycle și diagnostic măsurat

Proiect: `C:\Users\Moth\Desktop\VisionAssist`. Bază: commit `59f201d`.
Implementarea și verificările automate sunt finalizate. **Testele fizice pe Galaxy S25
nu au fost executate pentru acest milestone.** Protocolul telefonului este separat:
[SAMSUNG_S25_VALIDATION.md](SAMSUNG_S25_VALIDATION.md).

## Ce s-a implementat

- Cele trei ecrane au grupuri explicite de parcurgere TalkBack: comenzi principale,
  conținutul ecranului, navigare. Conținutul expune titlul destinației; titlul aplicației
  este heading. Previzualizarea ascunsă rămâne exclusă din accesibilitate.
- La text 200%, limita fixă de 96 dp rupea „Asistență” înaintea ultimei litere.
  Etichetele folosesc acum lățimea disponibilă a fiecărei destinații. Testele verifică
  textul complet fără overflow și păstrează verificarea că etichetele nu se suprapun.
- Diagnosticul este vizibil pe toate cele trei ecrane numai în Developer Mode. Agregarea
  statisticilor este opt-in; dezactivarea o golește fără a opri recunoașterea obiectelor.
  Eșantionarea memoriei este oprită în fundal și dispare la ieșirea din modul dezvoltator.
- FPS este calculat din timestampurile rezultatelor: maximum ultimele 20 rezultate din
  două secunde. Nu este FPS al senzorului. Lipsa a două rezultate lasă valoarea necunoscută.
- Mediana și p95 folosesc maximum 60 durate reale, p95 nearest-rank și numărul vizibil de
  eșantioane. Se resping durate negative și timestampuri duplicate/retrograde; un gol de
  o secundă resetează fereastra. Oprirea, eroarea și expirarea curăță măsurătorile vechi.
- CameraX temporizează acum strict apelul `MediaPipe.detect`, fără conversia/rotația cadrului
  sau JPEG. Apelul include pre/postprocesarea internă MediaPipe, nu doar operatorii LiteRT.
  Duratele istorice care includeau întregul analyzer nu sunt direct comparabile.
- Vârsta rezultatului folosește ceasul monoton de la primirea în analyzer. Nu este o
  estimare a momentului expunerii senzorului și nu include o latență de captură necunoscută.
- Memoria afișată este heap Java utilizat, eșantionat aproximativ la o secundă, și PSS
  al procesului, citit pe worker aproximativ la cinci secunde. Heap nu include toată memoria
  nativă; PSS include runtime/biblioteci și nu este memoria izolată a modelului.
- Sunt vizibile stările camerei, analizei, aplicației și sesiunii vocale. OpenAI raportează
  pornirea/oprirea capturii din callbackurile native WebRTC, protejate de generația sesiunii.
  Gemini citește starea nativă AudioRecord. Captura nativă și permisiunea de a transmite
  audio sunt afișate separat: mutingul nu înseamnă neapărat închiderea microfonului fizic.
- Diagnosticele nu emit live-region pe fiecare cadru, nu păstrează imagini/audio și nu au
  export automat sau telemetrie de rețea. Valorile indisponibile nu sunt înlocuite cu zero.

## Teste automate — rezultate finale

Toate comenzile Android au vizat explicit **emulator-5580, API36**, fără sesiune cloud.
Testul de microfon nativ a folosit numai emulatorul; nu s-a instalat sau pornit aplicația
pe telefonul personal. Unele rezultate JVM sunt reutilizate de Gradle pentru surse neschimbate.

| Verificare | Trecute | Omise intenționat | Eșecuri finale |
| --- | ---: | ---: | ---: |
| JVM | 34 | 0 | 0 |
| Android app | 30 | 2 | 0 |
| Android camera | 10 | 0 | 0 |
| Android detection | 4 | 0 | 0 |
| Android voice | 5 | 0 | 0 |
| Android ground | 5 | 1 | 0 |
| Total Android | **54** | **3** | **0** |
| Node backend | 9 | 0 | 0 |

Cele trei omise sunt conversația cloud live, măsurarea fizică Depth și benchmarkul ground
susținut. Nu sunt numărate ca trecute. Lint: **zero erori/fatal, 26 avertismente**.
Debug și release optimizat s-au construit cu succes; release rămâne **nesemnat**.

Acoperirea adăugată:

- cuantile/FPS, fereastră limitată, resetare și intrări invalide;
- măsurători pe rezultate CameraX/COCO reale și golire la Stop;
- opt-in/resetare în ViewModel, memorie reală a procesului fără inventarea inferenței;
- trei destinații la text 200%, roluri/grupuri/titluri și etichetă fără trunchiere;
- erori cameră/analiză cu Retry și eșec la salvarea onboardingului cu alegerea păstrată;
- conversație întreruptă: recuperare vizibilă, fotografie blocată și fără repornire automată;
- AudioRecord/AudioTrack reale pe emulator: pornire, input, întrerupere, close idempotent,
  respingerea audio după close și repornire fără callbackuri input rămase din sesiunea veche.

Testele existente de onboarding/DataStore, cameră/fundal/recreare, expirare, criptare,
prioritate audio, consimțământ foto și modele au fost păstrate.

Prima suită app a eșuat într-un singur caz: testul de randare cerea procente fără să activeze
Developer Mode explicit, după schimbarea implicitului componentei în false. Fixture-ul
setează acum `developer=true`; verificările existente ale etichetelor, scorurilor și
direcțiilor reale au rămas intacte. Suita completă a trecut ulterior, apoi a trecut din nou
după corecția vizuală a navigării. Logul inițial este păstrat, nu ascuns.

## Măsurătoare reală disponibilă și limite

Ultima probă scurtă din testul CameraX, **numai emulator**, are patru rezultate:
FPS analiză **2,99**, mediană detect **234 ms**, p95 **402 ms**, vârstă de la analyzer
**291 ms**, heap Java **8.851.072 bytes**. Acestea sunt datele efectiv înregistrate,
nu estimări pentru S25. Patru eșantioane, inițializarea și încărcarea calculatorului nu
permit un benchmark reprezentativ sau o comparație între dispozitive. Alte rulări au
valori diferite și sunt păstrate în log. Testul memoriei verifică și PSS pozitiv real;
nu se pretinde un benchmark de consum ori memorie izolată pe model.

Cele trei ecrane au fost inspectate vizual în emulator la font_scale=2.0, fără cameră
sau conversație pornită. Scala a fost restaurată la 1.0 și aplicația a fost oprită.
Capturi finale: [Asistență](milestone57/large-text-home-final.png),
[Voce](milestone57/large-text-voice-final.png), [Setări](milestone57/large-text-settings-final.png).
Acestea nu reprezintă o sesiune TalkBack umană sau o verificare pe telefon.

## Fișiere de producție modificate

Toate căile sunt relative la rădăcina proiectului.

- `app/src/main/java/ro/visionassist/app/ui/AnalysisDiagnostics.kt` — agregare pură nouă.
- `app/src/main/java/ro/visionassist/app/ui/DeveloperDiagnostics.kt` — panou nou, sampling limitat.
- `app/src/main/java/ro/visionassist/app/ui/DetectionViewModel.kt` — opt-in și resetări.
- `app/src/main/java/ro/visionassist/app/ui/DetectionPanel.kt` — diagnostic implicit dezactivat,
  eliminarea FPS duplicat; scorurile rămân disponibile în Developer Mode.
- `app/src/main/java/ro/visionassist/app/ui/VisionAssistScreen.kt` — semantică, titluri,
  lățimea etichetelor și găzduirea diagnosticului.
- `app/src/main/java/ro/visionassist/app/ui/VisionAssistRoute.kt` — conectarea diagnosticului.
- `core/camera/src/main/java/ro/visionassist/core/camera/DetectionAnalyzer.kt` — temporizare detector.
- `core/detection/src/main/java/ro/visionassist/core/detection/DetectionResult.kt` — documentarea duratei.
- `core/voice/src/main/java/ro/visionassist/core/voice/VoiceState.kt` — stare captură/muting.
- `core/voice/src/main/java/ro/visionassist/core/voice/RealtimeVoiceClient.kt` — callbackuri native.
- `core/voice/src/main/java/ro/visionassist/core/voice/GeminiVoiceClient.kt` — publicarea stării native.
- `core/voice/src/main/java/ro/visionassist/core/voice/GeminiPcmAudio.kt` — citirea stării AudioRecord.

Teste: `CameraLifecycleTest.kt`, `DetectionRenderingTest.kt`, `DetectionViewModelTest.kt`,
`DeviceReadinessAccessibilityTest.kt` (nou), `VoiceControlsTest.kt` din app/androidTest;
`AnalysisWindowTest.kt` (nou) din app/test; `PcmLifecycleTest.kt` (nou) din core/voice/androidTest.
Documentație: README, acest raport, checklistul S25 și dovezile din `docs/milestone57`.

## Reproducere și dovezi

Buildurile s-au executat în copia `D:\CodexTemp\VisionAssist-57\repo`, păstrând sursele
autoritare pe Desktop și fără drive V:. JDK21 și SDK-ul existente, fără antrenare.
Hashurile surselor Kotlin/XML/Gradle din copie coincid cu sursele verificate.

```powershell
# În proiect/copia de build, cu JAVA_HOME configurat:
.\gradlew.bat :app:assembleDebug :app:assembleRelease testDebugUnitTest :app:lintDebug :app:assembleDebugAndroidTest :core:camera:assembleDebugAndroidTest :core:voice:assembleDebugAndroidTest :core:detection:assembleDebugAndroidTest :core:ground:assembleDebugAndroidTest --console=plain
# După instalarea APK-urilor pe emulatorul selectat explicit:
adb -s emulator-5580 shell am instrument -w -r ro.visionassist.app.test/androidx.test.runner.AndroidJUnitRunner
# Echivalente pentru ro.visionassist.core.{camera,detection,voice,ground}.test.
# În backend, fără .env sau apeluri cloud:
node --test
```

Dovezi: [verification.json](milestone57/verification.json), cele șapte XML-uri JVM,
`large-text-build.log` (ultimul build), `verified-build.log` (build complet anterior),
`test-fixture-build.log`, `app-tests-final-layout.log`, `{camera,detection,voice,ground}-tests.log`,
`backend-tests.log`, `lint-results-debug.xml`, `emulator-diagnostics-final-layout.log`.
`app-tests.log` este eșecul intermediar descris mai sus. Exitcode adb nu a fost tratat
singur ca dovadă: au fost numărate statusurile individuale și verificat sumarul runnerului.
JSON-ul include hashuri APK, modele și surse. APK-urile generate rămân în copia de pe D:,
fără a fi adăugate în Git. Pe un clone nou, fixture-urile ground ignorate necesită
restaurare conform `RESUME_GROUND_HAZARDS.md`; modelele runtime sunt deja urmărite intenționat.

## Siguranță și lucruri rămase de verificat fizic

- `groundEnabled=false` și `WARNINGS_VALIDATED=false` sunt păstrate. Developer Mode nu
  activează ground inference sau avertizări nevalidate. Modelul depth experimental rămâne
  separat, cu worker ground dezactivat implicit. Ponderile și pragurile nu sunt modificate.
- Hashurile COCO, ground v3 și Barrier final coincid cu baseline-ul înregistrat.
  Scripturile/dataseturile/checkpointurile nu au fost modificate; niciun training sau
  benchmark lung nu a fost pornit. Nu există detectări fictive noi în producție.
- Testele semantice nu certifică TalkBack. Trebuie verificate fizic ordinea focalizării,
  vocile românești, inteligibilitatea, Bluetooth, ecoul și indicatorul de microfon.
- Nu s-a deschis un apel cloud; disponibilitatea contului/cotei și comportamentul real
  la pierderea rețelei rămân verificări manuale. Fixture-ul UI de eroare nu este un apel live.
- Lipsesc măsurători S25 pentru FPS, latență, memorie, baterie, temperatură și depth.
  Nu există o promisiune de performanță sau de siguranță a deplasării.

## Acțiunile următoare pe telefon

Instalează buildul debug din proiectul Desktop sau APK-ul verificat din D:, selectând
explicit S25. Urmează în ordine secțiunile A–F din
[checklist](SAMSUNG_S25_VALIDATION.md): TalkBack/text mare, TTS română fără internet,
Bluetooth, cameră/rotație/fundal, rețea/fotografie anulată, apoi Depth cu distanțe măsurate.
Notează PASS/FAIL/BLOCAT/NEEXECUTAT pentru fiecare caz. Nu șterge datele instalării personale
doar pentru onboarding și nu trimite cheile în chat sau în dovezi.
