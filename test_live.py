from kid_core import resolve, validate_pdf, make_zip
import io,zipfile
if __name__=='__main__':
    results=[]
    for isin in ['IE00B4L5Y983','IE00B3XXRP09','LU0290358497']:
        r=resolve(isin);results.append(r)
        print(isin,r['stato'],r['data_documento'],r['fonte'],len(r['pdf'] or b''),flush=True)
        if not r['pdf']: print(r['diagnostica'],flush=True)
    successes=[r for r in results if r['pdf']]
    for r in successes: validate_pdf(r['pdf'],r['isin'])
    with zipfile.ZipFile(io.BytesIO(make_zip(results))) as z:
        assert len(z.namelist())==len(successes)+1
    print(f'{len(successes)}/{len(results)} PDF recuperati e verificati; ZIP verificato.',flush=True)
    if len(successes)!=len(results): raise SystemExit(1)
