from conftest import Actor,join,register
from io import BytesIO
from PIL import Image

def document(cid,scope='club',body=None,title='值得讨论的书'):
    return dict(title=title,summary='摘要',body=body or {'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'阅读正文'}]}]},club_id=cid,scope=scope,tags=['阅读'],feedback_intent='欢迎回应',cover_asset_id=None)
def saved(a,cid,scope='club',body=None):
    r=a.post('/drafts',json={'club_id':cid});assert r.status_code==201,r.text
    d=r.json();r=a.put('/drafts/'+d['id'],json={'revision':1,**document(cid,scope,body)});assert r.status_code==200,r.text
    return r.json()
def png():
    data=BytesIO();Image.new('RGB',(20,10),'red').save(data,format='PNG');return data.getvalue()

def test_empty_draft_save_conflict_and_public_snapshot(env,community):
    owner,cid=community;a=join(env,owner,cid,'writer@example.com')
    d=a.post('/drafts',json={}).json()
    doc=document(None,title='');r=a.put('/drafts/'+d['id'],json={'revision':1,**doc});assert r.status_code==200
    assert a.post('/drafts/'+d['id']+'/publish',json={'revision':2}).status_code==422
    d=saved(a,cid,'public');path='/drafts/'+d['id']
    first=a.post(path+'/publish',json={'revision':d['revision']});assert first.status_code==201
    pid=first.json()['id'];assert first.json()['status']=='pending'
    assert a.post(path+'/publish',json={'revision':d['revision']}).json()['id']==pid
    new=document(cid,'public',title='完全不同的标题')
    assert a.put(path,json={'revision':d['revision'],**new}).status_code==200
    stale=a.put(path,json={'revision':d['revision'],**new});assert stale.status_code==409
    assert stale.json()['error']['code']=='STALE_DRAFT'
    assert owner.get('/reviews').json()['items'][0]['title']=='值得讨论的书'
    assert Actor(env[0]).get('/posts/'+pid).status_code==404
    assert owner.post('/posts/'+pid+'/review',json={'decision':'approve'}).status_code==200
    assert owner.post('/posts/'+pid+'/review',json={'decision':'approve'}).status_code==409
    assert Actor(env[0]).get('/posts/'+pid).json()['title']=='值得讨论的书'

def test_strict_json_and_asset_ownership(env,community):
    owner,cid=community;a=join(env,owner,cid,'writer@example.com');b=join(env,owner,cid,'other@example.com')
    d=saved(a,cid);other=saved(b,cid)
    uploaded=b.post('/drafts/'+other['id']+'/media',files={'file':('x.png',png(),'image/png')});assert uploaded.status_code==201
    asset=uploaded.json()['id']
    bad_bodies=[{'type':'doc','content':[{'type':'iframe','attrs':{'src':'https://evil'}}]}, {'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'evil','marks':[{'type':'link','attrs':{'href':'javascript:alert(1)'}}]}]}]}, {'type':'doc','content':[{'type':'figure','attrs':{'assetId':asset,'caption':'','alt':'','layout':'normal','spoiler':False}}]}]
    for body in bad_bodies:
        assert a.put('/drafts/'+d['id'],json={'revision':d['revision'],**document(cid,body=body)}).status_code==422
    assert a.post('/drafts/'+d['id']+'/media',files={'file':('x.png',b'not a picture','image/png')}).status_code==422
    assert a.post('/drafts/'+d['id']+'/media',files={'file':('x.svg',b'<svg/>','image/svg+xml')}).status_code==422

def test_author_can_keep_saving_draft_after_leaving_club(env,community):
    owner,cid=community;a=join(env,owner,cid,'formerwriter@example.com');d=saved(a,cid)
    assert a.delete('/clubs/'+cid+'/membership').status_code==200
    r=a.put('/drafts/'+d['id'],json={'revision':d['revision'],**document(cid,title='保留我未发布的输入')})
    assert r.status_code==200,r.text
    assert a.post('/drafts/'+d['id']+'/publish',json={'revision':r.json()['revision']}).status_code==403

def test_tiptap_link_nullable_or_text_title_is_saved(env,community):
    owner,cid=community;draft=saved(owner,cid)
    path='/drafts/'+draft['id']
    for title in (None,'链接说明'):
        body={'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'正常选区链接','marks':[{'type':'link','attrs':{'href':'https://example.com','target':'_blank','rel':'noopener noreferrer nofollow','class':None,'title':title}}]}]}]}
        response=owner.put(path,json={'revision':draft['revision'],**document(cid,body=body)})
        assert response.status_code==200,response.text
        draft=response.json()
        assert draft['body']==body
    for attrs in ({'title':'x'*161},{'title':123},{'onclick':'evil'}):
        body={'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'恶意链接属性','marks':[{'type':'link','attrs':{'href':'https://example.com',**attrs}}]}]}]}
        assert owner.put(path,json={'revision':draft['revision'],**document(cid,body=body)}).status_code==422

def test_tiptap_bold_across_hard_break_is_saved_but_block_marks_rejected(env,community):
    owner,cid=community;draft=saved(owner,cid)
    path='/drafts/'+draft['id']
    body={'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'第一行','marks':[{'type':'bold'}]},{'type':'hardBreak','marks':[{'type':'bold'}]},{'type':'text','text':'第二行','marks':[{'type':'bold'}]}]}]}
    response=owner.put(path,json={'revision':draft['revision'],**document(cid,body=body)})
    assert response.status_code==200,response.text
    draft=response.json();assert draft['body']==body
    body={'type':'doc','content':[{'type':'paragraph','marks':[{'type':'bold'}],'content':[{'type':'text','text':'block不接受marks'}]}]}
    assert owner.put(path,json={'revision':draft['revision'],**document(cid,body=body)}).status_code==422
    body={'type':'doc','content':[{'type':'paragraph','content':[{'type':'hardBreak','marks':[{'type':'link','attrs':{'href':'javascript:alert(1)'}}]}]}]}
    assert owner.put(path,json={'revision':draft['revision'],**document(cid,body=body)}).status_code==422
