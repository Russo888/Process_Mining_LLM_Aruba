# Process Mining e supporto LLM su dati domestici Aruba

**Relazione di progetto — aggiornata al 27 ottobre 2026**

La relazione documenta il percorso sperimentale, dalle prime quattro settimane al confronto di sette configurazioni su tre mesi e alla loro integrazione nella dashboard. Tutte le sette prove finali sono state completate su Colab e gli artefatti sono stati verificati il 27 ottobre 2026. Heuristic con soglia 0,30 o 0,50 migliora la media armonica di circa il 90% rispetto al riferimento Inductive sullo stesso campione, ma la precision rimane bassa e il controllo sull'ordine non dimostra ancora una buona rappresentazione della routine. La relazione conserva risultati negativi, tentativi interrotti per memoria e motivazioni delle modifiche. Documenta inoltre la consultazione dei modelli, i controlli dell'interfaccia e le verifiche scientifiche ancora aperte.

## 1. Obiettivo del progetto

Il progetto studia come trasformare le registrazioni dei sensori domestici in una rappresentazione comprensibile delle sequenze osservate. La pipeline prepara un event log, applica algoritmi di process discovery, valuta le reti di Petri ottenute e mostra dati e risultati in una dashboard. Un assistente basato su LLM aiuta a consultare e spiegare le informazioni disponibili.

La dashboard costituisce il sito applicativo del progetto ed è stata verificata localmente con Streamlit. Le modifiche descritte riguardano il progetto sul PC; non attestano una pubblicazione su un servizio web esterno.

La domanda sperimentale è: **quanto bene un modello riesce a rappresentare le sequenze osservate, senza consentire troppi comportamenti aggiuntivi?** Non basta ottenere un programma funzionante o una fitness vicina a 1: bisogna verificare che la struttura trovata descriva qualcosa di specifico nei dati.

Questo lavoro è attualmente uno studio esplorativo. Non è stata dimostrata la capacità di prevedere attività, riconoscere anomalie reali o generalizzare ad altre abitazioni.

## 2. Componenti e ruoli

| Componente | Ruolo nel progetto |
|---|---|
| Preprocessing Python | Trasforma le righe dei sensori in eventi, zone e casi. |
| Alpha Miner | Produce una rete di Petri nella configurazione classica usata dal progetto. |
| Heuristic Miner | Produce una rete usando relazioni fra eventi e una soglia di dipendenza. |
| Inductive Miner | Produce una rete attraverso una struttura di processo; viene variata la soglia di rumore. |
| PM4Py | Esegue discovery, esportazione e misure di conformità. |
| Google Colab | Esegue il calcolo che richiede più memoria di quella disponibile sul PC. |
| Streamlit | Mostra dati, reti e metriche nella dashboard. |
| Google Gemini tramite API key | Supporta l'interpretazione testuale del contesto fornito dalla dashboard. |

Nel dialogo operativo si è usata anche la parola “addestramento”. Più precisamente, qui si applicano algoritmi di **process discovery** a un log. Gemini non viene addestrato su questo dataset e non costruisce le reti valutate con fitness e precision.

## 3. Dataset e preparazione degli eventi

### 3.1 Due finestre analizzate

| Proprietà | Primo esperimento | Secondo esperimento |
|---|---:|---:|
| Periodo del CSV derivato | 1–28 novembre 2011 | 1 gennaio–31 marzo 2012 |
| Eventi dopo il preprocessing | 65.783 | 329.885 |
| Casi | 109 | 322 |
| Etichette di zona | 12 | 12 |
| Varianti complete delle sequenze | 108 | 320 |
| Mediana degli eventi per caso | 481 | 884 |
| Massimo degli eventi per caso | 3.708 | 4.759 |

La seconda finestra contiene eventi in 82 dei 91 giorni di calendario. Mancano registrazioni dal 20 al 28 marzo inclusi: il vuoto è presente anche nel file grezzo locale. I giorni ai bordi delle finestre sono parziali. Tre mesi di calendario non equivalgono quindi a tre mesi completi e continui di osservazione.

Il file grezzo locale conserva un nome riferito a novembre 2011, ma dopo la sostituzione contiene dati di gennaio–marzo 2012. Per descrivere il dataset si sono usati i timestamp effettivi, non il nome del file.

La provenienza dell'estratto e la corrispondenza della mappa sensori con la pianta corretta restano da documentare in modo definitivo. Le zone sono assegnate dalla tabella del progetto: finché tale mappa non è validata, non si devono trattare le etichette come prova di attività umane effettivamente svolte.

### 3.2 Preprocessing adottato

1. Leggere data, ora, identificativo e stato del sensore dal TXT.
2. Conservare i sensori di movimento e porta previsti dalla mappa; escludere temperatura e sensori non mappati.
3. Convertire i timestamp e associare ogni sensore alla zona definita dal progetto.
4. Costruire un caso per ogni combinazione di giorno e fascia: notte 00–06, mattina 06–12, pomeriggio 12–19, sera 19–24.
5. Comprimere le ripetizioni consecutive della stessa zona all'interno dello stesso caso.
6. Salvare le colonne `case:concept:name`, `concept:name` e `time:timestamp` nel CSV derivato.

La configurazione mantiene sia ON sia OFF e sia OPEN sia CLOSE. Un evento derivato è quindi una registrazione compressa associata a una zona, non necessariamente una nuova attivazione o uno spostamento fisico. Il conteggio degli eventi non misura il tempo trascorso in una stanza.

Nel notebook Colab il TXT viene elaborato riga per riga. Questo limita la memoria necessaria durante la preparazione; la discovery carica comunque il log derivato in RAM. Vengono salvati anche un report delle esclusioni, la finestra temporale e i conteggi del preprocessing. Il lettore streaming richiede righe cronologiche e segnala un ordine non valido.

### 3.3 Una scelta già esaminata, ma non adottata

Sul primo dataset è stata verificata la sensibilità agli stati dei sensori: mantenendo solo ON/OPEN, con la stessa mappa e compressione, gli eventi derivati passavano da 65.783 a 33.310. Il dato mostra che la rappresentazione dipende molto da questa scelta. Non dimostra che gli eventi esclusi siano tutti errori e non costituisce un confronto completo di modelli con i due preprocessing. Il benchmark attuale conserva il preprocessing di riferimento per isolare il cambiamento di algoritmo e soglia.

## 4. Come vengono valutati i modelli

La **fitness token-based** misura quanto il modello riesce a riprodurre gli eventi osservati. Non coincide con la percentuale di tracce riprodotte perfettamente.

La **precision token-based** valuta quanto il modello limita i comportamenti aggiuntivi rispetto a quelli osservati. Una precision di 0,08 non significa “8% di previsioni corrette”: non è l'accuracy di un classificatore.

La dashboard chiama **F1** la media armonica delle due misure:

