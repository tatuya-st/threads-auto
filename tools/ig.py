#!/usr/bin/env python3
"""インスタ（@tatuya_st）用のトークンを作る・延長する（GitHub Actions で実行）。
トークンは state/ig_token.enc に、Threads と同じ鍵（THREADS_APP_SECRET）で暗号化して保存する。

モード:
  oauth    … 許可コード（CODE）とインスタのアプリの鍵（IG_SECRET）からトークンを作る（60日有効）
  refresh  … トークンを延長する（週1回）
  insights … アカウントと最近の投稿の数字を state/ig_insights.json に保存する（反応の記録と一緒に実行）。
             続けて state/ig_comments_queue.json の「まだ」のコメント（京より）を書き込む
"""
import json, os, subprocess, sys, urllib.parse, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
ENC = os.path.join(ROOT, 'state', 'ig_token.enc')
APP_ID = '2018285875537685'  # 便利アプリ-IG
REDIRECT = 'https://tatuya-st.github.io/threads-auto/callback.html'
KEY = os.environ.get('THREADS_APP_SECRET', '').strip() or os.environ.get('TOKEN2', '').strip()


def call(method, url, params, step=''):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url + ('?' + data.decode() if method == 'GET' else ''), data=None if method == 'GET' else data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f'インスタの返事がエラーでした（{step}）：{e.code} {e.read().decode(errors="replace")[:300]}')


def save(tok):
    if not KEY:
        raise SystemExit('暗号化の鍵がありません')
    os.makedirs(os.path.dirname(ENC), exist_ok=True)
    r = subprocess.run(['openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-salt', '-a', '-A', '-out', ENC, '-pass', 'env:K'],
                       input=tok, text=True, capture_output=True, env={**os.environ, 'K': KEY})
    if r.returncode:
        raise SystemExit('暗号化に失敗しました')


def load():
    if not (os.path.exists(ENC) and KEY):
        return ''
    r = subprocess.run(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2', '-a', '-A', '-in', ENC, '-pass', 'env:K'],
                       capture_output=True, text=True, env={**os.environ, 'K': KEY})
    return r.stdout.strip() if r.returncode == 0 else ''


def me(tok):
    return call('GET', 'https://graph.instagram.com/v21.0/me', {'fields': 'user_id,username', 'access_token': tok}, '3 アカウント確認')


def oauth():
    code = os.environ.get('CODE', '').strip().replace('#_', '')
    sec = os.environ.get('IG_SECRET', '').strip()
    if not (code and sec):
        raise SystemExit('コードかインスタの鍵がありません')
    short = call('POST', 'https://api.instagram.com/oauth/access_token', {
        'client_id': APP_ID, 'client_secret': sec, 'grant_type': 'authorization_code', 'redirect_uri': REDIRECT, 'code': code}, '1 コード→短いトークン')['access_token']
    tok = call('GET', 'https://graph.instagram.com/access_token', {'grant_type': 'ig_exchange_token', 'client_secret': sec, 'access_token': short}, '2 長いトークンに交換')['access_token']
    u = me(tok)
    save(tok)
    print(f"::notice::インスタのトークンを作りました（{u.get('username')}・60日有効、毎週自動で延長）")


def refresh():
    tok = load()
    if not tok:
        print('インスタのトークンはまだありません')
        return
    tok = call('GET', 'https://graph.instagram.com/refresh_access_token', {'grant_type': 'ig_refresh_token', 'access_token': tok})['access_token']
    save(tok)
    print('インスタのトークンを延長しました')


