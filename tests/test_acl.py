from conftest import Actor,join,register
from test_documents import saved,document,png

def test_private_acl_all_routes_and_members_scope(env,community):
    owner,cid=community;a=join(env,owner,cid,'writer@example.com');outsider=register(env,'outside@example.com');anon=Actor(env[0])
    d=saved(a,cid);asset=a.post('/drafts/'+d['id']+'/media',files={'file':('x.png',png(),'image/png')}).json()['id']
    body={'type':'doc','content':[{'type':'figure','attrs':{'assetId':asset,'caption':'','alt':'图片','layout':'normal','spoiler':False}}]}
    d=a.put('/drafts/'+d['id'],json={'revision':d['revision'],**document(cid,body=body)}).json()
    p=a.post('/drafts/'+d['id']+'/publish',json={'revision':d['revision']}).json();pid=p['id']
    for x in (outsider,anon):
        assert x.get('/posts').json()['items']==[]
        for path in ('/posts/'+pid,'/posts/'+pid+'/comments','/media/'+asset,'/drafts/'+d['id']):assert x.get(path).status_code==404
        assert x.post('/posts/'+pid+'/comments',json={'body':'偷看'}).status_code==404
    assert owner.get('/media/'+asset).status_code==200
    assert owner.post('/posts/'+pid+'/comments',json={'body':'很喜欢'}).status_code==201
    a.delete('/clubs/'+cid+'/membership')
    assert a.get('/posts/'+pid).status_code==404
    assert a.get('/me/posts').json()['items']==[]

def test_public_media_snapshot_is_not_whole_draft_and_withdraw(env,community):
    owner,cid=community;a=join(env,owner,cid,'writer@example.com');anon=Actor(env[0])
    d=saved(a,cid,'public');ids=[]
    for _ in range(2):ids.append(a.post('/drafts/'+d['id']+'/media',files={'file':('x.png',png(),'image/png')}).json()['id'])
    body={'type':'doc','content':[{'type':'figure','attrs':{'assetId':ids[0],'caption':'','alt':'图片','layout':'normal','spoiler':False}}]}
    d=a.put('/drafts/'+d['id'],json={'revision':d['revision'],**document(cid,'public',body)}).json()
    p=a.post('/drafts/'+d['id']+'/publish',json={'revision':d['revision']}).json();pid=p['id']
    owner.post('/posts/'+pid+'/review',json={'decision':'approve'})
    assert anon.get('/media/'+ids[0]).status_code==200
    assert anon.get('/media/'+ids[1]).status_code==404
    assert anon.post('/posts/'+pid+'/comments',json={'body':'游客'}).status_code==401
    assert a.delete('/drafts/'+d['id']).status_code==200
    assert anon.get('/media/'+ids[0]).status_code==200
    assert a.post('/posts/'+pid+'/withdraw',json={}).status_code==200
    assert anon.get('/posts/'+pid).status_code==404
    assert anon.get('/media/'+ids[0]).status_code==404
    assert owner.post('/posts/'+pid+'/review',json={'decision':'approve'}).status_code==409

def test_idempotent_publish_rechecks_original_post_acl_after_draft_changes_club(env,community):
    owner,cid_a=community
    writer=join(env,owner,cid_a,'movedwriter@example.com')
    from app.models import Club,Membership
    with env[0].state.session_factory.begin() as db:
        club_b=Club(slug='films',name='电影团',description='电影讨论')
        db.add(club_b);db.flush()
        db.add(Membership(club_id=club_b.id,user_id=writer.id,role='member',can_invite=False))
        cid_b=club_b.id
    draft=saved(writer,cid_a)
    published_revision=draft['revision']
    path='/drafts/'+draft['id']
    post=writer.post(path+'/publish',json={'revision':published_revision}).json()
    assert writer.delete('/clubs/'+cid_a+'/membership').status_code==200
    assert writer.get('/posts/'+post['id']).status_code==404
    moved=writer.put(path,json={'revision':published_revision,**document(cid_b,title='转到仍在的电影团')})
    assert moved.status_code==200
    repeated=writer.post(path+'/publish',json={'revision':published_revision})
    assert repeated.status_code==404,repeated.text
    assert repeated.json()['error']['code']=='NOT_FOUND'
    assert 'body' not in repeated.json()
