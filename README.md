# CASAS Aruba — Process Mining e analisi LLM

Il progetto trasforma gli eventi dei sensori CASAS Aruba in un event log, scopre tre reti di Petri e confronta fitness e precision. La dashboard permette analisi esplorative con Google Gemini tramite API key.

La [relazione di progetto](DOCUMENTAZIONE_PROGETTO.md), disponibile anche in [Word con guida al sito](DOCUMENTAZIONE_PROGETTO_CON_GUIDA.docx), documenta i tentativi successivi, le motivazioni, i risultati e i limiti. L'aggiornamento del 27 ottobre 2026 include il confronto completato delle sette configurazioni, interruzioni e tempi effettivi, diagnostiche dell'ordine, integrazione nella dashboard, schermate aggiornate, verifiche e sviluppi futuri. Conserva anche gli esperimenti che non hanno migliorato i risultati. Il capitolo 9 spiega l'uso del sito e indica otto posizioni per gli screenshot con istruzioni e didascalie proposte.

È disponibile anche la [versione inglese in Word](PROJECT_DOCUMENTATION_EN.docx), con [sorgente Markdown](PROJECT_DOCUMENTATION_EN.md), traduzione completa e figure già inserite nei punti S1–S8 della guida. Le figure AI mostrano lo stato reale non configurato, non una risposta generata: questa distinzione è esplicitata nel testo. L'edizione inglese è separata dalla documentazione italiana.

## Avvio Windows

Dalla **radice del repository**, eseguire `setup_and_run.bat`. Richiede Python 3.10+ e accesso a Internet per installare le dipendenze. Lo script crea `.venv_new`, installa o aggiorna i requisiti anche quando l'ambiente esiste già e avvia Streamlit. Per i successivi avvii usare `avvia_dashboard.bat`.

I sorgenti aggiornati e i dati da usare sono quelli nella radice di questo repository. Non occorre una seconda copia del progetto in una cartella omonima.

Installazione manuale:

```powershell
python -m venv .venv_new
.venv_new\Scripts\python.exe -m pip install -r requirements.txt
.venv_new\Scripts\python.exe -m streamlit run dashboard.py
```

Gemini è l’unico servizio AI supportato. Il messaggio "Configurato" indica la creazione del client; credenziali, connessione e disponibilità del modello sono verificate alla prima richiesta.

## Pipeline e file

```powershell
.venv_new\Scripts\python.exe main.py
```

`colab_runner.py` richiama la stessa pipeline. In Colab clonare prima il repository, installare `requirements.txt` e poi eseguire `python /percorso/del/repository/colab_runner.py`. Non servono nomi o copie alternative del dataset.

Tutti i percorsi sono risolti rispetto ai sorgenti, anche se Python viene avviato da un'altra directory.

| File | Contenuto |
|---|---|
| `data/aruba.20111101-20111128_20260218.180945.txt` | Dataset grezzo di ingresso |
| `data/dataset_aruba_attivita.csv` | Event log derivato |
| `data/models.pkl` | Reti di Petri e relativi marking, oppure errori di discovery |
| `data/metrics.json` | Fitness e precision per modello |
| `data/evaluation_metadata.json` | Seed, casi valutati, versione PM4Py e impronte dei dati/metriche |

I dati e i modelli del confronto sono già inclusi. La dashboard carica l'esperimento selezionato dalla barra laterale; non è necessario rigenerarlo a ogni avvio. I file PKL vanno caricati soltanto da fonti fidate.

La dashboard ora offre **Esperimento da caricare** e **Modello di processo** nella barra laterale. Il confronto Colab del 23 ottobre è installato in `data/experiments/comparison_20261023T213310299553Z/`: comprende Alpha, tre configurazioni Heuristic e tre Inductive. L'esperimento selezionato si carica automaticamente; cambiando modello si aggiornano rete, metriche e contesto AI, mentre chat e report del modello precedente vengono azzerati. Il confronto resta visibile per tutti i candidati del medesimo esperimento, incluse le diagnostiche sulle sequenze mescolate. Heuristic 0,30 e 0,50 sono indicati a pari merito.

Per aggiungere un futuro confronto, estrarre la cartella esportata in `data/experiments/<identificativo>/`, mantenendo `data/` con CSV, PKL, metriche e metadati, e `comparison_results.json` nella cartella padre. Solo i pacchetti con CSV e modelli disponibili vengono proposti: al momento il pacchetto principale in `data/` è incompleto perché manca il suo CSV. Il pulsante **Ricarica risultati** rilegge il pacchetto selezionato; **Upload manuale** consente di caricare un altro insieme di file. Non occorre ripetere la discovery per consultare i risultati.

## Calcolo su Google Colab

