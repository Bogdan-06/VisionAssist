# Antrenare locală VisionAssist, fără Codex

Rulezi comenzile în **Windows PowerShell**. După configurare nu este nevoie de
Codex, de un LLM, de chei API sau de servicii AI plătite pentru aceste operații.
Calculatorul trebuie să rămână pornit; păstrează fereastra de lucru deschisă.

```powershell
Set-Location 'C:\Users\Moth\Desktop\VisionAssist'
```

## 1. Verifică mediul înainte de antrenare

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-VisionAssist.ps1 -Task barrier -Action check -Device Gpu
powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-VisionAssist.ps1 -Task pothole -Action check -Device Gpu
```

`Gpu` folosește WSL2 `Ubuntu-24.04` și placa NVIDIA GTX 1650 Ti de 4 GB.
Nu revine silențios la CPU dacă GPU nu funcționează. `Cpu` folosește mediile Windows.
Verificarea gropilor recitește și calculează hashurile multor fișiere NPZ; pe discul
Windows accesat prin WSL poate dura câteva minute. Progresul apare în terminal.
Nu înseamnă că a început antrenarea.

O probă completă a lansatorului, limitată intenționat la 16 imagini de antrenare,
16 de validare și o singură epocă, este disponibilă pentru bariere:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-VisionAssist.ps1 -Task barrier -Action train -Device Gpu -Smoke -OutputDirectory 'D:\VisionAssistSmoke'
```

Proba păstrează separarea datelor și evaluează numai 4 imagini de validare.
Este un test al automatizării, nu dovadă de acuratețe. `Smoke` este permis doar
pentru un experiment nou de bariere și nu poate relua o antrenare completă.

Pe acest calculator mediile și datele sunt deja pregătite. Implicit:

- Date: `C:\Users\Moth\Documents\Codex\2026-10-09\new-chat\work\ground`.
- Bariere GPU: `/opt/visionassist/modelmaker-venv/bin/python`, TensorFlow 2.15.
- Gropi GPU: `/opt/visionassist/venv/bin/python`, TensorFlow 2.20 / Keras 3.
- Evaluator bariere GPU/WSL: `/opt/visionassist/barrier-runtime-venv/bin/python`.
- CPU Windows: subfolderele `modelmaker-venv`, respectiv `venv`, din folderul de date.
- Evaluator Windows: `barrier-runtime-venv\Scripts\python.exe`, MediaPipe 0.10.32.

Nu combina aceste medii: versiunile necesare celor două arhitecturi diferă.
Pe un calculator nou pregătește întâi datele conform `tools/ground/README.md`,
`docs/BARRIER_TRAINING.md` și `tools/ground/MODELMAKER_WINDOWS.md`. Instalarea GPU
pentru gropi se face explicit prin `Setup-GpuTraining.ps1`. Pentru bariere:

```powershell
wsl -d Ubuntu-24.04 -u root --exec bash /mnt/c/Users/Moth/Desktop/VisionAssist/tools/ground/setup_modelmaker_wsl.sh
```

Scripturile `check`, `train` și `evaluate` nu instalează automat dependențe și nu
descarcă automat dataseturi. Repară eroarea afișată și repetă comanda deliberat;
nu există bucle automate de reîncercare.

## 2. Pornește un experiment nou

Execută una dintre comenzi, în funcție de model. Nu le lansa simultan.

```powershell
# Scări, borduri, trepte: profilul existent MobileNetV2 SSD320/FPN
powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-VisionAssist.ps1 -Task barrier -Action train -Device Gpu -Epochs 20 -BatchSize 8 -Threads 8 -OutputDirectory 'D:\VisionAssistExperiments'

# Gropi: encoder MobileNetV2 înghețat și decoder de segmentare
powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-VisionAssist.ps1 -Task pothole -Action train -Device Gpu -Epochs 12 -BatchSize 16 -CacheBatchSize 32 -Threads 8 -OutputDirectory 'D:\VisionAssistExperiments'
```

