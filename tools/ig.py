#!/usr/bin/env python3
"""インスタ（@tatuya_st）用のトークンを作る・延長する（GitHub Actions で実行）。
トークンは state/ig_token.enc に、Threads と同じ鍵（THREADS_APP_SECRET）で暗号化して保存する。

モード:
  oauth    … 許可コード（CODE）とインスタのアプリの鍵（IG_SECRET）からトークンを作る（60日有効）
  refresh  … トークンを延長する（週1回）
"""
import json, os, subprocess, sys, urllib.parse, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
ENC = os.path.join(ROOT, 'state', 'ig_token.enc')
APP_ID = '2018285875537685'  # 便利アプリ-IG
REDIRECT = 'https://tatuya-st.github.io/threads-auto/callback.html'
KEY = os.environ.get('THREADS_APP_SECRET', '').strip() or os.environ.get('TOKEN2', '').strip()


def call(method, url, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url + ('?' + data.decode() if method == 'GET' else ''), data=None if method == 'GET' else data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f'インスタの返事がエラーでした：{e.code} {e.read().decode(errors="replace")[:300]}')


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
    return call('GET', 'https://graph.instagram.com/v21.0/me', {'fields': 'user_id,username', 'access_token': tok})


def oauth():
    code = os.environ.get('CODE', '').strip().replace('#_', '')
    sec = os.environ.get('IG_SECRET', '').strip()
    if not (code and sec):
        raise SystemExit('コードかインスタの鍵がありません')
    short = call('POST', 'https://api.instagram.com/oauth/access_token', {
        'client_id': APP_ID, 'client_secret': sec, 'grant_type': 'authorization_code', 'redirect_uri': REDIRECT, 'code': code})['access_token']
    tok = call('GET', 'https://graph.instagram.com/access_token', {'grant_type': 'ig_exchange_token', 'client_secret': sec, 'access_token': short})['access_token']
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


if __name__ == '__main__':
    {'oauth': oauth, 'refresh': refresh}[sys.argv[1]]()
