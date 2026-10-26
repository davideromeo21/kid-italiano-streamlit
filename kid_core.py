"""Ricerca KID italiani da cataloghi pubblici, senza API a pagamento."""
from __future__ import annotations
import csv
import io
import ipaddress
import re
import socket
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from urllib.parse import urljoin, urlsplit, parse_qs, quote

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

MAX_BYTES = 6_000_000
MONTHS = {name: i + 1 for i, name in enumerate('gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre'.split())}
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; KIDItaliano/2.0)', 'Accept-Language': 'it-IT,it;q=0.9,en;q=0.5', 'Cache-Control': 'no-cache'}


def valid_isin(value: str) -> bool:
    if not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}\d', value):
        return False
    digits = ''.join(str(ord(c) - 55) if c.isalpha() else c for c in value)
    return sum((int(c) * 2 // 10 + int(c) * 2 % 10) if i % 2 else int(c)
               for i, c in enumerate(digits[::-1])) % 10 == 0


def parse_isins(text: str) -> list[str]:
    return list(dict.fromkeys(v.strip('"\ufeff') for v in re.split(r'[\s,;]+', text.upper().strip()) if v.strip('"\ufeff') and v != 'ISIN'))


def public_url(url: str, check_dns: bool = True) -> str:
    p = urlsplit(url)
    if len(url) > 3000 or p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Usa un URL HTTPS pubblico')
    if not p.hostname or not re.fullmatch(r'[a-z0-9.-]+\.[a-z]{2,}', p.hostname, re.I):
        raise ValueError('Dominio non consentito')
    if p.hostname.endswith(('.local', '.localhost', '.internal', '.test')):
        raise ValueError('Indirizzo non pubblico')
    if check_dns:
        addresses = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError('Indirizzo non pubblico')
    return url


def download(url: str) -> tuple[bytes, str]:
    started = time.monotonic()
    for _ in range(5):
        public_url(url)
        with requests.get(url, headers=HEADERS, timeout=(8, 15), stream=True, allow_redirects=False) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers['Location'])
                continue
            response.raise_for_status()
            chunks, length = [], 0
            for chunk in response.iter_content(65536):
                length += len(chunk)
                if length > MAX_BYTES:
                    raise ValueError('Risposta oltre 6 MB')
                if time.monotonic() - started > 30:
                    raise TimeoutError('Tempo massimo di download superato')
                chunks.append(chunk)
            return b''.join(chunks), url
    raise ValueError('Troppi reindirizzamenti')


def kid_links(html: str, base: str) -> list[str]:
    links = []
    for a in BeautifulSoup(html, 'html.parser').select('a[href]'):
        url = urljoin(base, a['href'])
        label = a.get_text(' ', strip=True) + ' ' + a.get('title', '') + ' ' + url
        if not re.search(r'\bk[il]?id\b|priips?|informazioni chiave|PRP_', label, re.I):
            continue
        if re.search(r'(?:PRP|KID)_[A-Z]{2}_(?:en|de|fr|es)_', url, re.I):
            continue
        try:
            public_url(url, check_dns=False)
        except ValueError:
            continue
        score = (10 if re.search(r'KID\s*\(IT\)|PRP_IT_it|priipskid_it|[-_]it\.pdf|italiano', label, re.I) else 0) + (3 if '.pdf' in url else 0)
        links.append((score, url))
    return list(dict.fromkeys(url for _, url in sorted(links, key=lambda p: -p[0])))[:8]


def document_date(text: str) -> str:
    low = re.sub(r'\s+', ' ', text.lower())
    labels = r"(?:data (?:di |del )?(?:produzione|redazione|revisione|aggiornamento|pubblicazione|realizzazione|documento)|(?:prodotto|redatto|aggiornato|rivisto) (?:il|al|in data)|(?:è|e') datato|informazioni.{0,25}(?:aggiornate|corrette) al|informazioni.{0,35}precise a far data il)"
    dates = []
    for match in re.finditer(labels, low):
        fragment = low[match.end():match.end() + 85]
        numeric = re.search(r'\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b', fragment)
        named = re.search(r'\b(\d{1,2})\s+(' + '|'.join(MONTHS) + r')\s+(20\d{2})\b', fragment)
        iso = re.search(r'\b20\d{2}-\d{2}-\d{2}\b', fragment)
        try:
            if numeric:
                d, m, y = map(int, numeric.groups()); value = date(y, m, d)
            elif named:
                d, m, y = named.groups(); value = date(int(y), MONTHS[m], int(d))
            elif iso:
                value = date.fromisoformat(iso[0])
            else:
                continue
            if value <= date.today():
                dates.append(value.isoformat())
        except ValueError:
            continue
    return max(dates, default='')


def validate_pdf(data: bytes, isin: str) -> tuple[str, int]:
    if not data.startswith(b'%PDF-'):
        raise ValueError('La fonte non restituisce un PDF')
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 12:
        raise ValueError('PDF protetto o oltre 12 pagine')
    text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    if isin not in re.sub(r'\s+', '', text.upper()):
        raise ValueError('ISIN non presente nel PDF')
    low = re.sub(r'\s+', ' ', text.lower())
    if not re.search(r'documento contenente (?:le )?informazioni chiave', low):
        raise ValueError('Titolo KID italiano non riconosciuto')
    if sum(x in low for x in ['scopo', 'quali sono i rischi', 'quali sono i costi', 'per quanto tempo']) < 2:
        raise ValueError('Struttura italiana non confermata')
    return document_date(low), len(reader.pages)