`F1 = 2 × fitness × precision / (fitness + precision)`

È un criterio per ordinare i candidati, non una certificazione di qualità e non l'F1 di un problema di classificazione. Una precision alta accompagnata da fitness quasi nulla non indica un buon modello del log.

La discovery usa tutto il log della rispettiva prova. Le metriche vengono calcolate su casi completi campionati dallo stesso log, con seed 42: 50 nel primo esperimento e 20 nel secondo. Si tratta di valutazione **in-sample**, cioè su dati già disponibili durante la costruzione del modello. Non è ancora stata eseguita una separazione temporale fra training, validazione e test.

Nel terzo esperimento sono mantenuti gli stessi 20 casi del secondo. Il seed rende ripetibile il campionamento, ma non trasforma il campione in una validazione indipendente. I 21.069 eventi valutati appartengono a 20 periodi, non a 21.069 osservazioni indipendenti: una singola traccia può contenere molti eventi correlati.

## 5. Primo tentativo: quattro settimane e tre algoritmi

Il primo tentativo ha applicato Alpha, Heuristic con soglia di dipendenza 0,50 e Inductive con soglia di rumore 0,20 al dataset di novembre. L'obiettivo era verificare il funzionamento della pipeline e confrontare tre modi diversi di costruire il modello.

| Modello | Fitness | Precision | Media armonica |
|---|---:|---:|---:|
| Alpha Miner | 0,0229 | 0,6637 | 0,0444 |
| Heuristic Miner | 0,0035 | 0,5355 | 0,0069 |
| Inductive Miner | 0,9978 | 0,1549 | 0,2681 |

Alpha e Heuristic riproducevano male il log. La loro precision relativamente maggiore andava letta insieme a una fitness molto bassa. Inductive risultava primo secondo la media armonica, ma la precision restava debole: la rete consentiva troppi comportamenti.

Per Inductive solo 5 delle 50 tracce valutate erano perfettamente fitting, nonostante la fitness aggregata vicina a 1. La rete rappresentava 10 delle 12 etichette e ometteva le due uscite. Inoltre, 108 varianti su 109 casi indicavano sequenze lunghe e quasi tutte diverse. Questi elementi hanno motivato un approfondimento dei dati e della selettività del modello.

## 6. Secondo tentativo: più dati e calcolo su Colab

L'ipotesi operativa era che una finestra più ampia potesse fornire maggiore varietà e più osservazioni dei comportamenti meno frequenti. La memoria del PC costituiva un limite pratico; per questo è stato preparato un notebook Colab autonomo, con preprocessing, discovery, esportazione e valutazione.

La seconda prova completata ha usato circa tre mesi di dati e il solo Inductive Miner, mantenendo la soglia di rumore a 0,20. La valutazione è stata limitata a 20 casi completi per contenerne il costo. Il modello è stato esportato prima della valutazione, così da poterlo recuperare anche in caso di interruzione successiva.

| Misura Inductive | Primo tentativo | Secondo tentativo |
|---|---:|---:|
| Fitness | 0,997812 | 0,999858 |
| Precision | 0,154879 | 0,083982 |
| Media armonica | 0,268138 | 0,154949 |
| Tracce perfettamente fitting | 5/50, pari al 10% | 19/20, pari al 95% |
| Etichette rappresentate | 10/12 | 12/12 |

La copertura delle etichette è migliorata e il modello riproduce quasi perfettamente il campione. Tuttavia, la precision è diminuita di circa il 45,8% e la media armonica del 42,2%. Non emerge quindi un miglioramento complessivo nella qualità della rappresentazione del processo.

Questo confronto storico cambia sia periodo sia campione di valutazione. Non consente di attribuire il peggioramento alla sola quantità di dati. Mostra però che aumentare la finestra, mantenendo la rappresentazione adottata, non ha risolto il problema osservato.

### 6.1 Controllo con sequenze mescolate

Per verificare se il modello fosse sensibile all'ordine degli eventi, sono state permutate le etichette entro ciascuno degli stessi 20 casi, conservando timestamp e frequenze. Il replay è stato poi ripetuto.

| Sequenze del secondo tentativo | Fitness | Tracce fitting |
|---|---:|---:|
| Osservate | 0,9998583842 | 95% |
| Con ordine mescolato | 0,9998583842 | 95% |

Il modello ha ottenuto gli stessi valori anche con l'ordine alterato. Questo controllo suggerisce scarsa selettività rispetto all'ordine e spiega perché la sola fitness elevata non basti. Non è una validazione completa dell'anomaly detection: non sono state fornite anomalie reali annotate.

Anche sul primo dataset un controllo più piccolo, sui primi dieci casi, aveva mostrato fitness quasi invariata: 0,997618 sulle sequenze originali contro 0,997174 su quelle permutate. I due controlli sono diagnostiche separate, eseguite su campioni differenti.

### 6.2 Costo misurato della valutazione

L'output Colab comunicato riporta circa 2 secondi per il replay dei 20 casi e **39 minuti e 30 secondi** per il passaggio relativo alla precision, con una barra da 20.962 elementi. Questi elementi riguardano i prefissi delle sequenze elaborati nella valutazione, non 20.962 periodi indipendenti. La precision è stata quindi il costo dominante della vecchia cella 8.

I valori esportati sono fitness `0.9998583842422839` e precision `0.08398199566503706`. L'output conferma il completamento della valutazione e il backup dello ZIP su Drive. La durata osservata è riferita a quella specifica esecuzione, non a tutti gli algoritmi.

## 7. Terzo tentativo: confronto controllato di algoritmi e soglie

**Stato: sette configurazioni completate; archivio acquisito e verificato il 27 ottobre 2026.**

Il nuovo esperimento parte dal TXT ed esegue una sola preparazione del log. Tutti i candidati ricevono lo stesso CSV derivato e gli stessi 20 casi di valutazione, scelti con seed 42. In questo modo il confronto interno cambia algoritmo o parametro, mantenendo comuni i dati e il protocollo.

| ID | Algoritmo | Parametro | Funzione nel confronto |
|---|---|---|---|
| `inductive_020` | Inductive | Rumore 0,20 | Ripetere la configurazione di riferimento. |
| `inductive_000` | Inductive | Rumore 0,00 | Valutare l'effetto della soglia zero. |
| `inductive_010` | Inductive | Rumore 0,10 | Valutare una soglia intermedia. |
| `heuristic_030` | Heuristic | Dipendenza 0,30 | Confrontare un algoritmo differente. |
| `heuristic_050` | Heuristic | Dipendenza 0,50 | Riprendere la soglia della pipeline iniziale. |
| `heuristic_010` | Heuristic | Dipendenza 0,10 | Valutare una soglia più bassa. |
| `alpha` | Alpha classico | Nessuna soglia variata | Includere nuovamente il terzo algoritmo. |

