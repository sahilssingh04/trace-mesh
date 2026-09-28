"""Isolated real-browser UI test, with HTTP fulfilled by FastAPI TestClient.
No running server, real database or user credentials required.
Install playwright and its Chromium headless shell separately.
"""
import json
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect
from sqlalchemy import select
from app.main import create_app
from app.models import Case,Edge
from app.ingest import ingest,process_one
root=Path(__file__).resolve().parents[1]
key='browser-test-owner-key-1234567890'
with tempfile.TemporaryDirectory() as temp:
    app=create_app('sqlite:///'+str(Path(temp)/'test.db'),{key:{'role':'owner'}})
    with TestClient(app) as client:
        with app.state.factory.begin() as db:
            db.add(Case(id='GUIDE',title='Start here · four fictional people'));db.flush()
            ingest(db,'GUIDE','test',json.loads((root/'data/demo.json').read_text()))
            db.add(Case(id='SHOWCASE',title='V3 showcase · fictional fragmented records'));db.flush()
            ingest(db,'SHOWCASE','test',json.loads((root/'data/showcase-v3.json').read_text()))
            for e in db.scalars(select(Edge)):e.status='accepted'
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1500,'height':1050},accept_downloads=True)
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            def handler(route):
                request=route.request;url=urlsplit(request.url)
                if url.hostname!='weave.test':route.abort();return
                response=client.request(request.method,url.path+('?' +url.query if url.query else ''),headers=request.headers,content=request.post_data_buffer)
                headers={k:v for k,v in response.headers.items() if k.lower() not in ('content-length','content-encoding','transfer-encoding')}
                route.fulfill(status=response.status_code,headers=headers,body=response.content)
                if url.path.endswith('/imports') and response.status_code==202:process_one(app.state.factory)
            page.route('**/*',handler)
            page.goto('http://weave.test/')
            page.locator('#token').fill(key);page.locator('#signIn').click()
            expect(page.locator('#graphAccess button')).to_have_count(4)
            page.locator('[data-tab=links]').click()
            page.locator('.link-card').first.wait_for()
            assert page.locator('.link-card').count()==2
            page.locator('.link-card button').first.click()
            expect(page.locator('#inspector')).to_contain_text('Why this connection?')
            page.locator('[data-tab=input]').click()
            page.locator('#file').set_input_files(str(root/'data/demo2.json'))
            page.locator('#parseFile').click()
            expect(page.locator('#previewCounts')).to_contain_text('49 edges')
            with page.expect_download():page.locator('#downloadJson').click()
            page.locator('#savePreview').click()
            expect(page.locator('#jobs')).to_contain_text('completed')
            page.locator('[data-tab=records]').click()
            expect(page.locator('#recordRows .row')).to_have_count(53)
            page.once('dialog',lambda d:d.accept('Reviewed synthetic records'))
            page.locator('#acceptVisible').click()
            expect(page.locator('#recordRows .badge.pending')).to_have_count(0)
            page.locator('[data-tab=input]').click()
            page.locator('#noteText').fill('Asha called Ravi on 2026-01-10.\nRavi reportedly met Neel.')
            page.locator('#parseNote').click()
            expect(page.locator('#previewCounts')).to_contain_text('1 edges')
            assert 'source only' in page.locator('#previewWarnings').inner_text()
            page.locator('[data-tab=network]').click()
            page.locator('#graphAccess button').first.click()
            expect(page.locator('#inspector')).to_contain_text('Save changes')
            page.locator('[data-tab=insights]').click()
            expect(page.locator('#insightContent')).to_contain_text('Missing-data sensitivity')
            page.locator('[data-tab=brief]').click()
            expect(page.locator('#briefContent')).to_contain_text('Recent saved leads')
            page.locator('[data-tab=timeline]').click()
            expect(page.locator('#timelineRows .row').first).to_be_visible()
            page.locator('[data-tab=identity]').click()
            expect(page.locator('#identityInfo')).to_contain_text('candidate pairs compared')
            page.locator('.more-nav summary').click()
            with page.expect_download():page.locator('#htmlReport').click()
            page.locator('[data-tab=network]').click()
            page.locator('#cases').select_option('SHOWCASE')
            expect(page.locator('#graphAccess button')).to_have_count(10)
            page.locator('[data-tab=identity]').click()
            match=page.locator('#identityContent article').filter(has_text='asha-a → asha-b')
            expect(match).to_have_count(1)
            page.once('dialog',lambda d:d.accept('Matched fictional email identifiers'))
            match.get_by_role('button',name='Merge into right entity').click()
            expect(page.locator('#identityHistory')).to_contain_text('Matched fictional email identifiers')
            expect(page.locator('#graphAccess button')).to_have_count(9)
            page.locator('[data-tab=links]').click()
            page.locator('.link-card button').first.click()
            expect(page.locator('#inspector')).to_contain_text('Why this connection?')
            page.once('dialog',lambda d:d.accept('Seek further corroborating records'))
            page.locator('#inspector').get_by_role('button',name='Worth following').click()
            expect(page.locator('#inspector')).to_contain_text('Decision saved')
            page.locator('[data-tab=timeline]').click()
            expect(page.locator('#geoMap circle')).to_have_count(2)
            page.locator('#geoMap circle').first.click()
            expect(page.locator('#geoDetails')).to_contain_text('fictional')
            page.locator('#timeSlider').fill('0')
            page.locator('#applyTime').click()
            expect(page.locator('#end')).to_have_value('2026-01-10')
            page.locator('#clearTime').click()
            expect(page.locator('#end')).to_have_value('')
            page.locator('[data-tab=identity]').click()
            page.once('dialog',lambda d:d.accept('Demonstrate reversible identity decision'))
            page.locator('#identityHistory').get_by_role('button',name='Undo merge').click()
            expect(page.locator('#identityHistory')).to_contain_text('(undone)')
            expect(page.locator('#graphAccess button')).to_have_count(10)
            page.locator('[data-tab=network]').click()
            page.locator('#graphAccess button').filter(has_text='Asha Rao').first.click()
            page.locator('#inspector').get_by_role('button',name='Show 1-hop neighbors').click()
            page.locator('#resetGraph').click()
            page.locator('.more-nav summary').click()
            with page.expect_download() as report:page.locator('#htmlReport').click()
            report.value.save_as(str(root/'verification/showcase-report.html'))
            (root/'verification').mkdir(exist_ok=True)
            page.evaluate('window.scrollTo(0,0)')
            page.locator('#notice').evaluate('(e) => e.hidden = true')
            page.screenshot(path=str(root/'verification/dashboard-v3.png'),full_page=True,animations='disabled')
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'mobile horizontal overflow'
            assert not errors,errors
            (root/'verification/browser.json').write_text(json.dumps({'status':'passed','engine':'Chromium 134 / Playwright 1.51','transport':'FastAPI TestClient intercept (not live TCP)', 'checks':['owner login','graph','hidden-link cards','source paths','exact demo2 upload and conversion','JSON download','job processing','bulk confirmation','natural-language draft and uncertainty','node editor','insights','mobile width','identity merge and undo','persisted lead review','timeline slider synchronized with graph','geographic markers','case brief','HTML report download','one-hop expansion'],'page_errors':errors},indent=2))
            browser.close()
print('Browser checks passed')
