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
    media = call('GET', G + 'me/media', {'fields': 'id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count',
                                         'limit': 12, 'access_token': tok}, '最近の投稿').get('data', [])
    posts = []
    for m in media:
        row = {k: m.get(k) for k in ('id', 'media_type', 'media_product_type', 'timestamp', 'permalink', 'like_count', 'comments_count')}
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
    with open(os.path.join(ROOT, 'state', 'ig_insights.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"インスタ：フォロワー{acc.get('followers_count')}・投稿{acc.get('media_count')}件を記録しました")
    try:
        read_comments(tok, media)
    except SystemExit as e:
        print(f'インスタのコメント読み取り：{e}')
    comments(tok)


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
        if it.get('reply_to'):
            try:
                r = call('POST', G + it['reply_to'] + '/replies', {'message': it['text'], 'access_token': tok}, 'コメントに返信')
                it.update(status='済み', comment_id=r.get('id'), at=now)
                it.pop('note', None)
            except SystemExit as e:
                it['note'] = f'{now} {str(e)[:200]}'
            continue
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