Sono sette configurazioni appartenenti a tre algoritmi. Alpha viene eseguito una volta perché la configurazione classica adottata non espone le due soglie variate per gli altri algoritmi. Ripetere la medesima configurazione sugli stessi dati non aggiungerebbe un confronto di parametri.

Il protocollo comprende fitness, precision, media armonica, percentuale di tracce fitting, etichette omesse, dimensioni della rete e fitness dopo permutazione degli eventi. La differenza fra fitness originale e mescolata è una diagnostica dell'ordine; non ha una soglia universale che certifichi un buon modello.

### 7.1 Limiti di risorse e loro revisione

I candidati girano uno alla volta in processi separati. Il notebook iniziale prevedeva 600 secondi e 4 GiB per processo. Nel dialogo operativo sono stati indicati 10 GiB e successivamente 2.100 secondi, pari a 35 minuti. Il tempo realmente osservato per la precision del riferimento, 39 minuti e 30 secondi, ha mostrato che 35 minuti sarebbero stati insufficienti per completare una prova analoga.

Sono stati discussi limiti più ampi, prima 3.600 e poi 5.400 secondi per configurazione. Nel primo confronto avviato con 5.400 secondi e 10 GiB, l'output comunicato mostra `memory_limit` per Inductive 0,20 e 0,00 e l'avvio di Inductive 0,10. Non disponiamo dell'archivio di quella prima esecuzione per stabilire fase e consumo esatto dell'interruzione.

La successiva esecuzione `comparison_20261023T213310299553Z` ha mantenuto il timeout di 5.400 secondi, disattivando il limite del nostro supervisore con `MAX_MODEL_RAM_GB=None`. Lo screenshot di avvio conferma queste impostazioni e lo ZIP conferma il completamento di tutti i candidati. Il limite artificiale era quindi un ostacolo operativo nelle prime prove; non misurava la qualità del modello. La memoria fisica di Colab restava comunque finita.

Nel codice utilizzato, disattivare il limite RAM disattivava anche il campionamento della memoria. Il valore `peak_worker_gb=0.0` esportato per ogni candidato significa pertanto **picco RAM non misurato**, non consumo nullo. Non è possibile ricavare da questi file quanta memoria sarebbe stata sufficiente.

I limiti includono il lavoro del processo del candidato, dalla lettura dei dati alla costruzione e valutazione. Un `timeout`, un `memory_limit` o un errore indicano una prova incompleta: non ricevono metriche pari a zero e non possono essere classificati come risultati scientificamente peggiori.

Il modello viene salvato prima della valutazione e il riepilogo viene aggiornato su Drive dopo ogni tentativo. I salvataggi proteggono il lavoro completato; non equivalgono a una ripresa automatica del calcolo interrotto.

Il limite temporale è applicato a ciascuna configurazione, non all'intera cella. Sette limiti di 90 minuti avrebbero consentito fino a 10 ore e mezza di lavoro dei processi, ma la durata osservata è stata molto inferiore. Modificare i limiti nella cella dopo averla avviata non modifica i parametri già passati al confronto in corso. Chiudere la sessione prima della cella di confezionamento finale non ha cancellato i risultati già copiati su Drive: l'archivio è stato recuperato scaricando la cartella del confronto.

### 7.2 Risultati del confronto completato

Le durate riportate sono quelle misurate dal supervisore per il singolo processo, comprensive del suo avvio. Le metriche sono state lette dai JSON originali e confrontate con CSV e metadati; i calcoli costosi di conformità non sono stati ripetuti sul PC.

| Configurazione | Stato | Fitness | Precision | Media armonica | Fitness mescolata | Durata |
|---|---|---:|---:|---:|---:|---:|
| Heuristic 0,30 | Completata | 0,957796 | 0,174000 | 0,294500 | 0,960813 | 2 min 50 s |
| Heuristic 0,50 | Completata | 0,957796 | 0,174000 | 0,294500 | 0,960813 | 2 min 48 s |
| Heuristic 0,10 | Completata | 0,992856 | 0,143015 | 0,250017 | 0,978780 | 6 min 49 s |
| Inductive 0,00 | Completata | 1,000000 | 0,083982 | 0,154951 | 1,000000 | 31 min 06 s |
| Inductive 0,20 | Completata | 0,999858 | 0,083982 | 0,154949 | 0,999858 | 25 min 48 s |
| Inductive 0,10 | Completata | 0,999858 | 0,083982 | 0,154949 | 0,999858 | 26 min 13 s |
| Alpha classico | Completata | 0,003295 | 0,601504 | 0,006555 | 0,003531 | 0 min 50 s |

Heuristic 0,30 e 0,50 risultano primi a pari merito: fitness 0,957796, precision 0,174000 e media armonica 0,294500. Rispetto a Inductive 0,20 la media armonica cresce del 90,06% relativo; il valore assoluto resta circa 0,29. Il manifest indica 0,30 come primo perché incontra quella configurazione prima di 0,50: non è una superiorità misurata di una soglia sull'altra.

Il confronto dei PNML conferma che Heuristic 0,30 e 0,50 producono grafi marcati ed etichettati isomorfi, cioè la stessa struttura a meno dei nomi interni dei nodi. Lo stesso vale per Inductive 0,20 e 0,10. In questi intervalli cambiare soglia non ha prodotto un'alternativa strutturale.

Inductive 0,00 aumenta la complessità della rete: 52 posti e 65 transizioni, contro 36 e 41 del riferimento. La precision rimane identica e la media armonica migliora solo di circa 0,000002. Questa variazione non risolve la permissività osservata. Alpha rimane inadatto al log in questa configurazione, con fitness 0,003295 e nessun caso perfettamente riprodotto.

Tutti i PNML rappresentano le 12 etichette del log. I `NaN` nelle colonne “Etichette omesse” ed “Errore” della schermata provengono da campi CSV vuoti: i JSON riportano liste di etichette omesse vuote e stato `ok`, non errori mancanti da interpretare come fallimenti.

### 7.3 Sensibilità all'ordine e tracce complete

Per Heuristic 0,30 e 0,50 la fitness aggregata delle sequenze mescolate è leggermente maggiore di quella originale: 0,960813 contro 0,957796, con differenza di −0,003017. Tuttavia, i JSON aggiungono un dettaglio utile: le tracce perfettamente fitting passano da 2/20 sulle sequenze reali a 0/20 su quelle mescolate. Esiste quindi un segnale su questa misura più restrittiva, ma limitato a due casi e insufficiente a sostenere una buona capacità generale di distinguere l'ordine.

Heuristic 0,10 ha fitness originale 0,992856 e mescolata 0,978780, con differenza positiva di 0,014076. Le tracce fitting passano da 3/20 a 0/20. È il segnale aggregato più favorevole fra le configurazioni provate, ma la precision scende a 0,143015 e la media armonica a 0,250017. La scelta dipende quindi anche dall'obiettivo, non solo dalla posizione in classifica.

