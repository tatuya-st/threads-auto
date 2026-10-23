#!/usr/bin/env python3
"""まだ公開していない queue/<id>.json を Threads に画像つきで投稿する（GitHub Actions で実行）。

モード:
  publish  … 未公開の投稿を1本ずつ公開（画像は images/<id>.png を先に push しておくこと）
  refresh  … アクセストークンを延長して token.enc に暗号化保存（60日で切れるため週1回）

環境変数: THREADS_TOKEN（最初に貼るトークン）, THREADS_APP_SECRET（暗号化の鍵にも使う）, GITHUB_REPOSITORY
"""
import glob, json, os, subprocess, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

API = 'https://graph.threads.net/v1.0'
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
ENC = os.path.join(ROOT, 'state', 'token.enc')
JST = timezone(timedelta(hours=9))
import re as _re
SECRET = os.environ.get('THREADS_APP_SECRET', '').strip()
# 「TOKEN」に app secret（32桁の英数字）が入っている場合は、鍵として使う
_t2 = os.environ.get('TOKEN2', '').strip()
if not SECRET and _re.fullmatch(r'[0-9a-f]{32}', _t2):
    SECRET = _t2
    os.environ['THREADS_APP_SECRET'] = _t2
if os.environ.get('THREADS_TOKEN', '').strip() == SECRET:
    os.environ['THREADS_TOKEN'] = ''


def call(method, url, params, tries=3):
    """Threads API を呼ぶ。サーバー側の一時的なエラー（5xx・429・通信切れ）は待って最大3回までやり直す。"""
    data = urllib.parse.urlencode(params).encode()
    for n in range(tries):
        if method == 'GET':
            req = urllib.request.Request(url + '?' + data.decode())
        else:
            req = urllib.request.Request(url, data=data, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors='replace')
            err = RuntimeError(f'{e.code} {body[:300]}')
            if not (e.code >= 500 or e.code == 429) or n == tries - 1:
                raise err
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if n == tries - 1:
                raise RuntimeError(f'通信エラー: {e}')
        time.sleep(15 * (n + 1))


