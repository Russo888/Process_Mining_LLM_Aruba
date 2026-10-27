# Confronto dei nuovi risultati Colab — 23 ottobre 2026

## Esito

Non emerge un miglioramento complessivo nella qualità del modello di processo. Sono aumentati la copertura degli eventi e il numero di tracce perfettamente riprodotte, ma il modello è ancora più permissivo rispetto al precedente: la precision e la media armonica sono inferiori. La comparazione non è un benchmark controllato: periodi e campioni di valutazione sono diversi.

## Nuovo dataset

- Dal 1 gennaio 2012 alle 08:00:09 al 31 marzo 2012 alle 06:44:37 nel CSV derivato.
- 329.885 eventi, 322 casi, 12 zone; prima 65.783 eventi e 109 casi.
- 82 giorni con eventi sui 91 giorni di calendario della finestra.
- Nessun evento dal 20 al 28 marzo 2012 inclusi. Anche il raw locale non contiene righe per queste nove date: il vuoto è già nell'ingresso, non soltanto nel CSV derivato.
- CSV ordinato, nessun valore nullo nelle tre colonne PM4Py.
- Mediana di 884 eventi per caso, media di 1.024,5 e massimo di 4.759; 320 varianti in 322 casi. I casi restano molto lunghi e quasi tutti diversi.
- Il file raw mantiene il vecchio nome riferito a novembre 2011, ma il suo contenuto ora copre gennaio–marzo 2012. Questo nome non descrive più correttamente il contenuto.

## Confronto Inductive Miner

| Metrica | Precedente | Nuovo |
|---|---:|---:|
| Fitness token-based | 0,997812 | 0,999858 |
| Precision token-based | 0,154879 | 0,083982 |
| Media armonica fitness/precision | 0,268138 | 0,154949 |
| Tracce perfettamente fitting | 5/50 (10%) | 19/20 (95%) |
| Etichette visibili rappresentate | 10/12 | 12/12 |

La precision scende di circa il 45,8%; la media armonica del 42,2%. La fitness aggregata cresce di circa 0,00205. Il miglioramento della copertura è reale: le due etichette di uscita, prima assenti dalla rete, ora sono presenti. La maggiore percentuale di tracce fitting non dimostra però un migliore apprendimento dell'ordine degli eventi.

Il modello nuovo ha 36 posti, 41 transizioni, di cui 29 silenti, e 104 archi. L'albero di processo ricostruito presenta un operatore parallelo alla radice, con rami di zone ripetibili e rami opzionali. La struttura consente moltissimi ordinamenti degli stessi eventi.

## Controllo negativo sul medesimo campione nuovo

Ho ricalcolato il token replay sui 20 casi indicati nei metadati, ottenendo esattamente la fitness salvata. Ho poi permutato le etichette delle zone entro ciascuno degli stessi casi con seed 42, mantenendo casi, timestamp e frequenze.

| Log | Fitness aggregata | Tracce fitting |
|---|---:|---:|
| Sequenze osservate | 0,9998583842 | 95% |
| Sequenze permutate | 0,9998583842 | 95% |

Anche la fitness media per traccia è identica. Su questo controllo il replay non distingue l'ordine reale da quello mescolato. È una diagnosi della scarsa selettività rispetto all'ordine, non un test completo di tutte le possibili anomalie.

## Coerenza degli artefatti

- Il digest delle metriche coincide con quello nei metadati.
- Il digest del dataset coincide ricostruendo il CSV con fine riga LF, come su Colab. La prima differenza apparente dipendeva soltanto dai fine riga Windows/Colab.
- Tutti i 20 casi di valutazione sono presenti; contengono 21.069 eventi, come dichiarato nei metadati.
- Il totale dei casi coincide: 322.
- Versione PM4Py locale e Colab: 2.7.23.11.
- La fitness salvata coincide con quella ricalcolata usando il nuovo pickle e il nuovo CSV. La precision riportata è quella esportata da Colab; non è stata ricalcolata in questo audit.

## Limiti del confronto e prossimo passo

Il modello precedente era valutato su 50 casi di novembre 2011; quello nuovo su 20 casi di gennaio–marzo 2012. Entrambe le valutazioni sono in-sample. Non si può attribuire causalmente il cambiamento alla sola durata del dataset o concludere quale modello generalizzi meglio senza un test comune.

Non consiglierei di allargare ancora il periodo con la stessa rappresentazione per inseguire fitness più alta. La priorità rimane validare mappa ed eventi, valutare una rappresentazione per episodi/attività più significativa e separare cronologicamente training, validazione e test. Soglie o algoritmi diversi vanno confrontati sullo stesso protocollo, includendo il controllo sulle sequenze permutate.

Questo audit non modifica modelli, CSV, metriche o metadati. Lo script `compare_colab_results.py` e il file `colab_comparison_2026-10-23.json` conservano la diagnostica riproducibile. Il riferimento precedente proviene dall'audit del 22 ottobre, non dal vecchio checkout annidato.