Inductive 0,00 mantiene fitness 1 e 20/20 tracce fitting anche con gli eventi mescolati. Le soglie 0,10 e 0,20 mantengono fitness 0,999858 e 19/20 in entrambi i log. Alpha ha 0/20 tracce fitting in entrambi. Il controllo usa una permutazione con seed 42: non è una distribuzione di risultati su molte permutazioni e non sostituisce anomalie reali annotate.

### 7.4 Tempi osservati e integrità degli artefatti

I processi dei sette candidati hanno impiegato complessivamente circa **1 ora e 36 minuti**, esclusi preparazione comune e backup fra i candidati. Inductive richiede circa 26–31 minuti per configurazione; Heuristic 0,30 e 0,50 circa 3 minuti; Heuristic 0,10 circa 7 minuti; Alpha circa 50 secondi. Sono tempi di questa esecuzione, non garanzie per altri runtime. Il riferimento Inductive ha terminato più velocemente dei 39 minuti e 30 secondi osservati nella vecchia valutazione: non attribuiamo causalmente la differenza a una sola modifica del codice o delle risorse.

La verifica locale ha superato 73 controlli su impronte, campione, metriche, formule, risultati individuali e strutture PNML. Il dataset canonico coincide con quello del secondo tentativo: 329.885 eventi, 322 casi, 12 zone. I 20 casi sono gli stessi e contengono 21.069 eventi; il CSV di valutazione corrisponde esattamente al campione di casi completi ricostruito con seed 42. Il riferimento Inductive 0,20 riproduce esattamente fitness e precision della precedente esportazione.

Le versioni registrate sono PM4Py 2.7.23.11, pandas 2.2.3 e NumPy 2.1.3. La verifica conferma la coerenza degli artefatti esportati, non costituisce un ricalcolo indipendente delle metriche di conformità. Il confronto resta in-sample: usare questi stessi casi per scegliere la soglia e dichiarare poi prestazioni su giorni nuovi sarebbe scorretto.

### 7.5 Dimensioni delle reti e copertura

| Configurazione | Posti | Transizioni totali | Transizioni silenti |
|---|---:|---:|---:|
| Inductive 0,20 | 36 | 41 | 29 |
| Inductive 0,00 | 52 | 65 | 53 |
| Inductive 0,10 | 36 | 41 | 29 |
| Heuristic 0,30 | 26 | 93 | 81 |
| Heuristic 0,50 | 26 | 93 | 81 |
| Heuristic 0,10 | 25 | 98 | 86 |
| Alpha classico | 9 | 12 | 0 |

Le transizioni silenti sono passaggi interni della rete senza un'etichetta di zona. La loro presenza non indica di per sé un errore; il loro numero contribuisce però alla complessità della rappresentazione e alla difficoltà di mostrarla. Il modello con più transizioni non è automaticamente migliore, e quello più piccolo non è automaticamente più fedele. Tutte le configurazioni nuove contengono le 12 etichette: tale copertura descrive la presenza delle zone, non la correttezza dei loro collegamenti né la capacità di riprodurre ogni caso.

## 8. Revisione della dashboard e del contesto per l'AI

La verifica ha riguardato anche il modo in cui i risultati vengono comunicati. Sono stati corretti quattro problemi:

| Problema riscontrato | Correzione applicata | Significato per la lettura |
|---|---|---|
| Fitness, precision e media armonica erano impilate. | Barre affiancate con scala 0–1. | Le metriche non vengono più sommate come componenti additive. |
| I conteggi erano descritti come attivazioni o attività. | Etichette riferite agli eventi compressi e alle zone. | Si evita di confondere frequenza degli eventi, presenza e durata. |
| Le fasce duravano 6, 6, 7 e 5 ore. | Confronto normalizzato per esposizione temporale, con totali consultabili. | I totali non sono interpretati automaticamente come intensità comparabili. |
| La rete completa aveva etichette troppo piccole. | DFG semplificato dei flussi principali affiancato alla rete. | Si rende leggibile la struttura prevalente senza eliminare il dettaglio. |

La normalizzazione usa l'esposizione di calendario entro i limiti temporali del log e tiene conto dei bordi parziali. Non corregge automaticamente i vuoti interni di acquisizione, come i nove giorni mancanti nel nuovo dataset, e non misura occupazione delle stanze.

Il DFG mostra transizioni osservate nel log: non è la rete di Petri del candidato selezionato e non ne certifica la qualità. La versione semplificata omette flussi meno frequenti. Gemini riceve un campione di casi completi entro un limite di 20.000 righe, insieme al contesto del modello selezionato e al DFG. Un campione non garantisce la rappresentatività dell'intero log: le risposte devono distinguere dati osservati e ipotesi interpretative.

Le schermate storiche negli audit rappresentano lo stato al momento della verifica. Il 27 ottobre 2026 è stata verificata anche la dashboard con i nuovi artefatti installati: selezione del modello, riepilogo delle metriche, parità fra i primi candidati e leggibilità del grafico comparativo.

### 8.1 Scelta dell'esperimento e del modello

Il confronto ricevuto è stato installato nella cartella `data/experiments/comparison_20261023T213310299553Z/`. Il dataset e le metriche rimangono associati ai modelli della medesima esecuzione. Questo permette di conservare pacchetti distinti e impedisce di presentare una rete insieme ai risultati appartenenti a un altro dataset.

Nella barra laterale sono disponibili due scelte. **Esperimento da caricare** seleziona il pacchetto di risultati e lo carica automaticamente. **Modello di processo** sceglie quale delle sette configurazioni mostrare. Sono presenti Alpha classico, le tre soglie Heuristic e le tre soglie Inductive. Il caricamento legge gli artefatti salvati: non ripete la discovery né la valutazione costosa.

Il modello selezionato compare nel titolo del riepilogo, nella rete di Petri e nelle metriche della configurazione. Il pannello comparativo continua a mostrare tutti i candidati dello stesso esperimento, in modo da conservare il contesto del confronto. La scelta della rete non cambia gli eventi del dataset né il DFG osservato: quei dati sono comuni ai sette candidati.

La selezione iniziale usa il primo candidato per media armonica presente nel pacchetto. Nel nuovo confronto viene proposto Heuristic 0,30, ma la dashboard indica esplicitamente **due configurazioni a pari merito**, includendo Heuristic 0,50. Non presenta la prima voce come una superiorità scientifica dimostrata sull'altra.

![Scelta del modello e metriche della configurazione nella dashboard](audit/dashboard_scelta_modelli.png)

