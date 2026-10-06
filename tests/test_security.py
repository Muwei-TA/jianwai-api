import json
from concurrent.futures import ThreadPoolExecutor
from conftest import Actor,register,join
from test_documents import saved,document,png

def test_origin_rotation_tokens_and_rate_limit(env):
    a=register(env,'verify@example.com',False);app,settings=env
    msg=json.loads(next(settings.outbox_dir.glob('*.json')).read_text())
    headers={'Origin':'https://evil.example','X-CSRF-Token':a.csrf}
    assert a.client.post('/api/v1/auth/verify-email',json={'token':msg['token']},headers=headers).status_code==403
    assert a.post('/auth/verify-email',json={'token':msg['token']}).status_code==200
    assert a.post('/auth/verify-email',json={'token':msg['token']}).status_code==422
    old_cookie=a.client.cookies.get('jw_session');old_csrf=a.csrf
    assert a.post('/auth/login',json={'email':'verify@example.com','password':'Strong secret 123!'}).status_code==200
    assert a.csrf!=old_csrf
    stale=Actor(app);stale.client.cookies.set('jw_session',old_cookie)
    assert stale.get('/auth/session').json()['user'] is None
    for _ in range(11):last=a.post('/auth/login',json={'email':'verify@example.com','password':'wrong'})
    assert last.status_code==429

def test_invitation_cap_revoke_leave_and_owner_members(env,community):
    owner,cid=community;a=join(env,owner,cid,'invitewriter@example.com')
    assert a.get('/clubs/'+cid+'/members').status_code==404
    rows=owner.get('/clubs/'+cid+'/members').json()['items'];assert len(rows)==2 and all('email' not in row for row in rows)
    assert a.patch(f'/clubs/{cid}/members/{a.id}/invite-permission',json={'can_invite':True}).status_code==404
    assert owner.patch(f'/clubs/{cid}/members/{a.id}/invite-permission',json={'can_invite':True}).status_code==200
    code=a.post('/clubs/'+cid+'/invites',json={}).json()['code']
    a.delete('/clubs/'+cid+'/membership')
    assert Actor(env[0]).post('/invites/preview',json={'code':code}).status_code==409
    invitations=[]
    for _ in range(20):
        result=owner.post('/clubs/'+cid+'/invites',json={});assert result.status_code==201;invitations.append(result.json())
    assert owner.post('/clubs/'+cid+'/invites',json={}).status_code==409
    first=invitations[0];assert owner.delete(f'/clubs/{cid}/invites/'+first['id']).status_code==200
    assert Actor(env[0]).post('/invites/preview',json={'code':first['code']}).status_code==409
    assert all('code' not in row for row in owner.get('/clubs/'+cid+'/invites').json()['items'])

def test_members_acl_review_note_and_concurrent_withdraw(env,community):
    owner,cid=community;a=join(env,owner,cid,'author@example.com');outsider=register(env,'outsider@example.com');anon=Actor(env[0])
    d=saved(a,cid,'members');p=a.post('/drafts/'+d['id']+'/publish',json={'revision':d['revision']}).json()
    assert outsider.get('/posts/'+p['id']).status_code==404
    a.delete('/clubs/'+cid+'/membership')
    assert a.get('/posts/'+p['id']).status_code==200
    code=owner.post('/clubs/'+cid+'/invites',json={}).json()['code'];a.post('/invites/redeem',json={'code':code})
    d=saved(a,cid,'public');p=a.post('/drafts/'+d['id']+'/publish',json={'revision':d['revision']}).json();pid=p['id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(owner.post,'/posts/'+pid+'/review',json={'decision':'approve','note':'内部审核注释'}),pool.submit(a.post,'/posts/'+pid+'/withdraw',json={})]
        outcomes=[f.result().status_code for f in futures]
    assert outcomes[1]==200 and outcomes[0] in (200,409)
    assert a.get('/posts/'+pid).json()['status']=='withdrawn'
    assert anon.get('/posts/'+pid).status_code==404
    assert anon.get('/posts/'+pid+'/comments').status_code==404
    assert a.post('/posts/'+pid+'/comments',json={'body':'不能回复撤回文章'}).status_code==409
    d=saved(a,cid,'public');p=a.post('/drafts/'+d['id']+'/publish',json={'revision':d['revision']}).json();pid=p['id']
    owner.post('/posts/'+pid+'/review',json={'decision':'approve','note':'内部审核注释'})
    assert 'review_note' not in anon.get('/posts/'+pid).json()
    assert a.get('/posts/'+pid).json()['review_note']=='内部审核注释'

def test_json_limits_and_draft_cover_ownership(env,community):
    owner,cid=community;a=join(env,owner,cid,'author@example.com');d=saved(a,cid)
    original=d['revision'];path='/drafts/'+d['id']
    bad=[{'type':'doc','attrs':{'onclick':'evil'}},{'type':'doc','content':[{'type':'heading','attrs':{'level':1}}]},{'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'x'*20001}]}]}]
    deep={'type':'paragraph'}
    for _ in range(22):deep={'type':'blockquote','content':[deep]}
    bad.append({'type':'doc','content':[deep]})
    for body in bad:assert a.put(path,json={'revision':original,**document(cid,body=body)}).status_code==422
    assert a.get(path).json()['revision']==original
    other=saved(a,cid);asset=a.post('/drafts/'+other['id']+'/media',files={'file':('x.png',png(),'image/png')}).json()['id']
    doc=document(cid);doc['cover_asset_id']=asset
    assert a.put(path,json={'revision':original,**doc}).status_code==422

def test_invalid_ids_and_unknown_routes_return_uniform_errors(env):
    a=register(env,'shape@example.com')
    from fastapi.testclient import TestClient
    previous=a.client.cookies.get('jw_session')
    a.client=TestClient(env[0],raise_server_exceptions=False)
    a.client.cookies.set('jw_session',previous)
    a.csrf=a.get('/auth/session').json()['csrf_token']
    for cid in (['fake'],{'id':'fake'},123):
        result=a.post('/drafts',json={'club_id':cid});assert result.status_code==422,result.text
    result=a.get('/no-such-route');assert result.status_code==404
    assert result.json()['error']['code']=='NOT_FOUND'

def test_image_mime_pixels_metadata_and_private_headers(env,community):
    from PIL import Image
    from io import BytesIO
    owner,cid=community;d=saved(owner,cid);path='/drafts/'+d['id']+'/media'
    assert owner.post(path,files={'file':('fake.jpg',png(),'image/jpeg')}).status_code==422
    data=BytesIO();Image.new('RGB',(5001,5000)).save(data,format='PNG')
    assert owner.post(path,files={'file':('huge.png',data.getvalue(),'image/png')}).status_code==422
    data=BytesIO();image=Image.new('RGB',(5,5));exif=Image.Exif();exif[0x010e]='private location';image.save(data,format='JPEG',exif=exif)
    asset=owner.post(path,files={'file':('meta.jpg',data.getvalue(),'image/jpeg')}).json()['id']
    response=owner.get('/media/'+asset);assert response.headers['cache-control']=='private, no-store'
    assert response.headers['x-content-type-options']=='nosniff'
    assert not Image.open(BytesIO(response.content)).getexif()

def test_rate_limit_cannot_be_bypassed_with_resource_ids(env):
    a=Actor(env[0])
    for i in range(121):result=a.post('/nonexistent-'+str(i),json={})
    assert result.status_code==429
