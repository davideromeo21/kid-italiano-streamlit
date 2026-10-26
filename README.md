# KID Italiano — Streamlit

App mobile-friendly per cercare KID italiani da una lista di ISIN e scaricare PDF e report in ZIP. Include la ricerca diretta nei cataloghi documentali della versione web corretta, senza dipendere esclusivamente dai motori di ricerca. Nessuna API key richiesta.

## Pubblicazione su Streamlit Community Cloud

1. Inserisci tutti i file di questa cartella nella radice di un repository GitHub, mantenendo `.streamlit/config.toml`.
2. Accedi a https://share.streamlit.io/ e collega GitHub.
3. Seleziona **Create app → Yup, I have an app**.
4. Scegli repository e branch. **Main file path: `streamlit_app.py`**.
5. In Advanced settings, scegli **Python 3.12**. Non servono secrets.
6. Premi **Deploy**. Il servizio assegnerà un URL `*.streamlit.app`.
7. Per condividerla pubblicamente, verifica la visibilità nelle impostazioni dell'app. Il codice può stare in un repository privato se l'account Streamlit ha accesso.

Documentazione ufficiale: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

## Avvio locale

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

## Controlli

ISIN con cifra di controllo valida; PDF leggibile fino a 12 pagine; ISIN nel testo; titolo e sezioni del KID in italiano; data da etichette di revisione/produzione, mai dalla scadenza del prodotto. I KID senza data sono segnalati. Il report conserva fonte, data e momento di recupero.

La copertura è maggiore per ETF. Fondi e certificati possono richiedere un URL aggiuntivo. Non è certificata l'ultima versione in assoluto, né l'autenticità di ogni fonte. CAPTCHA, blocchi del provider, scansioni e prodotti senza KID pubblico possono impedire il download. L'hosting Streamlit potrebbe ricevere blocchi diversi da quelli dei test locali.

I risultati e i documenti rimangono in memoria nella sessione; non vengono scritti su disco o conservati in un database. L'app non contiene dati cliente o credenziali. Massimo 20 ISIN per esecuzione, documenti fino a 6 MB e download con timeout. I PDF originali non sono inclusi nel repository.

## Test

```sh
python -m unittest -v test_kid
python test_live.py
```

`test_live.py` richiede Internet e verifica tre ETF di emittenti diversi. Può fallire se una fonte esterna blocca il recupero; il dettaglio delle fonti viene mostrato.

## Verifica del pacchetto — 26 ottobre 2026

Sei test locali superati per ISIN, date, selezione dei link, URL pubblici, gestione errori e ZIP. Verificata con Streamlit AppTest l'apertura, il pulsante esempio e il risultato per ISIN non valido. I test di download reali di questa versione Python non sono conclusivi: nell'ambiente di preparazione la risoluzione DNS esterna è bloccata. È necessario ripeterli dopo il deploy su Streamlit; la precedente versione web aveva recuperato i tre ETF di esempio.