La schermata mostra Heuristic 0,30 con fitness 0,9578, precision 0,1740 e media armonica 0,2945. I dati comuni sono 322 casi, 329.885 eventi e 12 zone. I valori a schermo sono arrotondati; i JSON conservano quelli completi.

### 8.2 Confronto e diagnostiche mostrate a schermo

La scheda **Confronto Metriche** include la tabella con stato, fitness, precision, media armonica, percentuali di tracce fitting originali e mescolate, fitness mescolata, differenza rispetto all'ordine originale, durata ed eventuali etichette omesse o errori. La tabella può essere scaricata in CSV.

Con sette configurazioni il grafico usa barre orizzontali affiancate, così i nomi delle soglie restano leggibili. La scala è fissata a 0–1 e fitness, precision e media armonica non vengono sommate. I campi vuoti relativi alle etichette omesse sono mostrati come “Nessuna”, evitando di scambiare un `NaN` di importazione CSV per un problema di discovery.

![Confronto delle metriche delle sette configurazioni nella dashboard](audit/dashboard_confronto_sette_modelli.png)

La rete di Petri completa rimane consultabile nella scheda dei modelli. Il DFG semplificato aiuta a leggere i flussi più frequenti del log, ma non sostituisce l'analisi delle reti né mostra tutti i comportamenti rari. Anche il numero di tracce perfettamente fitting deve essere letto accanto alla fitness aggregata, soprattutto per Heuristic, dove i due indicatori raccontano aspetti diversi.

### 8.3 Collegamento fra selezione e analista AI

Il contesto testuale passato alle azioni dell'analista identifica l'esperimento e la configurazione attivi. Include metriche selezionate, confronto degli altri candidati, diagnostiche disponibili, informazioni di valutazione e un riepilogo della rete con posti, transizioni, archi ed etichette. Il DFG viene presentato separatamente come struttura osservata nel log.

Al cambio di modello vengono azzerati conversazione e ultimo report, così una risposta precedente non appare riferita alla nuova configurazione. Al cambio di dataset vengono eliminati anche i riepiloghi derivati e i riferimenti al contesto CSV, che devono essere preparati nuovamente. Le impostazioni del servizio AI restano separate dalla scelta dell'algoritmo di process mining.

Questa integrazione rende coerente il materiale passato all'LLM, ma non garantisce che ogni risposta generata sia corretta. L'assistente riceve un riepilogo della rete e i flussi osservati, non l'intera semantica eseguibile della rete. Il cambio di selezione non addestra Gemini e non lo trasforma in un predittore validato del prossimo evento. I comandi relativi ad anomalie e prossime zone restano strumenti esplorativi da verificare.

### 8.4 Controlli applicativi eseguiti

Cinque test dedicati alla nuova gestione dei risultati sono stati completati con esito positivo. Verificano il caricamento coerente dei sette modelli, l'esclusione dei pacchetti incompleti dal catalogo, il rifiuto di un CSV con impronta discordante prima del caricamento del pickle, la corrispondenza del contesto AI alla configurazione selezionata e il cambio di modello nell'interfaccia.

Il test di interfaccia passa da Heuristic 0,30 a Inductive 0,00 e verifica l'aggiornamento della fitness a 1,0000 e della precision a 0,0840, oltre alla cancellazione di chat e report precedenti. Verifica anche che la scelta dell'upload manuale non lasci visibili i risultati del pacchetto appena abbandonato. Questi controlli sono eseguiti senza discovery e senza richieste reali ai servizi AI.

Il controllo nel browser ha confermato le sette opzioni del menu, il passaggio fra configurazioni, i valori mostrati e la leggibilità del grafico. I cinque test applicativi sono distinti dai 73 controlli di integrità del confronto Colab. Nessuno dei due gruppi dimostra generalizzazione su dati nuovi.

La revisione Gemini ha superato tutti i **30 test automatici** della suite. Le verifiche includono corrispondenza del CSV installato con il raw, preprocessing, notebook, campionamento, esportazione, gestione degli esperimenti, grafici e client Gemini con risposte simulate. I test del client non inviano richieste reali a Google. I test di discovery usano piccoli log sintetici; non è stata ripetuta la discovery del dataset completo. Questi controlli tecnici non dimostrano generalizzazione su nuovi dati.

### 8.5 File installati e uso del progetto

Il pacchetto è già installato sul PC. Per consultarlo basta avviare `avvia_dashboard.bat`, scegliere l'esperimento e poi il modello nella barra laterale. Non occorre riscaricare i file o rieseguire Colab. Il pulsante **Ricarica risultati** rilegge il pacchetto selezionato; **Upload manuale** permette di usare un altro insieme di CSV, PKL e metriche provenienti da una fonte fidata.

| Percorso nel progetto | Contenuto e funzione |
|---|---|
| `data/experiments/comparison_20261023T213310299553Z/data/` | CSV comune, modelli PKL, metriche e metadati del confronto installato. |
| Cartella padre del precedente percorso | Risultati dettagliati, manifest, tabella CSV e versioni del confronto. |
| `audit/colab_received_2026-10-27/` | Archivio estratto, inclusi log e PNML dei singoli candidati. |
| `dashboard_results.py` | Catalogo dei pacchetti, controlli di coerenza e riepilogo del modello selezionato. |
| `dashboard.py` e `dashboard_charts.py` | Interfaccia, selettori, reti, confronto e grafici. |
| `tests/test_dashboard_results.py` | Cinque verifiche dedicate alla gestione degli esperimenti e della selezione. |

La cartella principale `data/` conserva anche artefatti precedenti, ma al momento della verifica manca il suo CSV derivato: questo pacchetto incompleto non viene proposto nel menu. Il confronto installato ha invece il proprio CSV completo. Il riferimento Inductive 0,20 del secondo tentativo è rappresentato anche fra i sette candidati del nuovo pacchetto; il primo esperimento di quattro settimane resta documentato negli audit storici e non viene ricostruito artificialmente come pacchetto caricabile.

Per aggiungere in futuro un confronto, si estrae una nuova cartella in `data/experiments/`, mantenendo la sottocartella `data/` e i JSON di confronto nella cartella padre, senza sovrascrivere il pacchetto precedente. Modelli, CSV, metriche e metadati vanno trasferiti insieme: conservare metadati di un vecchio esperimento accanto a nuovi risultati renderebbe inaffidabile la tracciabilità.

## 9. Guida al sito e inserimento degli screenshot

Questo capitolo accompagna una dimostrazione del sito: avvio, scelta dei risultati, esplorazione del dataset, lettura delle reti, confronto delle metriche e consultazione dell'analista AI. Le schermate vanno inserite nei punti S1–S8 indicati sotto, subito dopo la spiegazione della funzione corrispondente. Gli spazi contrassegnati sono posizioni da completare, non immagini già acquisite.