Aceste comenzi sunt pentru viitoarele tale antrenări; implementarea automatizării
nu necesită pornirea lor pe datasetul complet. Pentru 4 GB, batch 8 este punctul
de pornire conservator la bariere. Nu există promisiunea că orice batch încape.
Dacă apare CUDA out-of-memory, păstrează experimentul eșuat și pornește unul
**nou** cu batch mai mic. Nu schimba batchul pentru o reluare a aceluiași program.

Parametri opționali: `-DataRoot`, `-Python`, `-EvaluationPython`, `-Backbone`,
`-WslDistro`, `-CacheBatchSize`. Căile pentru Python/evaluator în modul GPU sunt
căi Linux; căile pentru date, ieșire, run și checkpoint sunt căi Windows.
Fără `-OutputDirectory`, rezultatele merg în `visionassist-experiments` din proiect,
folder exclus din Git. Pentru a economisi C:, folosește explicit D:.

## 3. Vezi progresul și rezultatele

Terminalul afișează etapele, epocile și locația `EXPERIMENT`. În altă fereastră:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-VisionAssist.ps1 -Task barrier -Action status -Device Gpu -OutputDirectory 'D:\VisionAssistExperiments'
```

Pentru o singură rulare, adaugă `-RunDirectory 'D:\VisionAssistExperiments\NUMELE_RUNULUI'`.
Folosește același `-Device` ca la pornire pentru verificarea procesului în sistemul
corect. Un fișier care spune `running` fără procesul original este raportat ca
neconfirmat/stale; nu dovedește că antrenarea mai rulează. `history.csv` arată
ultima epocă completă; în checkpointuri, `committed.json` confirmă salvarea completă.

În fiecare experiment:

- `experiment.json`, `preflight.json`, `commands.json`: configurație, date, mediu,
  timpi și comenzile efective; `source/`: copii ale codului folosit.
- `status.json` și `logs/*.log`: stare, erori, etape terminate, ieșire completă.
- `training/history.csv`: pierderile de antrenare și validare pe epoci.
- `training/checkpoints/epoch-*/`: checkpointuri complete, imuabile, pe epoci.
- Bariere: `training/best.weights.h5`, `last.weights.h5`, `model.tflite`.
- Gropi: `training/decoder.weights.h5` (best), checkpoint complet `last.keras`
  în fiecare epocă, `segmentation.weights.h5` și `segmentation.tflite` finale.
- Evaluări JSON și predicții JSONL în directoare separate; `report.md` la final.

Modelul best este ales folosind **pierderea de validare**, înainte de test.
Testul ținut separat nu intră în antrenare sau selecție. Seturile istorice au fost
deja examinate în cercetare, deci nu reprezintă o evaluare de siguranță neatinsă.
La gropi, oprirea anticipată poate încheia legitim antrenarea înainte de `Epochs`.

## 4. Oprește și reia în siguranță

Apasă **Ctrl+C** în fereastra de lucru și așteaptă oprirea. Închiderea brutală a
ferestrei poate lăsa un proces WSL activ; verifică `status`, nu șterge lockuri și
nu porni încă un job peste el. Lansatorul verifică și procesele vechi cunoscute.
Scripturile vechi PowerShell folosesc aceeași blocare ca lansatorul nou.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-VisionAssist.ps1 -Task barrier -Action resume -Device Gpu -Epochs 20 -BatchSize 8 -RunDirectory 'D:\VisionAssistExperiments\NUMELE_RUNULUI_INTRERUPT' -OutputDirectory 'D:\VisionAssistExperiments'

powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-VisionAssist.ps1 -Task pothole -Action resume -Device Gpu -Epochs 12 -BatchSize 16 -RunDirectory 'D:\VisionAssistExperiments\NUMELE_RUNULUI_INTRERUPT' -OutputDirectory 'D:\VisionAssistExperiments'
```