def decrypt():
    if not (os.path.exists(ENC) and SECRET):
        return ''
    r = subprocess.run(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2', '-a', '-A', '-in', ENC, '-pass', 'env:THREADS_APP_SECRET'], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ''


def encrypt(tok):
    os.makedirs(os.path.dirname(ENC), exist_ok=True)
    r = subprocess.run(['openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-salt', '-a', '-A', '-out', ENC, '-pass', 'env:THREADS_APP_SECRET'], input=tok, text=True, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('トークンを保存できませんでした')


ERRS = []


def works(tok):
    try:
        return call('GET', f'{API}/me', {'fields': 'id,username', 'access_token': tok})
    except Exception as e:
        ERRS.append(str(e).replace(tok, '***')[:200])
        return None


def token():
    """使えるトークンを返す。貼り直されたトークン（Secrets）を優先し、短期トークンなら長期に交換して保存する。"""
    tries = [('secret', os.environ.get('THREADS_TOKEN', '').strip()), ('saved', decrypt())]
    for src, tok in tries:
        if not tok:
            continue
        me = works(tok)
        if not me:
            continue
        if src == 'secret' and SECRET:
            # 1時間で切れる短期トークンなら60日の長期トークンに交換（長期ならエラーになるのでそのまま）
            try:
                tok = call('GET', 'https://graph.threads.net/access_token', {'grant_type': 'th_exchange_token', 'client_secret': SECRET, 'access_token': tok})['access_token']
            except Exception:
                pass
            if decrypt() != tok:
                encrypt(tok)
        return tok, me
    _t = os.environ.get('THREADS_TOKEN', '').strip()
    print(f"::error::中身の形: 長さ{len(_t)} 先頭{_t[:2]!r} 英数字のみ={_t.isalnum()}")
    print(f"::error::トークン確認: secret={'あり' if os.environ.get('THREADS_TOKEN','').strip() else 'なし'} 鍵={'あり' if SECRET else 'なし'} 保存={'あり' if os.path.exists(ENC) else 'なし'} 応答={' / '.join(ERRS)}")
    raise SystemExit('Threadsのトークンが使えません。トークンを作り直して GitHub の THREADS_ACCESS_TOKEN に貼り直してください。')


def refresh():
    if not SECRET:
        _, me = token()
        print(f"::notice::トークンOK（@{me.get('username')}）")
        print('::notice::THREADS_APP_SECRET が未登録のため延長はお休み（投稿はできます。トークンは約60日有効）')
        return
    tok, _ = token()
    try:
        new = call('GET', 'https://graph.threads.net/refresh_access_token', {'grant_type': 'th_refresh_token', 'access_token': tok})['access_token']
        encrypt(new)
        print('トークンを延長しました')
    except Exception as e:
        print('延長は次回（発行から24時間たってから）:', e)
        if SECRET and decrypt() != tok:
            encrypt(tok)


def wait_ready(cid, tok):
    for _ in range(30):
        time.sleep(6)
        st = call('GET', f'{API}/{cid}', {'fields': 'status,error_message', 'access_token': tok})
        if st.get('status') == 'FINISHED':
            return
        if st.get('status') in ('ERROR', 'EXPIRED'):
            raise RuntimeError(f"画像の処理に失敗: {st.get('error_message')}")
    raise RuntimeError('画像の処理が終わりませんでした')


def publish():
    repo = os.environ['GITHUB_REPOSITORY']
    todo = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'queue', '*.json'))):
        qid = os.path.splitext(os.path.basename(f))[0]
        if not os.path.exists(os.path.join(ROOT, 'state', 'posted', qid + '.json')):
            todo.append((qid, json.load(open(f, encoding='utf-8'))))
    if not todo:
        print('公開待ちなし')
        return
    tok, me = token()
    sent_p = os.path.join(ROOT, 'state', 'sent.json')
    sent = json.load(open(sent_p, encoding='utf-8')) if os.path.exists(sent_p) else {}
    sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip() or 'main'
    failed = []
    for qid, q in todo[:2]:
        # 二重投稿の最終チェック：すでに Threads に出した商品が入っていたら公開しない
        dup = [it['itemcode'] for it in q['items'] if it['itemcode'] in sent]
        rec = {'id': qid, 'axis': q.get('axis'), 'theme': q.get('theme'), 'codes': [it['itemcode'] for it in q['items']]}
        try:
            made = datetime.strptime(qid[:13], '%Y%m%d-%H%M').replace(tzinfo=JST)
        except ValueError:
            made = datetime.now(JST)
        if dup:
            rec.update(skipped='二重投稿になるため公開せず', dup=dup)
        elif datetime.now(JST) - made > timedelta(hours=3):
            # 前回失敗して残った古い投稿は出さない（次の投稿と続けて2本出るのを防ぐ）
            rec.update(skipped='時間がたったため見送り')
        else:
          try:
              if q.get('kind') == 'talk':
                  params = {'media_type': 'TEXT', 'text': q['text'], 'access_token': tok}
              else:
                  img = f'https://raw.githubusercontent.com/{repo}/{sha}/images/{qid}.png'
                  params = {'media_type': 'IMAGE', 'image_url': img, 'text': q['text'], 'access_token': tok}
              if q.get('topic'):
                  params['topic_tag'] = q['topic']
              cid = call('POST', f"{API}/{me['id']}/threads", params)['id']
              if q.get('kind') != 'talk':
                  wait_ready(cid, tok)
              else:
                  time.sleep(3)
              mid = call('POST', f"{API}/{me['id']}/threads_publish", {'creation_id': cid, 'access_token': tok})['id']
              try:
                  link = call('GET', f'{API}/{mid}', {'fields': 'permalink', 'access_token': tok}).get('permalink', '')
              except Exception:
                  link = ''
              now = datetime.now(JST).isoformat(timespec='minutes')
              rec.update(media_id=mid, permalink=link, at=now)
              # リンクは本文ではなく自分の返信に付ける（失敗しても投稿本体はそのまま）
              if q.get('reply'):
                  try:
                      time.sleep(20)
                      rid = call('POST', f"{API}/{me['id']}/threads", {'media_type': 'TEXT', 'text': q['reply'], 'reply_to_id': mid, 'access_token': tok})['id']
                      time.sleep(3)
                      call('POST', f"{API}/{me['id']}/threads_publish", {'creation_id': rid, 'access_token': tok})
                      rec['reply'] = 'ok'
                  except Exception as e:
                      rec['reply'] = 'ng'
                      print(f"::warning::リンクの返信は付けられませんでした（本文はプロフィールのリンク案内のみ）: {str(e).replace(tok, '***')[:150]}")
              for it in q['items']:
                  sent[it['itemcode']] = {'name': it['name'], 'at': now, 'post': qid}
          except Exception as e:
            # この1本だけ失敗として記録し、同じ投稿を何度もやり直さない
            msg = str(e).replace(tok, '***')[:200]
            rec.update(skipped=f'エラー: {msg}')
            failed.append(qid)
            print(f'::error::{qid} を投稿できませんでした: {msg}')
        os.makedirs(os.path.join(ROOT, 'state', 'posted'), exist_ok=True)
        json.dump(rec, open(os.path.join(ROOT, 'state', 'posted', qid + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        json.dump(sent, open(sent_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(qid, rec.get('permalink') or rec.get('skipped'))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    {'publish': publish, 'refresh': refresh}[sys.argv[1] if len(sys.argv) > 1 else 'publish']()