Le due schermate già presenti nel capitolo 8 documentano l'integrazione tecnica. Qui si possono inserire screenshot nuovi, acquisiti con lo stesso esperimento per costruire una guida uniforme. Se si riutilizzano quelle immagini, mantenerne visibili periodo, configurazione e valori, evitando didascalie riferite a un altro modello.

### 9.1 Avvio e scelta dei risultati

Avviare `avvia_dashboard.bat` dalla cartella principale del progetto e aprire l'indirizzo locale indicato dal terminale. Nella barra laterale, sotto **Sorgente Dati**, scegliere **Esperimento da caricare**. Il pacchetto viene letto automaticamente. Nel menu **Modello di processo** scegliere una delle configurazioni disponibili, per esempio Heuristic 0,30.

Il nome selezionato appare nel riepilogo principale insieme a fitness, precision e F1. Il sito mostra anche il periodo del dataset, il numero di casi, gli eventi, le zone e le configurazioni prime a pari merito. Questi elementi consentono di verificare subito quale risultato si sta discutendo. Per osservare solo i dati e i modelli non occorre configurare Gemini.

**Screenshot S1 — Pagina iniziale e selezione del modello.** Lasciare aperta la barra laterale e inquadrare i due menu, il nome della configurazione e i tre valori principali. Usando Heuristic 0,30 si devono vedere circa 0,9578, 0,1740 e 0,2945. Se si vuole mostrare l'elenco delle alternative, acquisire una seconda immagine con il menu del modello aperto.

[SCREENSHOT S1]

**Didascalia proposta S1:** Scelta dell'esperimento e della configurazione Heuristic con soglia 0,30 e riepilogo delle metriche sul dataset di gennaio–marzo 2012.

### 9.2 Esplorazione degli eventi e delle distribuzioni

Aprire la scheda **Dati & Statistiche**. La tabella iniziale mostra un campione delle righe del log, con caso, zona e timestamp. Più in basso sono disponibili i conteggi per zona e per fascia oraria. Per confrontare fasce di durata diversa lasciare selezionata la misura **Eventi per ora di calendario**; la scelta **Eventi totali** mostra invece il volume complessivo.

La tabella dei denominatori si apre da **Come sono normalizzati i conteggi per fascia**. Consente di leggere le ore di calendario effettivamente considerate ai bordi del log. Non risolve i vuoti interni di acquisizione e non permette di stimare la permanenza nelle stanze.

**Screenshot S2 — Distribuzioni del dataset.** Inquadrare i grafici per zona e fascia, includendo il nome della misura selezionata e le unità degli assi. Se non entrano nella stessa immagine, inserirne due consecutive in questo punto. Non descriverli come grafici del tempo trascorso nelle zone.

[SCREENSHOT S2]

**Didascalia proposta S2:** Distribuzione degli eventi compressi per zona e confronto delle fasce orarie normalizzato per ora di calendario.

### 9.3 Lettura dei flussi osservati

Aprire la scheda **Modelli Petri Net**. La prima visualizzazione è il **DFG semplificato**: i nodi rappresentano zone e gli archi i passaggi consecutivi osservati entro i casi. I numeri sugli archi indicano le frequenze; la nota sotto il grafico precisa quanti flussi e quanta parte delle transizioni sono mostrati.

Il DFG dipende dal dataset caricato. Se si cambia soltanto configurazione nello stesso esperimento, il DFG rimane lo stesso perché descrive i dati comuni, non il modello scelto.

**Screenshot S3 — DFG semplificato.** Inquadrare il grafico con etichette leggibili, frequenze e nota di copertura. Non tagliare la nota che distingue i flussi del log dalla rete selezionata.

[SCREENSHOT S3]

**Didascalia proposta S3:** DFG dei flussi più frequenti osservati nel log con frequenze e copertura delle transizioni visualizzate.

### 9.4 Consultazione della rete di Petri selezionata

Nella stessa scheda scorrere fino a **Rete di Petri completa**. La visualizzazione corrisponde al modello scelto nella barra laterale. Il pulsante a schermo intero aiuta a leggere reti complesse; l'espansione **Dettaglio Petri Net** mostra numero di posti, transizioni e archi.

Per dimostrare il funzionamento del selettore si può passare da Heuristic 0,30 a Inductive 0,00: cambiano rete e metriche del modello, mentre conteggi del dataset e DFG restano comuni. La rete completa può diventare molto densa, quindi lo screenshot deve essere accompagnato dal nome della configurazione e non presentato come prova autonoma di qualità.

**Screenshot S4 — Rete di Petri.** Inserire una vista ingrandita della rete scelta e specificare il modello nella didascalia. Se il nome scompare nella modalità a schermo intero, riprenderlo dalla selezione verificata prima dell'ingrandimento. Per il confronto fra due modelli aggiungere una seconda immagine nello stesso punto con una didascalia distinta.

[SCREENSHOT S4]

**Didascalia proposta S4:** Rete di Petri prodotta da Heuristic Miner con soglia di dipendenza 0,30 sul log di gennaio–marzo 2012.

### 9.5 Confronto delle configurazioni e controllo dell'ordine

Aprire **Confronto Metriche**. La tabella riunisce i sette candidati dello stesso esperimento e li ordina per media armonica. Mostra anche stato della prova, fitness mescolata, differenza rispetto alle sequenze originali, percentuali di tracce perfettamente fitting e durata. Le colonne più a destra possono richiedere lo scorrimento orizzontale o l'apertura a schermo intero.

Per presentare il risultato bisogna mostrare sia il vantaggio di Heuristic 0,30 e 0,50 nella classifica sia la debole selettività rispetto all'ordine. Il pari merito non va interpretato come due miglioramenti indipendenti, dato che le reti di quelle due configurazioni sono strutturalmente equivalenti. Il pulsante **Scarica tabella del confronto** esporta le informazioni mostrate in un CSV.

**Screenshot S5 — Tabella con diagnostiche.** Inquadrare tutti i candidati e le colonne necessarie a confrontare fitness originale, fitness mescolata e tracce fitting. Se la tabella è troppo larga, inserire due immagini: la prima con le metriche principali, la seconda con le diagnostiche e i nomi dei modelli ancora visibili. Non ridurre tutto fino a rendere il testo illeggibile.

[SCREENSHOT S5]

**Didascalia proposta S5:** Confronto delle sette configurazioni e diagnostiche sulle sequenze originali e mescolate per gli stessi venti casi di valutazione.

Più in basso il grafico mostra fitness, precision e media armonica con barre separate e scala comune 0–1. Le barre orizzontali permettono di leggere i nomi delle sette configurazioni. Il modello scelto nella barra laterale rimane identificato, ma il grafico continua a confrontare l'intero esperimento.

**Screenshot S6 — Grafico comparativo.** Inquadrare tutte le sette configurazioni, l'asse 0–1 e la legenda delle tre metriche. Per questa figura è possibile riutilizzare la schermata del confronto già inserita nel capitolo 8.

