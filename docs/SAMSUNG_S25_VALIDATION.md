# VisionAssist — verificare fizică Samsung Galaxy S25

Milestone 5.7. Acest document este un protocol, nu dovada unor teste fizice trecute.
Stare inițială pentru fiecare verificare de mai jos: **NEEXECUTAT PE TELEFON**.

## Pregătire și înregistrare

1. Folosește telefonul staționar, într-un spațiu controlat. Nu testa deplasarea în trafic.
2. Deschide proiectul `C:\Users\Moth\Desktop\VisionAssist` în Android Studio,
   selectează explicit Galaxy S25 din lista de dispozitive și instalează buildul debug.
   Alternativ, după build, folosește ADB cu serialul actual din `adb devices -l`:

   ```powershell
   $adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
   & $adb devices -l
   $phone = 'ÎNLOCUIEȘTE_CU_SERIALUL_S25'
   & $adb -s $phone install -r 'D:\CodexTemp\VisionAssist-57\repo\app\build\outputs\apk\debug\app-debug.apk'
   ```

   Instalarea cu `-r` păstrează preferințele. Nu șterge datele aplicației pentru a testa
   onboardingul pe instalarea cu configurația ta privată; folosește o instalare de test
   separată sau consemnează că onboardingul fizic nu a fost verificat.
3. Notează commitul, versiunea Android/One UI, data, bateria inițială, motorul TTS,
   vocea română, căștile/Bluetooth și iluminarea. Nu înregistra chei sau coduri private.
4. Pentru fiecare ID notează PASS, FAIL, BLOCAT sau NEEXECUTAT, pașii, rezultatul real
   și eventuale capturi ale interfeței fără secrete. Un test omis nu este PASS.

## A — TalkBack și text mărit

| ID | Acțiuni exacte | Rezultat așteptat |
| --- | --- | --- |
| A1 | Activează TalkBack din setările de accesibilitate. În VisionAssist parcurge prin glisări Asistență, Asistent AI și Setări. Activează comenzile prin dublă atingere. | Comenzile principale preced conținutul și navigarea; noul ecran are titlu; selecțiile, butoanele și comutatoarele sunt inteligibile. Nu există focalizare pe ecranul ascuns. |
| A2 | Din Setări schimbă aspectul și tema, apoi redeschide aplicația. | Alegerea persistă; etichetele și starea selectată sunt citite; nu pornesc camera sau microfonul prin schimbarea setării. |
| A3 | Setează dimensiunea fontului la maximul disponibil și mărește afișarea din setările telefonului. Repetă toate cele trei ecrane și dialogul serverului. | Niciun text esențial sau buton nu este tăiat; conținutul poate fi derulat; Start/Stop și navigarea rămân accesibile. Consemnează scala reală: maximul telefonului nu este automat 200%. |
| A4 | Cu camera pornită, explorează lista obiectelor. Apoi oprește camera. | Lista poate fi citită fără anunțuri TalkBack pe fiecare cadru; rezultatele vechi dispar. Absența detecțiilor nu este prezentată drept traseu sigur. |
| A5 | Pe o instalare de test nouă, alege fiecare aspect la prima lansare și verifică persistența după relansare. | Onboardingul nu solicită camera/microfonul și poate fi completat cu TalkBack. |

## B — Romanian offline TTS și prioritate

| ID | Acțiuni exacte | Rezultat așteptat |
| --- | --- | --- |
| B1 | În setările Android de sinteză vocală instalează o voce română offline. În VisionAssist activează anunțurile și apasă „Testează vocea locală și prioritatea audio”. Repetă fără internet. | Voce română inteligibilă; testul este identificat ca test, nu avertizare. Fără voce offline instalată apare explicația, nu succes inventat. |
| B2 | Cu backendul configurat, pornește conversația și declanșează testul local în timpul răspunsului AI; schimbă ecranul. | AI este întrerupt înaintea TTS și nu se aude peste anunț. Gemini cere repornire explicită; OpenAI reia doar după eliberarea priorității și confirmarea golirii audio, sau se oprește explicit. |
| B3 | În timpul anunțului încearcă Stop, apoi Start. | Stop rămâne utilizabil; Start rămâne blocat cât timp anunțul deține prioritatea. |

Un microfon WebRTC poate rămâne deschis nativ în timp ce transmisia este blocată.
Diagnosticul distinge aceste stări. Indicatorul Android trebuie verificat separat;
după Stop/fundal captura trebuie închisă. Audibilitatea nu dovedește singură absența
transmisiei: testele automate verifică suplimentar limita de consimțământ pentru imagini.

## C — Bluetooth și lifecycle audio

1. Conectează căștile și notează modelul/ruta selectată. Pornește conversația și verifică
   atât ascultarea în română, cât și redarea. Repetă B2.
2. Deconectează/reconectează căștile în timpul conversației. Notează dacă sesiunea se
   închide sau ruta se schimbă; nu trebuie să rămână redare ori captură necontrolată.
