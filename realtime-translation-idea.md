Ha két ember egymás szavába beszél, akkor a probléma már source separation + localization + diarization + speaker identification egyszerre.

És a jó hír: 2026-ban ezek nagy része már megoldott technológia, de a „két ember egyszerre beszél egy zajos szobában, telefonra szerelt 4 mikrofonos arrayből, 200–400 ms latencyvel tökéletesen különválasztva” még egyáltalán nem solved problem.

Röviden: én ezt csinálnám
                4–6 MEMS MIC
                     │
                     ▼
             ┌───────────────┐
             │ ESP32-S3/P4   │
             │               │
             │ AEC           │
             │ NS            │
             │ VAD           │
             │ beamforming   │
             │ DOA           │
             └───────┬───────┘
                     │
              4–6 channel PCM
                     │
                     ▼
              ┌─────────────┐
              │   PHONE     │
              │             │
              │ separation  │
              │ diarization │
              │ speaker ID  │
              └──────┬──────┘
                     │
              selected stream
                     │
                     ▼
              GPT realtime
                     │
                     ▼
                translation
                     │
                     ▼
               Bluetooth
Az ESP32-re tenném a klasszikus DSP-t, de a neurális source separationt már a telefonra.

1. Először a legfontosabb különbség
Tegyük fel:

👨 John: I think we should leave now.

és ugyanakkor:

👩 Maria: No, wait for Anna.

A mikrofon ezt látja:

MIX = John + Maria + noise + room reflections
Azt kell előállítanunk:

Stream A = John
Stream B = Maria
Ez nem speaker diarization.

A diarization csak azt mondja:

0.0–1.2   Speaker A
1.2–2.1   Speaker B
2.1–3.4   Speaker A
Ha egyszerre beszélnek, azt már overlapped speech / source separation problémának hívjuk.

A modern rendszerek erre már külön modelleket használnak. Például a pyannote 4.x-ben már van speech-separation pipeline és joint diarization/separation modell is. (GitHub)

2. A hangszín önmagában nem elég
Ez egy nagyon fontos pont.

Két embernek lehet:

John:
  110 Hz fundamental
  férfi
  mély hang

Maria:
  220 Hz fundamental
  nő
  magasabb hang
Ilyenkor könnyebb.

De ha:

John:   mély férfihang
Peter:  szintén mély férfihang
akkor a puszta pitch/frekvencia alapján nem lehet megbízhatóan szétválasztani őket.

A modern speaker embedding modellek ezért sokkal komplexebb hangjellemzőket használnak.

Tipikusan:

mel spectrum
+
formants
+
prosody
+
timbre
+
phonetic characteristics
+
temporal patterns
és ebből készül például egy:

speaker embedding = [0.12, -0.31, 0.77, ...]
A speaker embedding alapján lehet eldönteni:

„Ez valószínűleg John.”

A diarization rendszerek ténylegesen ilyen speaker characteristics/embedding megközelítést használnak. (NVIDIA Docs)

3. De a mikrofonarray ad még egy nagyon fontos információt
Honnan jön a hang?

Ez a DOA — Direction of Arrival.

Például:

              PHONE
                │
        MIC1 ───┼─── MIC2
                │
             MIC3
John:

          👨
           \
            \
             \ 35°
              \
             PHONE
Maria:

PHONE
   \
    \ -55°
     \
      👩
A több mikrofon között mérhető:

időeltérés

fáziseltérés

amplitúdókülönbség

alapján meg lehet becsülni a hangforrás irányát.

4. És itt lesz igazán erős a rendszer
Nem csak ezt tudod mondani:

„ez John hangja”

hanem:

Speaker candidate #1
    voice embedding → John
    direction → +35°

Speaker candidate #2
    voice embedding → Maria
    direction → -55°
Ez két egymást erősítő információ.

Spatial identity
John = +35°
Maria = -55°
Ha két hang hasonló hangszínű, a térbeli információ segíthet.

És fordítva: ha két ember ugyanabból az irányból beszél, a speaker embedding segíthet.

5. De van egy nagyon fontos 2026-os tanulság
Ne egyszerűen beamforming → diarization láncot építs.

Egy friss, 2026-os kutatás szerint az átfedő beszédnél a klasszikus beamformer frontend még ronthatja is a foundation-model-alapú diarization teljesítményét; jobb eredményt adhat, ha a térbeli információt közvetlenül a downstream modellhez adjuk. (arXiv)

Ez szerintem nagyon fontos a te projektednél.

Vagyis:

❌ MIC ARRAY
      ↓
beamformer
      ↓
mono audio
      ↓
speaker model
helyett inkább:

MIC ARRAY
   │
   ├── audio channels
   │
   ├── spatial features
   │
   └── DOA
        ↓
    neural model
        ↓