[SCREENSHOT S6]

**Didascalia proposta S6:** Fitness, precision e media armonica delle sette configurazioni rappresentate separatamente su scala 0–1.

### 9.6 Configurazione dell'analista AI

Nella barra laterale aprire **Impostazioni connessione**, inserire una **API Key Gemini** valida e il nome del modello disponibile per il proprio account, quindi premere **Configura Gemini**. In alternativa, la chiave può essere fornita tramite la variabile di ambiente `GOOGLE_API_KEY`. La chiave digitata nella dashboard resta nella sessione e non viene salvata automaticamente in `config.json`.

Il messaggio “Configurato” indica l'inizializzazione del client. La connessione viene verificata alla prima richiesta: quel messaggio da solo non prova che sia già stata ottenuta una risposta. Nella scheda **Analista AI** si trovano chat, generazione del report, suggerimenti di possibili anomalie e prossima zona. Le funzioni AI non modificano le reti o le metriche salvate.

**Screenshot S7 — Impostazioni AI.** Mostrare la configurazione Gemini, il nome del modello e lo stato della configurazione. Tenere nascosta la chiave API e non includere credenziali nel documento. Se il servizio non è stato collegato, descrivere la schermata come configurazione da completare, non come analisi riuscita.

[SCREENSHOT S7]

**Didascalia proposta S7:** Configurazione del motore AI utilizzato nella dimostrazione con identificazione del servizio e del modello linguistico.

### 9.7 Esempio di consultazione e scaricamento del report

Prima della richiesta verificare il modello di processo attivo nella barra laterale. Nella chat inserire, per esempio: “Spiega i limiti del modello selezionato usando precision, fitness e risultato sulle sequenze mescolate”. Il sito invia a Gemini il contesto previsto e mostra la risposta. La funzione **Genera Report Completo** produce un report testuale; dopo una generazione riuscita compare il pulsante per scaricarlo in TXT.

La risposta deve essere letta accanto ai numeri originali, distinguendo osservazioni e ipotesi. Una risposta plausibile non sostituisce una verifica delle anomalie né una valutazione della previsione. Quando si cambia configurazione vengono cancellati chat e report precedenti per evitare di riferirli al nuovo modello.

**Screenshot S8 — Domanda e risposta reale dell'AI.** Inquadrare la domanda, una parte significativa della risposta e il modello di processo selezionato. Inserire questa immagine soltanto dopo una richiesta effettivamente riuscita; non sono stati generati esempi fittizi per completare la guida. Se si usa il report, mostrare anche il pulsante di download dopo la generazione e indicare nella didascalia il motore linguistico effettivamente usato.

[SCREENSHOT S8]

**Didascalia proposta S8:** Esempio di consultazione dell'analista AI sul modello di processo selezionato e discussione dei suoi risultati da verificare sui dati.

### 9.8 Come completare il capitolo in Word

Per ogni figura, selezionare soltanto la riga `[SCREENSHOT S...]` corrispondente e sostituirla tramite **Inserisci → Immagini → Questo dispositivo**. Mantenere l'immagine in linea con il testo, rispettare i margini e aggiornare la didascalia proposta in base a ciò che lo screenshot mostra davvero. Lo spazio bianco è predisposto per facilitare l'inserimento e può essere ridotto dopo aver aggiunto l'immagine.

Usare immagini nitide e coerenti per dimensione e stile. Se una funzione richiede più scatti, numerarli S2a/S2b oppure S5a/S5b e mantenere l'ordine della spiegazione. Non sostituire le figure sui risultati con screenshot di un altro dataset senza modificare anche il testo. Le figure S7 e S8 restano da completare con la configurazione e le risposte effettive della dimostrazione; non attestano prove di connessione AI già eseguite durante i test dell'interfaccia.

## 10. Registro sintetico del percorso

| Fase | Domanda | Intervento | Evidenza e stato |
|---|---|---|---|
| Primo log | Quale algoritmo rappresenta meglio quattro settimane? | Alpha, Heuristic 0,50, Inductive 0,20. | Completata: Inductive primo, ma precision bassa. |
| Audit della rappresentazione | Che cosa significano eventi, casi e grafici? | Verifica delle zone, degli stati, delle distribuzioni e del campione AI. | Completata per i controlli descritti; mappa fisica ancora da validare. |
| Passaggio a Colab | Come elaborare più dati con i limiti del PC? | Preprocessing streaming, discovery singola, export e backup. | Completato e utilizzato nel secondo esperimento. |
| Log più ampio | Più osservazioni migliorano Inductive? | Tre mesi, rumore 0,20, valutazione su 20 casi. | Completata: precision e media armonica inferiori al riferimento storico. |
| Diagnostica dell'ordine | La fitness alta riflette l'ordine osservato? | Permutazione entro gli stessi casi e nuovo replay. | Completata: sul secondo campione i valori restano identici. |
| Confronto controllato | Cambiare algoritmo o soglia migliora il compromesso? | Sette configurazioni, stesso log e stesso campione. | Completato: Heuristic 0,30 e 0,50 primi a pari merito; selettività ancora debole. |
| Integrazione nella dashboard | Come consultare le alternative senza confondere artefatti e risultati? | Catalogo degli esperimenti, scelta della configurazione, diagnostiche e contesto AI coerenti. | Completata: sette modelli disponibili, cinque test superati e verifica nel browser. |
| Validazione futura | Il risultato si mantiene su giorni nuovi? | Separazione temporale dei dati, dopo aver fissato le scelte. | Da progettare ed eseguire. |

## 11. Conclusioni del percorso sperimentale

Il progetto dispone di una pipeline completa, di esportazioni riproducibili e di un'interfaccia per esplorare i risultati. Il percorso ha anche prodotto evidenze negative utili: alta fitness non implica un modello selettivo e un dataset più ampio non ha portato automaticamente a risultati migliori.

Restano quattro limiti principali: significato delle etichette da validare, casi temporali lunghi e molto variabili, valutazione in-sample e copertura temporale incompleta. Il nuovo confronto affronta la scelta di algoritmo e parametro; non risolve da solo questi altri problemi.

Il confronto ha individuato un miglioramento concreto delle metriche cambiando algoritmo: Heuristic 0,30 e 0,50 sono i candidati di riferimento per il compromesso fitness/precision in questo esperimento. Il controllo negativo e la bassa precision impediscono però di presentarli come modelli già affidabili della routine o dell'anomalia domestica. Heuristic 0,10 rimane utile come alternativa da studiare per la maggiore differenza di fitness rispetto alle sequenze mescolate.

