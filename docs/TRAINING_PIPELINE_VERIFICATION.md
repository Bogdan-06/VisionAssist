# Verificarea automatizării locale VisionAssist

Implementare pornită de la `6549e6f`, proiectul de pe Desktop. Probele au fost
executate la 31 octombrie / 1 noiembrie 2026. Nu s-a pornit antrenare completă.

## Dovezi funcționale

| Cerință | Implementare și dovadă |
| --- | --- |
| Lansator unic, două sarcini, șase acțiuni | `Train-VisionAssist.ps1`, `visionassist_training.py`; dispatch verificat automat pentru pothole/barrier, status/report executate efectiv. |
| Python, WSL2, CUDA, GPU, date, dependențe | Preflight real în mediile existente; NVIDIA GTX 1650 Ti Max-Q, 4096 MiB, WSL2 Ubuntu-24.04. Proba barrier a verificat inclusiv un kernel CUDA, nu doar numele plăcii. |
| Configurare | Epoci, batch, dispozitiv, threads, cache batch, date și output; teste de construire a comenzilor, inclusiv program personalizat de 7 epoci. |
| Checkpointuri și pierderi | CSVLogger, checkpointuri imuabile pe epoci, best separat de last, export final; smoke real pe GPU cu checkpoint și export. |
| Precision/recall/F1/TP/FP/FN | Evaluatoarele existente; probe limitate reale pentru barrier și toate cele trei surse pothole. Raportul păstrează pragul, clasa și unitatea metricii. |
| Progres, configurare, timpi și loguri | experiment/preflight/commands/status JSON, copii de sursă, log streaming, history.csv și raport Markdown; status observat pe un proces real activ. |
| Exclusivitate și protejarea fișierelor | Lock OS de proces plus lock comun Windows pentru toate cele trei lansatoare; teste reale de concurență, inclusiv respingerea joburilor prin lansatoarele vechi. Foldere noi și rapoarte deschise exclusiv. |
| Separarea datelor | Audit de identități, grupuri și hashuri; verificarea arrayurilor de fitting; teste negative pentru contaminare între splituri și arrayuri de test în fitting. Antrenorii își păstrează verificările existente. |
| Întrerupere și reluare | Proces copil real terminat la întrerupere; stare interrupted și propagarea eșecului, fără retry. Teste de restaurare a optimizatorului și callbackurilor Keras, refuz pentru configurații modificate, greutăți corupte, proces activ sau epoci terminate. |
| Comparație între experimente | `experiment_store.comparison`: Markdown cu metrici pe scope/prag, progres și identitatea platformei/datelor/modelului; test și comandă report reale. |
| Păstrarea aplicației și experimentelor | 71 fișiere de modele/checkpointuri verificate SHA-256 față de inventarul din 29 octombrie: zero diferențe. Nicio sursă Kotlin/Gradle și niciun asset Android modificat. |
| Fără integrare/avertizări automate | Run/export/evaluation metadata declară warning_eligible=false și installs_android_model=false. Ground gates din aplicație rămân false. |
| Folosire independentă | Ghidul românesc `TRAIN_VISIONASSIST_RO.md` include comenzile PowerShell pentru verificare, antrenare, status, reluare, evaluare și raport. Nu se citesc chei API. |

## Probe reale, fără antrenare completă

- Smoke barrier prin lansatorul unificat:
  `D:\CodexTemp\VisionAssist-training-pipeline\final-smoke-experiments\20261101-103255-barrier-2a1fd79d`.
  O epocă, 16 imagini train și 16 validation, batch efectiv 4; checkpoint complet,
  export și evaluare a 4 imagini de validare. `smoke_only=true`, `partial=true`.
  Nu este probă de acuratețe. Verificarea hashurilor citește inventarul complet,
  dar fittingul este limitat la subsetul smoke.
- Evaluare Windows a exportului barrier existent:
  `D:\CodexTemp\VisionAssist-training-pipeline\experiments\20261031-121914-barrier-0764e0a9`;
  4 imagini de validare, `partial=true`.
- Export/evaluare Windows din checkpointul barrier `best.weights.h5` existent:
  `D:\CodexTemp\VisionAssist-training-pipeline\checkpoint-evaluations\20261101-104943-barrier-a6e3d602`;
  2 imagini de validare, `partial=true`. `weight-loading.json`: încărcare strictă,
  toate cele 327 de tensori de predicție consumate, fără skip_mismatch.
