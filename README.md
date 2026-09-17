# 🏠 CASAS Aruba – Process Mining & LLM Analysis

Questo progetto combina il **Process Mining** con i modelli di **Intelligenza Artificiale (LLM)** per analizzare i comportamenti umani all'interno di una Smart Home (dataset CASAS Aruba).

![Dashboard Screenshot](https://raw.githubusercontent.com/Russo888/Process_Mining_LLM_Aruba/master/README_assets/dashboard.png) *(Inserire screenshot)*

## 🚀 Installazione Rapida (Windows)

Per chiunque scarichi il progetto, non è necessario configurare nulla a mano!

1. Clona o scarica questa repository.
2. Fai **doppio clic** sul file `setup_and_run.bat`.
3. Lo script farà tutto in automatico:
   - Creerà un ambiente virtuale isolato (`.venv_new`).
   - Installerà tutte le librerie necessarie da `requirements.txt`.
   - Avvierà automaticamente la dashboard nel tuo browser.

*(Per i successivi riavvii, basterà cliccare di nuovo su `setup_and_run.bat` oppure su `avvia_dashboard.bat`).*

---

## 📊 Report Dettagliato del Progetto

### 1. Il Dataset
Il progetto utilizza il celebre dataset **CASAS Aruba**, che raccoglie log generati da sensori di movimento e porte in una vera abitazione per diversi mesi. 
Il modulo `preprocessing.py`:
- Estrae i dati dai sensori (motion `M` e door `D`).
- Mappa i sensori in attività domestiche umane reali (es. *Camera_Letto*, *Cucina_Prep*, *Soggiorno*).
- Comprime i log rimuovendo duplicati consecutivi e organizza le tracce in "casi" basati sulla giornata e sulla fascia oraria (Mattina, Pomeriggio, Sera, Notte).

### 2. Algoritmi di Process Discovery
Tramite `pm4py`, l'event log viene analizzato con tre differenti approcci di Process Mining per estrarre il modello del processo domestico (Petri Net):
1. **Alpha Miner**: Molto preciso ma soffre nel gestire loop o percorsi paralleli complessi (tipici dei movimenti umani in casa).
2. **Heuristic Miner**: Tiene conto delle frequenze, ma in questo specifico dataset non raggiunge ottimi risultati.
3. **Inductive Miner 🏆 (Miglior Modello)**: L'algoritmo che si è dimostrato più robusto. Riesce a riprodurre quasi il 100% delle tracce reali dell'utente, anche se a discapito di una precisione minore (tende a sovra-generalizzare permettendo varianti non previste).

**Metriche calcolate sui log (Novembre 2011):**
* Eventi analizzati: ~65.700
* Fitness dell'Inductive Miner: **0.998**
* Precision dell'Alpha Miner: **0.785**

### 3. Integrazione AI (Gemini / Ollama)
La dashboard include un tab **"🤖 Analista AI"**. Il codice passa al modello linguistico (LLM) il grafo del processo estratto (DFG - Direct Follows Graph) e le metriche calcolate. 
L'LLM è in grado di:
- **Generare Report**: Scrivere riassunti esecutivi e trovare insight (es. orari di picco).
- **Rilevare Anomalie**: Evidenziare colli di bottiglia o pattern inusuali nella routine domestica.
- **Predittore**: Dato un percorso parziale (es. `Camera -> Corridoio`), l'AI usa la struttura del processo per prevedere la probabile destinazione successiva.

---

## ⚙️ Requisiti Manuali
Se non si vuole usare lo script automatico:
- `Python 3.10+`
- Creare il venv: `python -m venv .venv_new`
- Installare requisiti: `pip install -r requirements.txt`
- Avviare: `streamlit run dashboard.py`

## 🔑 Configurazione AI
L'AI supporta sia **Google Gemini** (Cloud) che **Ollama** (Locale).
Nel file `config.json` puoi inserire la tua `google_api_key`. In alternativa, puoi inserirla direttamente dalla barra laterale della dashboard una volta avviata.