speaker separation + identification
Ne dobd el túl korán a multi-channel információt.

6. Milyen hardvert választanék?
Ha tényleg telefonra szerelhető modult szeretnél, én nem 2 mikrofont választanék.

Minimum:
4 mikrofon

Én inkább:
6 mikrofon

felé mennék.

A geometria legalább olyan fontos, mint a mikrofonok száma.

Egy 2026-os Espressif microphone-array guideline 2 mikrofonra kb. 4–6,5 cm, hárommikrofonos körre pedig 4–6,5 cm mikrofontávolságot javasol; az array mikrofonjainak érzékenysége és fázisa között is szoros egyezést ír elő. (Espressif Systems)

Ez azt jelenti, hogy egy ilyen:

     M1       M2

M3      PHONE      M4

     M5       M6
elrendezés sokkal érdekesebb lehet, mint hat mikrofon véletlenszerűen egymás mellett.

7. ESP32-S3 vagy ESP32-P4?
Itt módosítanám az eredeti tervünket.

ESP32-S3
Jó:

audio capture

VAD

noise suppression

alap DSP

beamforming

Wi-Fi

alacsony fogyasztás

Az Espressifnek konkrét hárommikrofonos ESP32-S3 referenciahardware-e is van, a Korvo-1. (GitHub)

ESP32-P4
Ha új hardware-t tervezel, ezt is komolyan megfontolnám.

Az Espressif jelenlegi AFE frameworkje már tartalmaz:

AEC

noise suppression

VAD

BSS / blind source separation

funkciókat. A BSS kétcsatornás feldolgozást is támogat. (Espressif Systems)

Tehát az ESP32/P4 oldalon már nem neked kell nulláról megírnod az összes audio frontendet.

8. Mi futhat az ESP32-n?
Én ezt tenném oda:

① Microphone synchronization
Nagyon fontos.

MIC1 ─┐
MIC2 ─┤
MIC3 ─┤ → synchronized frames
MIC4 ─┤
MIC5 ─┤
MIC6 ─┘
② High-pass / low-pass
③ Noise suppression
④ VAD
⑤ AEC
ha a telefon/füles hangja visszaszivárog.

Az Espressif ESP-SR AFE-ben ezekhez már vannak kész komponensek. (Espressif Systems)

⑥ DOA / spatial features
⑦ esetleg egyszerű beamforming
⑧ PCM továbbítás a telefonra
9. Amit NEM tennék az ESP32-re
Nem futtatnék rajta egy nagy:

SepFormer
WavLM
ECAPA-TDNN
SortFormer
jellegű modern modellt.

Nem azért, mert elméletileg lehetetlen bármit ML-ezni az ESP32-n, hanem mert rossz helyre tennéd a számítási terhelést.

A telefon sokkal jobb erre.

10. Telefonon már nagyon komoly separation modellek vannak
Például a SpeechBrainnek van:

SepFormer

RE-SepFormer

ConvTasNet

DPRNN

DPTNet

SkiM

speech-separation implementációja és pretrained modellje. (GitHub)

Az ESPnet pedig ennél is szélesebb választékot kínál, többek között:

TasNet

DPRNN

Conformer

FaSNet

neural beamformers

DCCRN

Deep Clustering

és egyéb separation/enhancement modelleket. (GitHub)

11. De a separation modellnek van egy nagy problémája
Latency.
Egy nagyon jó offline separator:

audio
████████████████████
        ↓
    separation
        ↓
speaker A
speaker B
nem feltétlenül alkalmas arra, hogy:

audio
▌▌▌▌▌▌▌▌
 ↑
real-time
módon működjön.

A neural separation gyakran több jövőbeli audio mintát is használ.

Ez az ún. algorithmic look-ahead.

12. Mekkora latencyt okoz?
Itt nagyon fontos, hogy ne adjunk hamis „10 ms” vagy „50 ms” számot.

A separation latency függ:

modelltől

chunk mérettől

hop size-tól

look-ahead-től

CPU/GPU/NPU-tól

quantizationtől

channel counttól

speaker counttól

Ezért inkább engineering budgetet adnék.

Klasszikus DSP
VAD             5–20 ms
NS              5–20 ms
beamforming     1–10 ms
DOA             5–20 ms
~10–40 ms

jó hardveren.

Neural speaker separation
Realtime-optimized modellnél:

~30–150 ms

lehet reális cél.

Nagyobb/kevésbé realtime modellnél:

100–500+ ms

is lehet.

Ezért nem tennék a V1-be egy nagy SepFormert csak azért, mert jó a benchmarkja.

13. Van egy nagyon fontos optimalizáció
Nem kell mindig separationt csinálnod.

Ha csak:

John beszél
akkor nincs szükség:

John
Maria
Peter
Anna
négy külön streamre.

A pipeline:

one speaker detected
      ↓
normal enhancement
      ↓
GPT
Amikor érzékeled:

overlap probability > threshold
akkor aktiválod:

target speaker extraction
Ez óriási teljesítmény- és latency-előny.

14. Én így építeném a döntési logikát
                  AUDIO
                    │
                    ▼
                  VAD
                    │
              ┌─────┴─────┐
              │           │
         1 speaker    multiple speech
              │           │
              ▼           ▼
          normal       overlap
          pipeline       detector
                          │
                    ┌─────┴─────┐
                    │           │
                   no          yes
                    │           │
                    ▼           ▼
                diarization   separation
                                │
                                ▼
                         target speaker
                                │
                                ▼
                              GPT
Ez szerintem sokkal jobb, mint folyamatosan separationt futtatni.

15. Az overlap detection már lényegében megoldott
2026-ban erre több kész rendszer van.

A pyannote modern diarization pipeline-jai kezelik az overlapping speech problémát, és újabb verziókban joint diarization/separation irányú modellek is vannak. (GitHub)

NVIDIA oldalon pedig a SortFormer streaming diarization modellje kifejezetten online/chunked használatra készült. A jelenlegi dokumentációban a streaming változat legfeljebb 4 speakeres workloadokra van pozicionálva. (NVIDIA Docs)

De ez nem jelenti azt, hogy az overlap tökéletesen megoldott.

16. A legnehezebb esetek
Könnyű
John:  █████████████
Maria:             ███████████
Nincs overlap.

Nagyon jól megoldható.

Közepes
John:  █████████████████
Maria:       █████
Rövid overlap.

Jól kezelhető.

Nehéz
John:  ████████████████████
Maria: ████████████████████
Ketten egyszerre beszélnek végig.

Source separation kell.

Nagyon nehéz
John:     █████████████████
Maria:    █████████████████
Peter:    █████████████████
Noise:    █████████████████
TV:       █████████████████
Ez már nagyon nehéz.

És ha mindenki:

hasonló hangmagasságú

ugyanabból az irányból beszél

visszhangos szobában van

akkor nincs olyan DSP-trükk, ami garantáltan megoldja.

17. A szoba akusztikája óriási probléma
Ez valószínűleg nagyobb probléma lesz, mint elsőre gondolnád.

Egy:

szőnyeg + függöny + kanapé
szoba:

speaker → mic
viszonylag könnyű.

Egy:

üveg + beton + csempe
hely:

speaker
  ↓
wall
  ↓
reflection
  ↓
mic
és:

direct sound + reflection 1 + reflection 2 + reflection 3
érkezik.

Ez a reverberation.

És a separation modelleknek sokkal nehezebb dolguk lesz.

18. A telefon elhelyezése is kritikus
Ha a telefon:

speaker → PHONE
és a speaker 1 méterre van:

jó.

Ha:

speaker
   ↓

PHONE

   ↓
table reflection
már rosszabb.

Ha pedig a telefon zsebben van:

felejtsük el a jó spatial separationt.

A telefonra rakott hardware előnye pont az, hogy a microphone array geometriája ismert és kontrollált.

19. A mikrofonok egyezése nagyon fontos
Nem érdemes:

MIC1 = random AliExpress MEMS
MIC2 = másik gyártó
MIC3 = harmadik
Az arraynek konzisztensnek kell lennie.

Az Espressif saját guideline-ja is külön hangsúlyozza az érzékenység-, fázis- és frekvencia-illesztést. (Espressif Systems)

Én ezért:

azonos mikrofonmodell + azonos PCB layout + factory calibration

irányba mennék.

20. A speaker identificationhez nem kell folyamatosan újra tanulni
Például amikor először találkozol Johnnal:

John
  ↓
5–10 sec relatively clean speech
  ↓
speaker embedding
  ↓
John profile
Utána:

new segment
 ↓
embedding
 ↓
cosine similarity
 ↓
John = 0.91
Ez sokkal olcsóbb.

És ha van spatial információ:

voice similarity = 0.91
direction similarity = 0.96
temporal continuity = 0.94
akkor nagyon stabil lehet.

21. A diarization és speaker identification együtt sokkal jobb
Én három state-et tartanék:

UNKNOWN
   ↓
CANDIDATE
   ↓
IDENTIFIED
Például:

Speaker 1
embedding confidence = 0.62
→ UNKNOWN

Speaker 1
embedding confidence = 0.79
→ CANDIDATE

Speaker 1
embedding confidence = 0.94
→ JOHN
Így nem fog a rendszer egyetlen rossz 300 ms-os hangrészletből azt mondani:

„Ez biztos John.”