- Evaluare pothole din exportul existent:
  `D:\CodexTemp\VisionAssist-training-pipeline\pothole-evaluations\20261101-104551-pothole-a93f92cc`;
  RDD 2 imagini, video 2 clipuri și UK 2 imagini; toate rapoartele sunt parțiale.
- Export/evaluare pothole din greutățile decoderului existent:
  `D:\CodexTemp\VisionAssist-training-pipeline\pothole-evaluations\20261101-105653-pothole-9d813997`;
  RDD 1 imagine, video 1 clip și UK 1 imagine, fără fitting.
- Verificarea finală `-Task pothole -Action check -Device Gpu` a trecut, inclusiv
  auditul arrayurilor și executarea unui kernel CUDA cu TensorFlow 2.20. Log:
  `D:\CodexTemp\VisionAssist-training-pipeline\final-pothole-gpu-check.log`.
- Smoke sintetic Keras 3 pe WSL/GPU: un batch minuscul, salvare completă, restaurare
  și încă un batch. S-au comparat variabilele optimizatorului și starea callbackurilor;
  nu s-a folosit niciun dataset real pentru acest test.

Au fost păstrate și încercările eșuate în directoare distincte. Testarea a descoperit
și corectat două probleme: redirectorul python.exe al unui venv Windows era confundat
cu alt job; separatoarele HDF5 Keras 2.15 diferă între Linux și Windows. Testele de
regresie acoperă ambele. Nu s-au relaxat verificările pentru a accepta greutăți lipsă.

## Teste reutilizabile

Rezultatele finale: **50 teste Python trecute**, zero eșecuri și zero omiteri
(34 în mediul de date, 15 în mediul Model Maker și 1 smoke Keras 3/WSL).
Separat: trei teste de exclusivitate între lansatoare și verificarea sintaxei
PowerShell au trecut. Logurile și JSON-urile sumare sunt păstrate local în
`D:\CodexTemp\VisionAssist-training-pipeline`.

Testele fără runtime Model Maker se execută cu Python din `work\ground\venv`, iar
testele Model Maker, comparație SciPy și HDF5 portabil cu `modelmaker-venv`.
`test_segmentation_resume.py` se execută separat în mediul TensorFlow 2.20 / Keras 3.
Amestecarea mediilor nu este un test valid al tuturor dependențelor: o primă
încercare de comparație în mediul fără SciPy a fost corectată prin alegerea mediului
Model Maker existent, fără instalări noi.

```powershell
Set-Location 'C:\Users\Moth\Desktop\VisionAssist'
$data = 'C:\Users\Moth\Documents\Codex\2026-10-09\new-chat\work\ground'
& "$data\venv\Scripts\python.exe" -B -m unittest discover -s tools/ground -p test_training_controller.py -v
& "$data\venv\Scripts\python.exe" -B -m unittest discover -s tools/ground -p test_experiment_store.py -v
& "$data\venv\Scripts\python.exe" -B -m unittest discover -s tools/ground -p test_training_process.py -v
& "$data\modelmaker-venv\Scripts\python.exe" -B -m unittest discover -s tools/ground -p test_modelmaker_resume.py -v
& "$data\modelmaker-venv\Scripts\python.exe" -B -m unittest discover -s tools/ground -p test_portable_modelmaker_weights.py -v
wsl -d Ubuntu-24.04 -u root --exec /opt/visionassist/venv/bin/python -B -m unittest discover -s /mnt/c/Users/Moth/Desktop/VisionAssist/tools/ground -p test_segmentation_resume.py -v
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\ground\Test-TrainingLauncher.ps1
```

## Limitele verificării

Nu s-a executat intenționat un run complet de 12/20 epoci. Probele limitate nu
estimează acuratețea, siguranța navigării sau consumul unui antrenament complet.
Reluarea se face la ultima epocă salvată complet; ordinea shuffle/GPU nu este
garantată identică bit cu bit. Modelele vechi de gropi care au doar best weights
nu conțin optimizatorul/callbackurile necesare reluării și sunt refuzate explicit.
Evaluările GPU/WSL folosesc CPU pentru inferență; rezultatele Linux și Windows
nu sunt presupuse identice numeric. Nu s-a efectuat un nou build Android, deoarece
automatizarea nu modifică proiectul Android. Inventarul verificat nu reprezintă
un backup pe GitHub al modelelor sau al dataseturilor.