def catalog(url: str) -> tuple[list[str], dict]:
    try:
        data, final = download(url)
        links = kid_links(data.decode('utf-8', errors='replace'), final)
        return links, {'fonte': url, 'esito': f'{len(links)} collegamenti KID individuati'}
    except Exception as exc:
        return [], {'fonte': url, 'esito': str(exc)[:250]}


def web_fallback(isin: str, diagnostics: list) -> list[str]:
    query = quote(f'"{isin}" KID italiano pdf')
    urls = [f'https://www.google.com/search?q={query}', f'https://html.duckduckgo.com/html/?q={query}']
    results = []
    for url in urls:
        try:
            data, final = download(url)
            links = []
            for a in BeautifulSoup(data, 'html.parser').select('a[href]'):
                href = urljoin(final, a['href'])
                parts = urlsplit(href); params = parse_qs(parts.query)
                if parts.hostname and 'duckduckgo.com' in parts.hostname:
                    href = params.get('uddg', [''])[0]
                elif parts.hostname and 'google.com' in parts.hostname:
                    href = params.get('q', params.get('url', ['']))[0]
                try:
                    public_url(href, check_dns=False)
                except ValueError:
                    continue
                if isin in href.upper() or '.pdf' in href.lower():
                    links.append(href)
            results.extend(links)
            diagnostics.append({'fonte': url, 'esito': f'{len(links)} risultati utilizzabili'})
        except Exception as exc:
            diagnostics.append({'fonte': url, 'esito': str(exc)[:250]})
    return list(dict.fromkeys(results))[:6]


def resolve(isin: str, source: str = '') -> dict:
    result = {'isin': isin, 'stato': '', 'data_documento': '', 'fonte': '', 'controllato_utc': datetime.now(timezone.utc).isoformat(), 'note': '', 'diagnostica': [], 'pdf': None}
    if not valid_isin(isin):
        result.update(stato='ISIN non valido', note='Controlla formato e cifra di controllo.')
        return result
    started = time.monotonic()
    diagnostics = result['diagnostica']
    urls = [f'https://www.justetf.com/it/etf-profile.html?isin={isin}', f'https://rebalix.com/it/etf/{isin}']
    candidates = [source] if source else []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for links, diagnostic in pool.map(catalog, urls):
            candidates.extend(links); diagnostics.append(diagnostic)
    seen, best, count, undated = set(), None, 0, False

    def examine(queue):
        nonlocal best, count, undated
        attempts = 0
        while queue and attempts < 8 and time.monotonic() - started < 100:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url); attempts += 1
            try:
                data, final = download(url)
                if not data.startswith(b'%PDF-'):
                    links = kid_links(data.decode('utf-8', errors='replace'), final)
                    queue[:0] = [link for link in links if link not in seen]
                    diagnostics.append({'fonte': final, 'esito': f'Pagina HTML: {len(links)} collegamenti KID'})
                    continue
                dt, pages = validate_pdf(data, isin)
                count += 1; undated = undated or not dt
                diagnostics.append({'fonte': final, 'esito': f'PDF verificato: {pages} pagine, data {dt or "da verificare"}'})
                if best is None or dt > best[0]:
                    best = (dt, final, data)
            except Exception as exc:
                diagnostics.append({'fonte': url, 'esito': str(exc)[:250]})
    examine(list(dict.fromkeys(candidates)))
    if not best and time.monotonic() - started < 65:
        examine(web_fallback(isin, diagnostics))
    if best:
        dt, final, data = best
        result.update(stato='KID trovato · data da verificare' if undated else 'KID italiano verificato', data_documento=dt, fonte=final, pdf=data,
                      note=f'{count} PDF verificati. Selezionata la data più recente riconosciuta tra quelli trovati. ' + ('Almeno un documento è privo di data riconoscibile: confronto non conclusivo. ' if undated else '') + 'Ultima versione assoluta non certificata.')
    else:
        result.update(stato='Recupero non riuscito', note='Nessun KID italiano verificabile dalle fonti raggiunte. Non significa che il documento non esista. Prova un URL emittente e controlla il dettaglio delle fonti.')
    return result


def make_zip(results: list[dict]) -> bytes:
    output, report = io.BytesIO(), io.StringIO()
    fields = ['isin', 'stato', 'data_documento', 'fonte', 'controllato_utc', 'note']
    writer = csv.DictWriter(report, fieldnames=fields, delimiter=';'); writer.writeheader()
    for result in results:
        row = {key: str(result.get(key, '')) for key in fields}
        writer.writerow({key: "'" + value if value.startswith(('=', '+', '-', '@')) else value for key, value in row.items()})
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('report.csv', report.getvalue().encode('utf-8-sig'))
        for result in results:
            if result.get('pdf'):
                archive.writestr(f"{result['isin']}_KID_IT_{result['data_documento'] or 'data_da_verificare'}.pdf", result['pdf'])
    return output.getvalue()