Per eseguire la discovery fuori dal PC aprire `Aruba_Colab_Training.ipynb` tramite **File → Carica notebook** in [Google Colab](https://colab.research.google.com/). Il codice necessario è incorporato, senza dipendere da commit pubblicati del repository.

1. Caricare il dataset in Google Drive, ad esempio `ArubaColab/input/aruba.txt`.
2. Eseguire il notebook in ordine, collegare Drive e modificare la variabile `DATASET` con il percorso esatto.
3. Usare un runtime CPU; il codice PM4Py non usa automaticamente la GPU. RAM elevata, se disponibile nel proprio piano, può aiutare, senza garantire che ogni log sia gestibile.
4. Nella sezione 4 il raw viene trasformato in streaming con la stessa mappa, gli stessi filtri M/D, i casi data+fascia e la compressione dei duplicati del progetto. `START_DATE` e `END_DATE` delimitano facoltativamente la finestra inclusiva; `None` usa tutto il file. Il riepilogo e `preprocessing_report.json` riportano periodo, esclusioni e sensori non mappati e vengono salvati su Drive prima del caricamento in RAM. La discovery usa comunque tutto il log derivato in RAM, con un solo miner alla volta (Inductive di default).
5. Salvare ed esportare prima della valutazione facoltativa, più costosa. Il notebook crea un backup su Drive e scarica `aruba_results.zip` con CSV, PKL, PNML, metriche e manifest delle versioni. Le metriche sono vuote se la valutazione è saltata.
6. Estrarre lo ZIP e caricare CSV, PKL e JSON nella dashboard locale, oppure copiarli in `data/` dopo aver conservato i vecchi risultati. Non serve trasferire il dataset raw sul PC. La consultazione richiede comunque RAM per il CSV e la visualizzazione.

La modalità `raw_sensors` conserva mappa, stati e segmentazione attuali e non interpreta eventuali annotazioni di attività. Per un log di attività già preparato selezionare `event_log_csv`, con le tre colonne PM4Py richieste. La valutazione facoltativa usa al massimo 20 casi e rimane in-sample: eseguire il codice su Colab non modifica il protocollo scientifico.

`colab_pipeline.py` contiene gli strumenti usati dal notebook. `colab_runner.py` resta l'entry point della pipeline locale per gli ambienti in cui il repository è già installato.

## Confrontare algoritmi su Colab

Il notebook separato `Aruba_Colab_Confronto_Modelli.ipynb` parte dal **TXT originale**, applica il preprocessing del progetto e confronta sette configurazioni sullo stesso CSV generato: Inductive con rumore 0.20 (riferimento), 0.00 e 0.10; Heuristic con dipendenza 0.10, 0.30 e 0.50; Alpha classico. Per ciascuna usa tutti gli eventi per la discovery e gli stessi 20 casi di valutazione selezionati con seed 42. Il confronto rimane in-sample; non è un test di generalizzazione né un'ottimizzazione su giorni nuovi.

Ogni tentativo gira in un processo separato, con limiti iniziali di 600 secondi e 4 GiB di RAM. Il monitor verifica la memoria ogni 0,5 secondi, senza garanzia contro ogni picco OOM. I modelli vengono salvati su Drive prima della valutazione, e la tabella viene aggiornata dopo ogni tentativo. Tempi e limiti vanno adattati alla RAM disponibile del runtime.

Questi sono i valori iniziali nel notebook locale, non una stima della durata: nella prova Colab completata la sola precision ha richiesto 39 minuti e 30 secondi. Prima di un nuovo avvio impostare un limite adeguato; nella discussione operativa è stato consigliato fino a 5.400 secondi per candidato. Registrare i limiti effettivamente usati insieme ai risultati.

L'archivio contiene `comparison.csv`, tutti i modelli e le metriche in formato dashboard, metadati comuni, PNML dei singoli candidati, log ed errori. Riporta anche fitness sulle sequenze permutate e copertura delle etichette: una fitness alta da sola non stabilisce che il modello sia migliore. I tentativi interrotti non ricevono punteggi artificiali.

## Significato del preprocessing

Il primo log analizzato copriva **1–28 novembre 2011**, con **65.783 eventi, 109 casi e 12 etichette di zona**. Dopo la sostituzione con gli artefatti Colab, il CSV verificato copre **1 gennaio–31 marzo 2012**, con **329.885 eventi, 322 casi e 12 zone**. Mancano eventi dal 20 al 28 marzo inclusi; il nome del TXT locale conserva il vecchio periodo e non descrive il contenuto attuale. Dettagli e limiti sono nella relazione di progetto.

- Sono mantenuti i sensori di movimento `M` e porta `D`, compresi entrambi gli stati `ON/OFF` e `OPEN/CLOSE`; i sensori di temperatura sono esclusi.
- La tabella `SENSOR_ACTIVITY_MAP` associa convenzionalmente i sensori a zone. Etichette come `Cucina_Prep` non sono annotazioni validate di attività umane: non dimostrano, da sole, che il residente stia cucinando. La corrispondenza fisica delle zone richiede validazione sulla pianta originale.
- I casi corrispondono a data e fascia: Notte 00–06, Mattina 06–12, Pomeriggio 12–19, Sera 19–24. Non rappresentano episodi comportamentali annotati.
- Eventi consecutivi della stessa zona nello stesso caso vengono compressi. I timestamp restano quelli del file originale, senza conversioni di fuso.

Cambiare filtri, mappatura o segmentazione richiede la rigenerazione di CSV, modelli e metriche con `main.py`.

## Discovery e valutazione

La pipeline locale usa Alpha Miner, Heuristic Miner (`dependency_threshold=0.5`) e Inductive Miner (`noise_threshold=0.2`). I modelli sono scoperti sull'intero log. La valutazione locale token-based usa al massimo **50 casi completi**, estratti con `numpy.random.default_rng(42)` e condivisi fra tutti i modelli. Il secondo esperimento Colab completato contiene invece solo Inductive e valuta **20 casi su 322**. Il benchmark delle sette configurazioni è stato completato e acquisito: Heuristic 0,30 e 0,50 sono primi a pari merito, con fitness 0,957796, precision 0,174000 e media armonica 0,294500. Il controllo sulle sequenze mescolate mostra ancora una selettività debole. Gli artefatti ricevuti sono conservati separatamente in `audit/colab_received_2026-10-27/`.

Sono quindi metriche **in-sample**, non una stima delle prestazioni su dati nuovi. La fitness token-based non coincide con la percentuale di tracce riprodotte perfettamente. La precision misura quanto il modello limita i comportamenti non osservati: alta fitness e bassa precision indicano **sovrageneralizzazione**.

Il modello migliore è quello con la maggiore **media armonica fitness/precision**, chiamata F1 nella dashboard: `2 * fitness * precision / (fitness + precision)`. È lo stesso criterio per entrambe le funzioni di selezione. Non è l'F1 di un classificatore.

Per il confronto installato i valori sono in `data/experiments/comparison_20261023T213310299553Z/data/metrics.json`, con i metadati nella stessa cartella e il confronto dettagliato nella cartella padre. I file `data/metrics.json` e `data/evaluation_metadata.json` appartengono al precedente run con solo Inductive. Versioni o parametri diversi possono modificare i risultati: la dashboard calcola la classifica per il pacchetto caricato e mostra le parità.

## Configurazione AI

`config.json` contiene modello Gemini, temperatura e un campo vuoto per la chiave Google. Si può impostare `GOOGLE_API_KEY` nell'ambiente o inserire la chiave nella sidebar. La configurazione manuale usa il modello selezionato, senza nomi discordanti nell'interfaccia.

Gemini usa il Google GenAI SDK (`google-genai`); il modello predefinito resta quello di `config.json`, modificabile dalla sidebar. La migrazione segue la [documentazione ufficiale Google](https://ai.google.dev/gemini-api/docs/migrate).

Il contesto delle azioni identifica esperimento e modello selezionati, metriche, diagnostiche disponibili e un riepilogo della rete, insieme al DFG osservato del log. Cambiando modello vengono cancellati chat e report precedenti. Gemini riceve un campione deterministico di tracce complete fino a 20.000 eventi. Il limite è in righe, non una garanzia sul numero di token; tracce più lunghe del budget sono escluse e l'assenza di un campione viene segnalata.

Il contesto è passato come testo nella richiesta; per Gemini viene inviato al servizio Google soltanto quando si richiede un'analisi. Non vengono creati file temporanei o upload persistenti. Il contesto DFG testuale contiene i primi 30 flussi per frequenza e le prime 5 varianti, abbreviate dopo 20 eventi.

Nella dashboard le metriche sono barre affiancate con scala 0–1. La distribuzione delle zone mostra **eventi compressi**, non permanenza nelle stanze. Il confronto delle fasce usa di default eventi per ora di calendario: il denominatore interseca ogni fascia con la finestra fra primo e ultimo timestamp, correggendo i giorni di bordo parziali. Non stima la presenza né rileva buchi interni di acquisizione. Sono disponibili anche i totali e la tabella dei denominatori.

La scheda modelli affianca alla rete di Petri un DFG semplificato dei 12 flussi più frequenti, con conteggi e copertura espliciti. Il DFG descrive il log e non è una riduzione della rete selezionata; le transizioni fra casi diversi sono escluse.

Le risposte LLM sono suggerimenti esplorativi: anomalie, spiegazioni e prossime zone richiedono verifica sui dati. Il DFG descrive il comportamento osservato, non una regola ideale, e le previsioni non sono probabilità calibrate.

## Verifiche

```powershell
.venv_new\Scripts\python.exe -m unittest discover -s tests -v
.venv_new\Scripts\python.exe -m pip check
```

La revisione Gemini ha superato tutti i **30 test automatici** della suite. Le verifiche includono corrispondenza del CSV installato con il raw, preprocessing, notebook, campionamento, esportazione, gestione degli esperimenti, grafici e client Gemini con risposte simulate. I test del client non inviano richieste reali a Google. I test di discovery usano piccoli log sintetici; non è stata ripetuta la discovery del dataset completo. Questi controlli tecnici non dimostrano generalizzazione su nuovi dati. Le richieste reali a Gemini richiedono una API key valida e un modello disponibile all’account.