def insights():
    import datetime
    tok = load()
    if not tok:
        print('インスタのトークンはまだありません')
        return
    G = 'https://graph.instagram.com/v21.0/'
    acc = call('GET', G + 'me', {'fields': 'user_id,username,account_type,followers_count,follows_count,media_count', 'access_token': tok}, 'アカウント')
    media = call('GET', G + 'me/media', {'fields': 'id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count,is_ai_generated',
                                         'limit': 12, 'access_token': tok}, '最近の投稿').get('data', [])
    posts = []
    for m in media:
        row = {k: m.get(k) for k in ('id', 'media_type', 'media_product_type', 'timestamp', 'permalink', 'like_count', 'comments_count', 'is_ai_generated')}
        row['caption'] = (m.get('caption') or '')[:60]
        for metric in ('reach,saved,shares,views', 'reach,saved'):
            try:
                ins = call('GET', G + m['id'] + '/insights', {'metric': metric, 'access_token': tok}, '投稿の数字')
                for d in ins.get('data', []):
                    row[d['name']] = (d.get('values') or [{}])[0].get('value', d.get('total_value', {}).get('value'))
                break
            except SystemExit:
                continue
        posts.append(row)
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%dT%H:%M+09:00')
    out = {'at': now, 'account': {k: acc.get(k) for k in ('username', 'account_type', 'followers_count', 'follows_count', 'media_count')}, 'posts': posts}
    try:
        dem = call('GET', G + 'me/insights', {'metric': 'follower_demographics', 'period': 'lifetime', 'metric_type': 'total_value',
                                              'breakdown': 'age,gender', 'access_token': tok}, 'フォロワーの年齢・性別')
        res = dem['data'][0]['total_value']['breakdowns'][0]['results']
        out['followers_age_gender'] = {'-'.join(r['dimension_values']): r['value'] for r in res}
    except (SystemExit, KeyError, IndexError) as e:
        print(f'フォロワーの年齢・性別：{e}')
    with open(os.path.join(ROOT, 'state', 'ig_insights.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"インスタ：フォロワー{acc.get('followers_count')}・投稿{acc.get('media_count')}件を記録しました")
    try:
        read_comments(tok, media)
    except SystemExit as e:
        print(f'インスタのコメント読み取り：{e}')
    req3 = os.path.join(ROOT, 'state', 'ig_probe3.request')
    if os.path.exists(req3):
        os.remove(req3)
        try:
            probe3(tok, media)
        except Exception as e:
            print(f'タイアップ確認：{e}')
    req2 = os.path.join(ROOT, 'state', 'ig_probe2.request')
    if os.path.exists(req2):
        os.remove(req2)
        try:
            probe2(tok, media)
        except Exception as e:
            print(f'インスタの全部試す：{e}')
    if not os.path.exists(os.path.join(ROOT, 'state', 'ig_probe.json')):
        try:
            probe(tok, media)
        except Exception as e:
            print(f'インスタの機能確認：{e}')
    comments(tok)


def probe(tok, media):
    """新しい機能が今のトークンで通るかを、読むだけで確かめる（書き込み・削除はしない）。結果は state/ig_probe.json。"""
    import datetime
    out = {}
    for ver in ('v21.0', 'v25.0'):
        G = f'https://graph.instagram.com/{ver}/'
        mid = media[0]['id'] if media else ''
        reel = next((m['id'] for m in media if m.get('media_product_type') == 'REELS'), mid)
        tests = {
            '投稿の残り枠': ('me/content_publishing_limit', {'fields': 'quota_usage,config'}),
            'タグ付けされた投稿': ('me/tags', {'limit': 3}),
            'ストーリーズ一覧': ('me/stories', {}),
            'コラボ招待': ('me/collaboration_invites', {}),
            'コラボ投稿一覧': ('me/collaborative_media', {}),
            '投稿の新しい項目（保存・シェア・リポスト数・AIラベル）': (mid, {'fields': 'saved_count,shares_count,reposts_count,is_ai_generated,alt_text'}),
            'リールの新しい数字（スキップ率・リポスト）': (reel + '/insights', {'metric': 'reels_skip_rate,reposts'}),
            'アカウントの属性（年齢・性別）': ('me/insights', {'metric': 'follower_demographics', 'period': 'lifetime', 'metric_type': 'total_value', 'breakdown': 'age,gender'}),
            '音源の検索（Audio API）': ('me/audio', {'q': 'cafe'}),
        }
        res = {}
        for name, (path, params) in tests.items():
            try:
                r = call('GET', G + path, {**params, 'access_token': tok}, name)
                res[name] = {'ok': True, 'sample': json.dumps(r, ensure_ascii=False)[:300]}
            except SystemExit as e:
                res[name] = {'ok': False, 'error': str(e)[:300]}
        out[ver] = res
    out['at'] = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%dT%H:%M+09:00')
    with open(os.path.join(ROOT, 'state', 'ig_probe.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('インスタの機能確認：' + '・'.join(f"{k}={'OK' if v['ok'] else 'NG'}" for k, v in out['v25.0'].items()))


def probe2(tok, media):
    """「全て試せ」用。投稿は公開しない（入れ物を作るだけ）。いいねは自分の投稿に付けてすぐ外す。結果は state/ig_probe2.json。"""
    import datetime, time
    G = 'https://graph.instagram.com/v25.0/'
    PAGES = 'https://tatuya-st.github.io/threads-auto/'
    out = {}
    def t(name, method, path, params):
        try:
            r = call(method, G + path, {**params, 'access_token': tok}, name)
            out[name] = {'ok': True, 'sample': json.dumps(r, ensure_ascii=False)[:300]}
            return r
        except SystemExit as e:
            out[name] = {'ok': False, 'error': str(e)[:300]}
            return None
    mid = media[0]['id'] if media else ''
    reel = next((m['id'] for m in media if m.get('media_product_type') == 'REELS'), mid)
    # 1. AIラベル付きの入れ物（公開しない）
    c = t('AIラベル付きの画像の入れ物を作る（公開しない）', 'POST', 'me/media',
          {'image_url': PAGES + 'assets/photos/ready/takumihonpo-kyo-final.jpg', 'caption': 'テスト（公開しません）', 'is_ai_generated': 'true'})
    cid = (c or {}).get('id')
    if cid:
        t('入れ物の状態とAIラベルを読む', 'GET', cid, {'fields': 'id,status_code,is_ai_generated'})
    # 2. トライアルリールの入れ物（公開しない）
    r = t('トライアルリールの入れ物を作る（公開しない）', 'POST', 'me/media',
          {'media_type': 'REELS', 'video_url': PAGES + 'assets/photos/ready/currentbody-2026-11-12/reel-currentbody-v3.mp4',
           'caption': 'テスト（公開しません）', 'trial_params': json.dumps({'graduation_strategy': 'MANUAL'}), 'is_ai_generated': 'true'})
    rid = (r or {}).get('id')
    if rid:
        time.sleep(20)
        t('トライアルリールの入れ物の状態', 'GET', rid, {'fields': 'id,status_code,status'})
    # 3. 削除の権限（公開していない入れ物を消す。公開中の投稿には触らない）
    if cid:
        t('削除（未公開の入れ物で試す）', 'DELETE', cid, {})
    # 4. 公開済み投稿のAIラベル項目を読む
    if mid:
        t('公開済み投稿のAIラベル項目', 'GET', mid, {'fields': 'id,is_ai_generated,alt_text'})
    # 5. 数字（1つずつ）
    t('リールのスキップ率', 'GET', reel + '/insights', {'metric': 'reels_skip_rate'})
    t('アカウントのリポスト数', 'GET', 'me/insights', {'metric': 'reposts', 'period': 'day', 'metric_type': 'total_value'})
    # 6. いいね（自分の最新投稿に付けてすぐ外す）
    if mid and t('いいねを付ける（自分の投稿）', 'POST', 'me/likes', {'media_id': mid}):
        t('いいねを外す（元に戻す）', 'DELETE', 'me/likes', {'media_id': mid})
    # 7. 正しい呼び方でもう一度（公式ではFacebookログイン版のみの印あり）
    t('コラボ招待（正しい呼び方）', 'GET', 'me/collaboration_invites', {})
    t('音源検索（ig_audio）', 'GET', 'ig_audio', {'audio_type': 'music'})
    out['at'] = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%dT%H:%M+09:00')
    with open(os.path.join(ROOT, 'state', 'ig_probe2.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('インスタの全部試す：' + '・'.join(f"{k}={'OK' if v['ok'] else 'NG'}" for k, v in out.items() if k != 'at'))


def probe3(tok, media):
    """タイアップ投稿ラベル（is_paid_partnership）が読めるか・付けられるか。公開はしない。結果は state/ig_probe3.json。"""
    G = 'https://graph.instagram.com/v25.0/'
    out = {}
    def t(name, method, path, params):
        try:
            r = call(method, G + path, {**params, 'access_token': tok}, name)
            out[name] = {'ok': True, 'sample': json.dumps(r, ensure_ascii=False)[:400]}
            return r
        except SystemExit as e:
            out[name] = {'ok': False, 'error': str(e)[:300]}
    for m in media[:12]:
        t('読む ' + m['id'] + ' ' + (m.get('caption') or '')[:12].replace('\n', ' '), 'GET', m['id'], {'fields': 'id,is_paid_partnership'})
    t('付けて入れ物を作る（公開しない）', 'POST', 'me/media', {'image_url': 'https://tatuya-st.github.io/threads-auto/assets/photos/ready/takumihonpo-kyo-final.jpg',
                                                    'caption': 'テスト（公開しません）', 'is_paid_partnership': 'true'})
    with open(os.path.join(ROOT, 'state', 'ig_probe3.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


def read_comments(tok, media):
    """コメントのある投稿（11/11以降）のコメントと返信を state/ig_comments_seen.json に保存する（京が返事を書くため）。"""
    G = 'https://graph.instagram.com/v21.0/'
    out = []
    for m in media:
        if (m.get('timestamp') or '') < '2026-11-11' or not m.get('comments_count'):
            continue
        cs = call('GET', G + m['id'] + '/comments', {'fields': 'id,text,username,timestamp,replies{id,text,username,timestamp}',
                                                    'limit': 50, 'access_token': tok}, 'コメントを読む').get('data', [])
        out.append({'media_id': m['id'], 'permalink': m.get('permalink'), 'caption': (m.get('caption') or '')[:40],
                    'comments': [{'id': c['id'], 'user': c.get('username'), 'text': c.get('text'), 'at': c.get('timestamp'),
                                  'replies': [{'id': r['id'], 'user': r.get('username'), 'text': r.get('text')}
                                              for r in (c.get('replies') or {}).get('data', [])]} for c in cs]})
    with open(os.path.join(ROOT, 'state', 'ig_comments_seen.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    # 調べ用（コメントが0件で返る原因を探す。原因がわかったら消す）
    dbg = {}
    q = os.path.join(ROOT, 'state', 'ig_comments_queue.json')
    tests = {}
    if out:
        mid = out[0]['media_id']
        tests['comments_素'] = (mid + '/comments', {})
        tests['media_comments欄'] = (mid, {'fields': 'comments_count,comments{id,text,username,from}'})
    if os.path.exists(q):
        cid = next((i.get('comment_id') for i in json.load(open(q)) if i.get('comment_id')), None)
        if cid:
            tests['京のコメント'] = (cid, {'fields': 'id,text,username,from,media,replies'})
            tests['京のコメント_文字だけ'] = (cid, {'fields': 'text,timestamp'})
            tests['京のコメント_素'] = (cid, {})
    if out:
        tests['comments_文字だけ'] = (out[0]['media_id'] + '/comments', {'fields': 'id,text,timestamp'})
        tests['v23_comments'] = ('../v23.0/' + out[0]['media_id'] + '/comments', {'fields': 'id,text,username,timestamp'})
        tests['me_権限'] = ('me', {'fields': 'user_id,username'})
    for k, (path, prm) in tests.items():
        try:
            dbg[k] = call('GET', G + path, {**prm, 'access_token': tok}, k)
        except SystemExit as e:
            dbg[k] = str(e)[:400]
    with open(os.path.join(ROOT, 'state', 'ig_comments_debug.json'), 'w') as f:
        json.dump(dbg, f, ensure_ascii=False, indent=1)


def comments(tok):
    """state/ig_comments_queue.json の「まだ」のコメントを、言葉が一致する投稿（11/11以降）に1回だけ書き込む。"""
    import datetime
    q = os.path.join(ROOT, 'state', 'ig_comments_queue.json')
    if not os.path.exists(q):
        return
    items = json.load(open(q))
    todo = [i for i in items if i.get('status') == 'まだ']
    if not todo:
        return
    G = 'https://graph.instagram.com/v21.0/'
    media = call('GET', G + 'me/media', {'fields': 'id,caption,timestamp,permalink', 'limit': 25, 'access_token': tok}, 'コメント先の投稿').get('data', [])
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%dT%H:%M+09:00')
    for it in todo:
        if not it.get('reply_to') and it.get('reply_match') and it.get('media_id'):
            # 返信先のコメントIDが分からないとき：その投稿のコメントから、言葉が一致する1件を探す
            try:
                cs = call('GET', G + it['media_id'] + '/comments', {'fields': 'id,text', 'limit': 50, 'access_token': tok}, '返信先を探す').get('data', [])
            except SystemExit as e:
                it['note'] = f'{now} {str(e)[:200]}'
                continue
            hit = [c for c in cs if it['reply_match'] in (c.get('text') or '')]
            if len(hit) != 1:
                it['note'] = f'{now} 返信先が{len(hit)}件見つかり書き込まず（1件だけのときに書く）'
                continue
            it['reply_to'] = hit[0]['id']
        if it.get('reply_to'):
            try:
                r = call('POST', G + it['reply_to'] + '/replies', {'message': it['text'], 'access_token': tok}, 'コメントに返信')
                it.update(status='済み', comment_id=r.get('id'), at=now)
                it.pop('note', None)
            except SystemExit as e:
                it['note'] = f'{now} {str(e)[:200]}'
            continue
        if it.get('media_id'):
            hit = [m for m in media if m.get('id') == it['media_id']] or [{'id': it['media_id']}]
        else:
            hit = [m for m in media if (m.get('timestamp') or '') >= it.get('after', '2026-11-11')
                   and any(k in (m.get('caption') or '') for k in it['keywords'])]
        if len(hit) != 1:
            it['note'] = f'{now} 投稿が{len(hit)}件見つかり書き込まず（1件だけのときに書く）'
            continue
        try:
            r = call('POST', G + hit[0]['id'] + '/comments', {'message': it['text'], 'access_token': tok}, 'コメントを書く')
            it.update(status='済み', comment_id=r.get('id'), permalink=hit[0].get('permalink'), at=now)
            it.pop('note', None)
        except SystemExit as e:
            it['note'] = f'{now} {str(e)[:200]}'
            if '"code":10' in str(e) or 'permission' in str(e).lower():
                break
    with open(q, 'w') as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    print('インスタのコメント：' + '／'.join(f"{i['name']}={i['status']}" for i in items))


if __name__ == '__main__':
    {'oauth': oauth, 'refresh': refresh, 'insights': insights, 'comments': lambda: comments(load())}[sys.argv[1]]()