Păstrează numărul **total** inițial de epoci, batchul, dispozitivul și aceleași date
și versiuni. `Epochs` nu înseamnă epoci suplimentare. Reluarea creează alt folder,
fără a modifica sursa. Se reia ultima epocă salvată complet, cu optimizatorul,
separat de modelul best; la gropi se restaurează și starea callbackurilor.
Ordinea shuffle și calculele GPU nu sunt garantate identice bit cu bit după restart.
Nu se reia un run deja terminat sau oprit legitim prin EarlyStopping.
Vechile modele de gropi care au doar greutăți best nu au starea necesară reluării
și sunt refuzate explicit; pot fi evaluate sau folosite ca dovezi istorice.

## 5. Evaluează un model existent fără antrenare

Evaluare completă Windows, runtime-ul de referință pentru bariere:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-VisionAssist.ps1 -Task barrier -Action evaluate -Device Cpu -Checkpoint '.\barrier-training-runs\20261028-215718-4bd1910e\training\model.tflite' -Split all -OutputDirectory 'D:\VisionAssistExperiments'
```

Probă scurtă, numai 4 imagini de validare:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-VisionAssist.ps1 -Task barrier -Action evaluate -Device Cpu -Checkpoint '.\barrier-training-runs\20261028-215718-4bd1910e\training\model.tflite' -Split validation -MaxImages 4 -OutputDirectory 'D:\VisionAssistExperiments'
```

`-Checkpoint` acceptă și checkpointuri de greutăți compatibile: `best.weights.h5`
sau `last.weights.h5` pentru bariere, `decoder.weights.h5`,
`segmentation.weights.h5` sau decoder complet `.keras` pentru gropi. Sunt exportate
într-un director nou înainte de evaluare, fără antrenare și fără modificarea sursei.
Pentru bariere sunt necesare metadatele runului lângă greutăți.

Exemplu gropi cu modelul de cercetare existent:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-VisionAssist.ps1 -Task pothole -Action evaluate -Device Cpu -Checkpoint 'C:\Users\Moth\Documents\Codex\2026-10-09\new-chat\work\ground\segmentation-run-v2\segmentation.tflite' -Split test -MaxImages 2 -OutputDirectory 'D:\VisionAssistExperiments'
```

La gropi `test/all` rulează evaluatoarele existente RDD, video și UK; validarea este
salvată în timpul antrenării. `MaxImages` limitează imagini în RDD/UK și **clipuri**
în video (fiecare conține mai multe cadre). Fără limită, evaluarea este completă.
Evaluările limitate au `partial=true`, nu sunt rezultate de calitate complete.
Toată inferența de evaluare este CPU, chiar când antrenorul ales este WSL/GPU.
MediaPipe Linux a avut diferențe numerice față de Windows; raportul păstrează
identitatea platformei/runtime-ului. Pentru comparația cu telefonul, folosește
evaluatorul Windows 0.10.32 și protocolul existent de compatibilitate Android.

## 6. Compară experimentele

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Train-VisionAssist.ps1 -Task barrier -Action report -Device Cpu -OutputDirectory 'D:\VisionAssistExperiments' -ReportFile 'D:\VisionAssistExperiments\comparatie-01.md'
Invoke-Item 'D:\VisionAssistExperiments\comparatie-01.md'
```

Alege un nume nou dacă raportul există deja. Raportul păstrează TP, FP, FN,
precision, recall și F1 pe clase/praguri, plus identitatea datelor și modelelor.
Nu compara metrici de pixeli cu metrici de obiecte sau rezultate parțiale cu
evaluări complete. Valorile nedefinite sunt N/A, fără scoruri inventate.
Rapoartele JSON originale și limitările lor sunt dovezile complete.

Antrenarea/exportul/evaluarea **nu instalează modelul în Android**, nu activează
detecția experimentală sau avertizările și nu validează siguranța navigării.
Modelele, dataseturile, checkpointurile și cheile existente rămân la locul lor.