La priorità successiva è validare la mappa sensori e confrontare definizioni di evento e caso più significative, per esempio distinguendo gli stati dei sensori e costruendo episodi motivati dal problema applicativo. Queste alternative non sono ancora state valutate come pipeline complete. Prima di scegliere ulteriori soglie, occorre definire una separazione temporale fra dati usati per costruire i modelli, dati per scegliere le configurazioni e dati finali di test, evitando di spezzare lo stesso caso fra insiemi.

Il contributo del progetto è anche metodologico: abbiamo documentato un primo confronto debole, l'ampliamento del dataset senza miglioramento complessivo, una diagnosi della permissività, un'interruzione per risorse e una nuova esecuzione completata con migliori metriche. La conclusione è sostenuta da questo percorso, non dalla sola selezione del numero più alto.

### 11.1 Valutazione complessiva del lavoro

Come prototipo didattico e studio sperimentale, il lavoro ha una pipeline completa e una progressione motivata dalle evidenze. La nuova dashboard consente di discutere i risultati e i limiti senza nascondere le alternative meno riuscite. La solidità del progetto deriva anche dalla capacità di riconoscere che un modello funzionante e una metrica elevata non bastano per validare l'interpretazione comportamentale.

Come sistema già pronto per riconoscere routine o anomalie, il progetto non ha ancora evidenze sufficienti. La precision del candidato primo è circa 0,174, solo due dei venti casi sono perfettamente riprodotti e la fitness aggregata non peggiora dopo il mescolamento. Questi risultati consentono una discussione scientifica onesta, ma non una promessa di rilevazione affidabile.

Il miglioramento relativo del 90% non va presentato come “90% di accuratezza”: la media armonica passa da circa 0,155 a 0,2945. Né il nuovo Heuristic può essere dichiarato migliore del vecchio Inductive di novembre su un terreno comune: il confronto storico usa periodi e campioni diversi. Le conclusioni controllate riguardano le sette configurazioni sullo stesso log di gennaio–marzo.

### 11.2 Decisione attuale e sviluppi successivi

Per la dimostrazione viene proposto Heuristic 0,30, dichiarando il pari merito con 0,50 e mantenendo disponibili tutte le configurazioni. Heuristic 0,10 è un'alternativa da esaminare per l'obiettivo specifico di sensibilità all'ordine. La classifica per media armonica e tale obiettivo non sono equivalenti; non esiste ancora un vincitore validato per tutte le finalità.

Il prossimo ciclo di lavoro dovrebbe procedere in questo ordine:

1. Verificare provenienza del TXT, pianta e mappa dei sensori, quindi motivare il significato degli stati conservati e la gestione dei giorni mancanti.
2. Definire prima dell'esperimento un obiettivo misurabile e una separazione cronologica dei dati. Scegliere rappresentazione e soglie sui dati di sviluppo, lasciando il test finale fuori da quelle decisioni.
3. Confrontare il preprocessing attuale con alternative motivate, usando lo stesso protocollo per ogni candidato. La prova ON/OPEN finora eseguita misura soltanto la variazione dei conteggi, non il miglioramento di un modello.
4. Ripetere i controlli negativi su più permutazioni e riportare la variabilità delle misure. Se si vuole sostenere l'anomaly detection, acquisire esempi pertinenti di anomalie con una valutazione esplicita.
5. Aumentare eventualmente la finestra temporale dopo aver verificato che la rappresentazione sia significativa. Sei mesi erano stati discussi come possibile estensione, ma non sono stati usati negli esperimenti completati e non garantiscono un miglioramento.

Queste attività costituiscono il lavoro futuro. Non sono state avviate ulteriori discovery sul PC per aggiornare la documentazione e la nuova selezione della dashboard.

## 12. Tracciabilità e verifiche ancora aperte

L'archivio ricevuto è `comparison_20261023T213310299553Z-20261027T170514Z-1-001.zip`. I file sono conservati in `audit/colab_received_2026-10-27/`, separati dagli artefatti attivi della dashboard. La chiusura della sessione prima della cella finale non ha impedito il recupero dei backup salvati su Drive.

Il pacchetto include tabella, risultati dettagliati, manifest, metadati, log, CSV comune, modelli PKL e PNML. Il report di preprocessing non è incluso nella cartella del confronto: potrebbe trovarsi nella cartella padre del run su Drive. L'identità del log derivato è stata verificata tramite la sua impronta canonica; questo non sostituisce la documentazione della provenienza del TXT e delle esclusioni del preprocessing.

Restano aperte la verifica della mappa fisica dei sensori e la valutazione su giorni nuovi. La dashboard aggiornata è stata invece controllata nel browser dopo l'installazione dei sette candidati. La prima esecuzione interrotta per memoria è documentata dall'output fornito, ma il relativo archivio non è nel pacchetto ricevuto.

Il manifest e i JSON sono conservati con i rispettivi risultati. Per il confronto fra file si distingue l'impronta dei byte del CSV dall'impronta canonica delle tre colonne: differenze fra fine riga Windows e Linux non costituiscono da sole una modifica degli eventi. Il grafico della dashboard arrotonda i valori per leggibilità; l'analisi del pari merito e dei miglioramenti usa i valori completi.

La revisione del 27 ottobre conserva il racconto dei tentativi precedenti. Gli audit del 22 e del 23 ottobre rimangono evidenze storiche e non vanno letti come descrizioni della dashboard aggiornata. Le schermate inserite nelle sezioni precedenti rappresentano la versione con la nuova scelta di esperimento e modello.

## 13. Evidenze nel repository

- [Audit del primo dataset](audit/VALUTAZIONE_RISULTATI.md) e [diagnostica storica](audit/results_audit.json).
- [Confronto dopo il passaggio a Colab](audit/CONFRONTO_COLAB_2026-10-23.md) e [diagnostica del secondo dataset](audit/colab_comparison_2026-10-23.json).
- [Notebook del primo calcolo Colab](Aruba_Colab_Training.ipynb).
- [Notebook del confronto fra tre algoritmi](Aruba_Colab_Confronto_Modelli.ipynb).
- [Preprocessing ed esportazione Colab](colab_pipeline.py), [esecuzione del benchmark](colab_benchmark.py) e [valutazione della pipeline locale](evaluation.py).

- [Verifica del confronto ricevuto](audit/comparison_verification_2026-10-27.json) e [script di verifica](audit/verify_received_comparison.py).
- [Gestione degli esperimenti nella dashboard](dashboard_results.py) e [test della selezione dei risultati](tests/test_dashboard_results.py).
- [Schermata della selezione](audit/dashboard_scelta_modelli.png) e [schermata del confronto](audit/dashboard_confronto_sette_modelli.png).

I numeri storici derivano dagli audit conservati e dall'output Colab fornito. I risultati del terzo tentativo derivano dai JSON e dai PNML ricevuti il 27 ottobre 2026. Le conclusioni distinguono metriche esportate, controlli di integrità locali e verifiche scientifiche ancora da svolgere.