3. Apasă Stop și treci aplicația în fundal. Verifică indicatorul de microfon Android.
4. Repetă folosind difuzorul. Notează ecoul, întârzierea și inteligibilitatea; nu estima
   o latență numerică doar după auz. Audio focus poate închide conversația cu mesaj.

## D — Camera, rotație, erori și fundal

1. Permite camera, pornește-o și îndreapt-o spre obiecte staționare bine iluminate.
   Confirmă rezultate reale; nu folosi rezultatele pentru a decide deplasarea.
2. Rotește 0/90/180/270°, schimbă ecranele și verifică alinierea chenarelor.
3. Trimite aplicația în fundal, blochează/deblochează ecranul și revino. Verifică eliberarea
   resurselor în fundal și reluarea camerei dacă fusese cerută. Conversația nu repornește singură.
4. Apasă „Oprește camera”, rotește și revino din fundal: camera rămâne oprită.
5. Refuză permisiunea camerei pe o instalare de test și verifică explicația și accesul
   la setările aplicației. Nu revoca accidental configurația instalării personale.
6. În Setări activează Developer Mode: notează FPS, mediană/p95 și numărul eșantioanelor,
   vârsta rezultatului, heap Java și PSS proces. Repetă în ambele aspecte și pe cele trei ecrane.
   Oprește analiza: nu trebuie păstrate valori vechi ca și cum ar fi măsurători curente.

Nu porni benchmarkuri lungi. Diagnosticul este în memorie, fără export automat și fără
înregistrarea audio/imaginilor. FPS este rata rezultatelor, nu FPS senzor; p95 folosește
nearest-rank pe maximum 60 de apeluri MediaPipe din sesiunea recentă. Heap Java nu este
PSS/RSS și exclude o parte importantă a memoriei native. PSS proces este eșantionat
separat, pe un worker, o dată la 5 secunde; include runtime și biblioteci native și
nu este memoria izolată a modelului. Eșantionarea se oprește în fundal.

## E — Rețea și fotografie întreruptă

1. Cu backendul configurat pornește o conversație. Întrerupe Wi-Fi/datele și verifică
   eroarea/reîncercările limitate, în timp ce recunoașterea locală continuă.
2. Restabilește rețeaua și repornește explicit dacă este necesar. Schimbă furnizorul
   numai după Stop. Nu presupune disponibilitatea cotei sau credențialelor cloud.
3. Cere descrierea scenei și refuză fotografia. Repetă anulând în pregătire, oprind camera,
   oprind conversația și trecând în fundal. Aprobă apoi o fotografie nouă.
4. Capturile anulate înainte de trimitere nu trebuie expediate ulterior sau asociate altei
   cereri. Captura poate fi prea rapidă pentru a reproduce manual cursa; notează această
   limită și păstrează testul automat ca probă. O imagine deja transmisă nu poate fi retrasă.

## F — Referințe ARCore Depth, exclusiv staționar

1. Folosește o suprafață plană, texturată, bine iluminată, aproximativ perpendiculară
   pe camera din spate. Măsoară fizic camera–suprafață; nu ghici valoarea.
2. Din Setări → „Gropi · model experimental” → „Deschide experimentul de adâncime”.
   Camera obișnuită și conversația trebuie să se oprească.
3. Cu telefonul stabil, notează referința reală și citirea centrală. Dacă ARCore cere
   inițializare, fă doar o mișcare mică și revino la poziția măsurată.
4. Repetă cel puțin trei citiri la fiecare dintre trei distanțe măsurate din intervalul
   0,5–8 m, de exemplu aproximativ 1/2/3 m, în limita spațiului disponibil.
5. Calculează eroarea absolută și relativă pe fiecare citire; consemnează și absențele.
   Pragul testului existent max(0,15 m, 15%) este doar criteriu grosier al prototipului,
   nu o certificare de precizie. Unsupported/timeout/lipsa citirii nu reprezintă PASS.
6. Revino în aplicație și verifică posibilitatea repornirii camerei obișnuite.

| Referință măsurată (m) | Citire 1 | Citire 2 | Citire 3 | Erori / citiri lipsă | Rezultat |
| --- | --- | --- | --- | --- | --- |
| De completat | — | — | — | — | NEEXECUTAT |

Depth este distanță axială până la suprafață, nu distanță de mers sau adâncime a gropii.
Modelul experimental și avertizările rămân dezactivate, inclusiv în Developer Mode.

## Foaie de rezultat

Pentru fiecare A1–A5, B1–B3, C, D, E, F: commit / telefon / dată / configurație /
PASS-FAIL-BLOCAT-NEEXECUTAT / observații. Atașează doar dovezi fără credențiale.
Nu transforma rezultatele emulatorului în rezultate fizice și nu numi prototipul
înlocuitor al bastonului alb.
