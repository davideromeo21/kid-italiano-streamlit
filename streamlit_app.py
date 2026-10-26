import streamlit as st
from kid_core import parse_isins, resolve, make_zip

st.set_page_config(page_title='KID Italiano', page_icon='📄', layout='centered')
st.markdown('''<style>
.stApp{background:#f7f8f3}h1,h2,h3{color:#163d34}textarea{font-family:monospace!important}
.block-container{max-width:900px;padding-top:2.5rem}div[data-testid="stMetric"]{background:white;border:1px solid #e3e8e1;border-radius:12px;padding:16px}
@media(max-width:640px){.block-container{padding:1.5rem 1rem}h1{font-size:2rem!important}}
</style>''', unsafe_allow_html=True)
st.caption('DOCUMENTI DI INVESTIMENTO · ITALIANO')
st.title('I tuoi KID, in un posto.')
st.write('Incolla gli ISIN e scarica i documenti italiani, singolarmente o in un unico ZIP.')
st.info('Ricerca diretta nei cataloghi ETF. Copertura parziale per fondi e certificati. “Più recente” significa tra i documenti trovati e datati; l’ultima versione dell’emittente non è garantita.')

if 'input' not in st.session_state:
    st.session_state.input = ''
if st.button('Prova un esempio'):
    st.session_state.input = 'IE00B4L5Y983\nIE00B3XXRP09\nLU0290358497'
text = st.text_area('Un ISIN per riga, oppure separati da virgole', key='input', height=160, placeholder='IE00B4L5Y983')
upload = st.file_uploader('Oppure importa un elenco TXT / CSV', type=['txt', 'csv'])
with st.expander('Hai già un URL dell’emittente?'):
    st.caption('Una riga per documento: ISIN;https://pagina-prodotto-o-PDF')
    sources = st.text_area('Fonti aggiuntive', height=90)

if st.button('Cerca i KID in italiano', type='primary', use_container_width=True):
    if upload:
        if upload.size > 100_000:
            st.error('Usa un elenco inferiore a 100 KB.'); st.stop()
        try:
            text += '\n' + upload.getvalue().decode('utf-8-sig')
        except UnicodeDecodeError:
            st.error('Il file deve essere in formato UTF-8.'); st.stop()
    isins = parse_isins(text)
    if not isins or len(isins) > 20:
        st.error('Inserisci da 1 a 20 ISIN per ricerca.'); st.stop()
    mapping = {}
    for line in sources.splitlines():
        parts = line.split(';', 1)
        if len(parts) == 2:
            mapping[parts[0].strip().upper()] = parts[1].strip()
    st.session_state.results = []
    progress, status = st.progress(0), st.empty()
    for i, isin in enumerate(isins):
        status.write(f'Ricerca {i+1}/{len(isins)} · {isin}')
        try:
            result = resolve(isin, mapping.get(isin, ''))
        except Exception as exc:
            result = {'isin': isin, 'stato': 'Errore di recupero', 'note': str(exc)[:250], 'pdf': None, 'diagnostica': []}
        st.session_state.results.append(result)
        progress.progress((i+1)/len(isins))
    status.success('Ricerca completata. Controlla le fonti e scarica i documenti.')

results = st.session_state.get('results', [])
if results:
    st.subheader('La tua raccolta')
    st.metric('KID italiani verificati', f"{sum(bool(r.get('pdf')) for r in results)} / {len(results)}")
    st.download_button('Scarica ZIP e report', make_zip(results), file_name='KID_Italiani.zip', mime='application/zip', use_container_width=True, type='primary')
    for result in results:
        with st.container(border=True):
            st.markdown(f"**{result['isin']}**")
            st.write(result['stato'])
            if result.get('data_documento'):
                st.caption('Data documento: ' + result['data_documento'])
            st.caption(result['note'])
            if result.get('pdf'):
                st.download_button('Scarica PDF', result['pdf'], file_name=result['isin']+'_KID_IT.pdf', mime='application/pdf', key='pdf_'+result['isin'], use_container_width=True)
                st.link_button('Apri la fonte', result['fonte'])
            with st.expander('Dettaglio delle fonti'):
                for item in result.get('diagnostica', []):
                    st.text(item['fonte'])
                    st.caption(item['esito'])

st.divider()
with st.expander('Limiti e privacy'):
    st.write('Gli ISIN vengono comunicati ai cataloghi documentali e, se necessario, ai motori di ricerca. I risultati sono tenuti nella sessione, senza archivio permanente dei documenti. Non caricare nomi, dati cliente o informazioni personali nel campo ISIN. I blocchi dei siti, i PDF scansionati e i documenti non indicizzati possono impedire il recupero. Le fonti possono essere distributori. Verifica fonte e classe del prodotto prima di usare il documento. Non vengono sostituiti KID italiani con documenti inglesi.')
st.caption('KID Italiano · Versione Streamlit · Cataloghi diretti')