22. Melyik probléma mennyire solved 2026-ban?
Probléma	2026 állapot
VAD	🟢 nagyon jó
Noise suppression	🟢 nagyon jó
AEC	🟢 nagyon jó
Beamforming	🟢 érett
DOA	🟢 érett
Speaker embedding	🟢 nagyon jó
Speaker identification	🟢 jó
Speaker diarization	🟢 nagyon jó
Overlap detection	🟢 jó
2-speaker separation	🟢 jó
3+ speaker separation	🟡 nehéz
Realtime separation	🟡 jó, de kompromisszumos
Erős reverberation	🟡 nehéz
hasonló hangú emberek	🟡 nehéz
3 ember egyszerre	🟠 nehéz
4+ ember egyszerre	🔴 nagyon nehéz
tökéletes voice identity preservation	🔴 nincs garantálva
<300 ms teljes translation pipeline	🟡 megvalósítható, de agresszív cél
23. A kész könyvtárak, amiket én konkrétan néznék
ESP32
ESP-SR

AEC / NS / VAD / BSS front-endhez. (Espressif Systems)

ESP-DSP

FFT, FIR, IIR, matrix/vector operations stb.; ESP32-S3/P4-re optimalizált implementációkkal. (GitHub)

ESP-ADF

magasabb szintű audio pipeline-okhoz. (Espressif Systems)

Telefon / backend
pyannote.audio

Diarization + speaker embedding + modern separation pipeline-ok. (GitHub)

NVIDIA NeMo

SortFormer / streaming diarization / speaker embedding. (NVIDIA Docs)

SpeechBrain

SepFormer / RE-SepFormer / ConvTasNet / DPRNN stb. (GitHub)

ESPnet

ha komolyabb research/production speech pipeline-t akarsz és többféle neural separation/beamforming modellből választanál. (GitHub)

24. Amit én a te projektednél választanék
Nem egyetlen „AI speaker separator”-t építenék.

Hanem hibrid rendszert:

                 6 MIC ARRAY
                      │
                      ▼
              ESP32-P4 / S3
                      │
          ┌───────────┼───────────┐
          │           │           │
         AEC          NS          VAD
          │           │           │
          └───────────┼───────────┘
                      │
                 raw channels
                      │
                      ▼
                   PHONE
                      │
          ┌───────────┼────────────┐
          │           │            │
          ▼           ▼            ▼
         DOA      embedding     overlap
          │           │          detection
          └───────────┼────────────┘
                      │
              ┌───────▼────────┐
              │ Decision layer │
              └───────┬────────┘
                      │
           ┌──────────┴───────────┐
           │                      │
       no overlap             overlap
           │                      │
           ▼                      ▼
       diarization          target speaker
           │                  separation
           └──────────┬───────────┘
                      │
                speaker audio
                      │
                      ▼
               GPT Realtime
                      │
                  translation
                      │
                      ▼
                 Bluetooth
Ezzel egy nagyon fontos dolgot nyersz:
nem kell minden másodpercben megoldanod a „cocktail party problem”-et.

A legtöbb normál beszélgetésben:

90% idő:
  egy ember beszél
és csak bizonyos részekben:

10%:
  overlap
A separation modellt csak akkor indítod, amikor tényleg szükséges.

25. A latency-budgetem erre a rendszerre
Én V1-ben ezt céloznám:

Komponens	Cél
6-channel capture	5–10 ms
ESP32 AEC/NS/VAD	5–20 ms
DOA	5–15 ms
speaker embedding	10–30 ms
overlap detection	10–30 ms
neural separation	30–100 ms
phone → OpenAI	20–60 ms
realtime translation onset	150–350 ms
output → BT	30–120 ms
Normál, egybeszélős esetben:

~250–500 ms
Overlap esetén:

~300–650 ms
jó cél lehet.

A separation nem feltétlenül ad hozzá 100 ms-ot minden esetben, mert csak overlap esetén aktiválod.

És egy szerintem nagyon fontos design-döntés
Ha az a cél, hogy a felhasználó azonnal hallja a fordítást, én nem próbálnám az overlap esetén mindig tökéletesen szétválasztani a két embert.

Inkább:

confidence > 0.85
       ↓
fordítsd

confidence 0.60–0.85
       ↓
fordítsd, de tarts rövid buffer-t

confidence < 0.60
       ↓
várj / kérj új audio-t
Így a rendszer folyamatosan használható marad, és nem egy tökéletességre optimalizált offline diarizálóvá válik.

A 2026-os rendszerek is jól mutatják ezt a trade-offot: például a NVIDIA streaming SortFormer kifejezetten bounded-latency online feldolgozásra készült, míg az offline diarizálás magasabb pontosságot céloz; a dokumentációjuk jelenleg 4-speaker streaming modellt is kínál. (NVIDIA Docs)