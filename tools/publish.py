#!/usr/bin/env python3
"""まだ公開していない queue/<id>.json を Threads に画像つきで投稿する（GitHub Actions で実行）。

モード:
  publish  … 未公開の投稿を1本ずつ公開（画像は images/<id>.png を先に push しておくこと）
  refresh  … アクセストークンを延長して token.enc に暗号化保存（60日で切れるため週1回）

環境変数: THREADS_TOKEN（最初に貼るトークン）, THREADS_APP_SECRET（暗号化の鍵にも使う）, GITHUB_REPOSITORY
"""
import glob, json, os, random, subprocess, sys, time, urllib.parse, urllib.request
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
        if method in ('GET', 'DELETE'):
            req = urllib.request.Request(url + '?' + data.decode(), method=method)
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
        os.environ['TOKEN_SRC'] = src
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


def remote_has(rel):
    """push 後に別の実行が先に記録した物があるか（古いコミットで動いた実行が二重に出さないように）。"""
    try:
        subprocess.run(['git', 'fetch', '-q', '--depth', '1', 'origin', 'main'], cwd=ROOT, capture_output=True, timeout=60)
        return subprocess.run(['git', 'cat-file', '-e', 'FETCH_HEAD:' + rel], cwd=ROOT, capture_output=True).returncode == 0
    except Exception:
        return False


def replied_ids():
    """ルイが自動で返信したコメントのid（state/replied/ の記録から）"""
    ids = set()
    for f in glob.glob(os.path.join(ROOT, 'state', 'replied', '*.json')):
        try:
            ids |= {str(x.get('to')) for x in json.load(open(f, encoding='utf-8')).get('done', [])}
        except Exception:
            pass
    return ids


def send_replies(tok, me):
    """queue/replies/<id>.json（ルイが決めたコメントへの返信）を出し、結果を state/replied/<id>.json に残す。
    中身: {"kind":"replies","items":[{"to":コメントのid,"user":名前,"text":返信文}]}"""
    files = sorted(glob.glob(os.path.join(ROOT, 'queue', 'replies', '*.json')))
    outd = os.path.join(ROOT, 'state', 'replied')
    todo = [f for f in files if not os.path.exists(os.path.join(outd, os.path.basename(f)))]
    if not todo:
        return True
    os.makedirs(outd, exist_ok=True)
    done_to = replied_ids()
    ok_all = True
    for f in todo:
        rid_ = os.path.splitext(os.path.basename(f))[0]
        if remote_has(f'state/replied/{rid_}.json'):
            print(f'{rid_} はほかの実行で返信済みなので出しません')
            continue
        q = json.load(open(f, encoding='utf-8'))
        rec = {'id': rid_, 'kind': 'replies', 'done': [], 'ng': []}
        for n, it in enumerate(q.get('items', [])[:50]):
            if str(it.get('to')) in done_to:
                print(f"{it.get('user', '')} さんにはもう返信済みなので出しません")
                continue
            if n:
                time.sleep(random.randint(45, 90))
            try:
                cid = call('POST', f"{API}/{me['id']}/threads", {'media_type': 'TEXT', 'text': it['text'], 'reply_to_id': it['to'], 'access_token': tok})['id']
                time.sleep(3)
                mid = call('POST', f"{API}/{me['id']}/threads_publish", {'creation_id': cid, 'access_token': tok})['id']
                rec['done'].append({'to': it['to'], 'reply_id': mid})
                done_to.add(str(it['to']))
            except Exception as e:
                msg = str(e).replace(tok, '***')[:200]
                rec['ng'].append({'to': it.get('to'), 'error': msg})
                print(f"::warning::{it.get('user', '')} さんへの返信を出せませんでした: {msg}")
        rec['at'] = datetime.now(JST).isoformat(timespec='minutes')
        json.dump(rec, open(os.path.join(outd, rid_ + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"{rid_} コメント返信 {len(rec['done'])}件（失敗 {len(rec['ng'])}件）")
        if rec['ng'] and not rec['done']:
            ok_all = False
    return ok_all


def recent_texts(tok, me):
    """Threadsに実際に出ている自分の最近の投稿の本文（git の記録がずれても二重投稿を止める最後の砦）"""
    try:
        r = call('GET', f"{API}/{me['id']}/threads", {'fields': 'text', 'limit': 25, 'access_token': tok})
        return [''.join((x.get('text') or '').split())[:60] for x in r.get('data', [])]
    except Exception as e:
        print(f"::warning::最近の投稿を読めませんでした: {str(e).replace(tok, '***')[:150]}")
        return None


LINK_GAP_H = 20  # リンク返信は約1日1回まで（貼りすぎによる表示減・凍結を避ける）


def last_link_at():
    """最後にリンク返信を付けた時刻（state/posted の記録から）"""
    last = None
    for f in glob.glob(os.path.join(ROOT, 'state', 'posted', '*.json')):
        try:
            r = json.load(open(f, encoding='utf-8'))
            if r.get('reply') == 'ok' and r.get('at'):
                t = datetime.fromisoformat(r['at'])
                last = t if last is None or t > last else last
        except Exception:
            pass
    return last


def thin_link(q):
    """直近にリンクを貼っていたら、今回はリンク返信を付けずプロフィール案内にする（PR表記は残す）"""
    last = last_link_at()
    if not q.get('reply') or not last or datetime.now(JST) - last >= timedelta(hours=LINK_GAP_H):
        return q
    q = dict(q, reply=None)
    q['text'] = (q.get('text') or '').replace('※PR：返信に楽天ROOMのリンクがあります', '※PR：楽天ROOMはプロフィールのリンクから')
    print(f"{q.get('id')} は直近にリンクを貼ったため、今回はリンク返信なし")
    return q


def publish():
    repo = os.environ['GITHUB_REPOSITORY']
    todo = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'queue', '*.json'))):
        qid = os.path.splitext(os.path.basename(f))[0]
        if not os.path.exists(os.path.join(ROOT, 'state', 'posted', qid + '.json')):
            todo.append((qid, json.load(open(f, encoding='utf-8'))))
    has_rep = any(not os.path.exists(os.path.join(ROOT, 'state', 'replied', os.path.basename(f)))
                  for f in glob.glob(os.path.join(ROOT, 'queue', 'replies', '*.json')))
    if not todo and not has_rep:
        print('公開待ちなし')
        return
    tok, me = token()
    rep_ok = send_replies(tok, me) if has_rep else True
    if not todo:
        if not rep_ok:
            raise SystemExit(1)
        return
    sent_p = os.path.join(ROOT, 'state', 'sent.json')
    sent = json.load(open(sent_p, encoding='utf-8')) if os.path.exists(sent_p) else {}
    sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip() or 'main'
    failed = []
    live = recent_texts(tok, me)
    for qid, q in todo[:2]:
        if remote_has(f'state/posted/{qid}.json'):
            print(f'{qid} はほかの実行で公開済みなので出しません')
            continue
        q = thin_link(q)
        # 二重投稿の最終チェック：すでに Threads に出した商品が入っていたら公開しない
        # 商品つきの投稿には必ずPR表記を入れる（ステマ規制対策）
        if q.get('items') and 'PR' not in (q.get('text') or ''):
            q['text'] = (q.get('text') or '').rstrip() + '\n\n※PR'
        # 同じ商品コードに加え、同じ商品名も二度と出さない（楽天の「同じSNSで同じ商品は1回まで」対策）
        nm = lambda s: ''.join((s or '').split()).lower()
        sent_names = {nm(v.get('name')) for v in sent.values() if isinstance(v, dict)}
        dup = [it['itemcode'] for it in q['items'] if it['itemcode'] in sent or nm(it.get('name')) in sent_names]
        rec = {'id': qid, 'axis': q.get('axis'), 'theme': q.get('theme'), 'codes': [it['itemcode'] for it in q['items']]}
        try:
            made = datetime.strptime(qid[:13], '%Y%m%d-%H%M').replace(tzinfo=JST)
        except ValueError:
            made = datetime.now(JST)
        head = ''.join((q.get('text') or '').split())[:60]
        if live is None:
            rec = None
            print(f'{qid} は最近の投稿を確認できないため、今回は出さずに次の実行に回します')
            continue
        if head and head in live:
            rec.update(skipped='Threadsに同じ本文がすでにあるため公開せず')
        elif dup:
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
    if failed or not rep_ok:
        raise SystemExit(1)


def insights():
    """直近の投稿の反応（閲覧・いいね・返信・再投稿）とアカウント全体の数字を state/insights.json に保存する。"""
    tok, me = token()
    out = {'at': datetime.now(JST).isoformat(timespec='minutes'), 'posts': {}}
    try:
        r = call('GET', f"{API}/{me['id']}/threads_insights", {'metric': 'views,likes,replies,reposts,followers_count', 'access_token': tok})
        acc = {}
        for m in r.get('data', []):
            v = m.get('total_value', {}).get('value')
            if v is None and m.get('values'):
                v = sum(x.get('value', 0) for x in m['values'])
            acc[m['name']] = v
        out['account'] = acc
    except Exception as e:
        print(f"::error::アカウントの数字を読めません（threads_manage_insights の許可が必要）: {str(e).replace(tok, '***')[:200]}")
        raise SystemExit(1)
    since = datetime.now(JST) - timedelta(days=14)
    for f in sorted(glob.glob(os.path.join(ROOT, 'state', 'posted', '*.json'))):
        rec = json.load(open(f, encoding='utf-8'))
        if not rec.get('media_id'):
            continue
        try:
            made = datetime.strptime(rec['id'][:13], '%Y%m%d-%H%M').replace(tzinfo=JST)
        except ValueError:
            continue
        if made < since:
            continue
        try:
            r = call('GET', f"{API}/{rec['media_id']}/insights", {'metric': 'views,likes,replies,reposts,quotes', 'access_token': tok})
            out['posts'][rec['id']] = {m['name']: (m.get('values') or [{}])[0].get('value', m.get('total_value', {}).get('value')) for m in r.get('data', [])}
        except Exception as e:
            print(f"::warning::{rec['id']} の数字は読めませんでした: {str(e).replace(tok, '***')[:120]}")
    json.dump(out, open(os.path.join(ROOT, 'state', 'insights.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # 日ごとの記録（ダッシュボードと投稿時間の調整に使う）。60日分だけ残す
    log_p = os.path.join(ROOT, 'state', 'insights_log.json')
    log = json.load(open(log_p, encoding='utf-8')) if os.path.exists(log_p) else {}
    log[out['at'][:10]] = {'account': out['account'], 'posts': out['posts']}
    log = dict(sorted(log.items())[-60:])
    json.dump(log, open(log_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"::notice::数字を保存しました（投稿{len(out['posts'])}件・フォロワー{out['account'].get('followers_count')}）")


def comments():
    """直近7日の投稿に来たコメントのうち、まだ自分が返していないものを state/comments.json に保存する。"""
    tok, me = token()
    mine = me.get('username')
    since = datetime.now(JST) - timedelta(days=7)
    todo, fails, ok = [], [], 0
    skip = replied_ids()  # 返信済みが API にまだ反映されていなくても出さない
    for f in sorted(glob.glob(os.path.join(ROOT, 'state', 'posted', '*.json'))):
        rec = json.load(open(f, encoding='utf-8'))
        try:
            made = datetime.strptime(rec['id'][:13], '%Y%m%d-%H%M').replace(tzinfo=JST)
        except (ValueError, KeyError):
            continue
        if not rec.get('media_id') or made < since:
            continue
        try:
            r = call('GET', f"{API}/{rec['media_id']}/replies", {'fields': 'id,text,username,timestamp,permalink,has_replies', 'access_token': tok})
        except Exception as e:
            fails.append(rec['id'])
            print(f"::warning::{rec['id']} のコメントを読めません: {str(e).replace(tok, '***')[:200]}")
            continue
        ok += 1
        for c in r.get('data', []):
            if c.get('username') == mine:
                continue
            answered = False
            F = 'id,text,username,timestamp,permalink,has_replies'
            if c.get('has_replies'):
                try:
                    rr = call('GET', f"{API}/{c['id']}/replies", {'fields': F, 'access_token': tok})
                    answered = any(x.get('username') == mine for x in rr.get('data', []))
                    # 返信の返信（こちらの返信にさらにコメントが来た分）も拾う
                    for x in rr.get('data', []):
                        if x.get('username') != mine or not x.get('has_replies'):
                            continue
                        r3 = call('GET', f"{API}/{x['id']}/replies", {'fields': F, 'access_token': tok})
                        for y in r3.get('data', []):
                            if y.get('username') == mine or str(y['id']) in skip:
                                continue
                            done = False
                            if y.get('has_replies'):
                                r4 = call('GET', f"{API}/{y['id']}/replies", {'fields': 'username', 'access_token': tok})
                                done = any(z.get('username') == mine for z in r4.get('data', []))
                            if not done:
                                todo.append({'id': y['id'], 'post': rec['id'], 'user': y.get('username'), 'text': y.get('text', ''), 'at': y.get('timestamp'), 'link': y.get('permalink'), 'thread': (c.get('text') or '')[:80]})
                except Exception:
                    pass
            if not answered and str(c['id']) not in skip:
                todo.append({'id': c['id'], 'post': rec['id'], 'user': c.get('username'), 'text': c.get('text', ''), 'at': c.get('timestamp'), 'link': c.get('permalink')})
    if fails and not ok:
        print('::error::どの投稿のコメントも読めません（threads_read_replies の許可が入ったトークンが必要）')
        raise SystemExit(1)
    out = {'at': datetime.now(JST).isoformat(timespec='minutes'), 'unanswered': todo}
    json.dump(out, open(os.path.join(ROOT, 'state', 'comments.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"::notice::返信待ちのコメント {len(todo)}件")


# 他の人のThreads投稿から、楽天ROOM・ガジェット系で伸びている投稿を集める（ルイの情報収集用）
# threads_keyword_search の審査が通るまでは、自分の投稿しか返ってこない（それで正常）
WORDS = [('楽天ROOM', 'KEYWORD'), ('楽天ルーム', 'KEYWORD'), ('楽天ROOM', 'TAG'), ('楽天アフィリエイト', 'KEYWORD'), ('買ってよかった', 'KEYWORD'), ('ガジェット', 'TAG')]


def search():
    tok, me = token()
    print(f"::notice::使ったトークン：{'GitHubに貼ったもの' if os.environ.get('TOKEN_SRC') == 'secret' else '保存済みの古いもの'}（長さ{len(tok)}）")
    mine = me.get('username')
    since = int((datetime.now(JST) - timedelta(days=3)).timestamp())
    found, seen, fails = [], set(), []
    for q, mode in WORDS:
        try:
            r = call('GET', f'{API}/keyword_search', {'q': q, 'search_type': 'TOP', 'search_mode': mode, 'since': since, 'limit': 25,
                                                    'fields': 'id,text,media_type,permalink,timestamp,username,has_replies,is_reply', 'access_token': tok})
        except Exception as e:
            fails.append(q)
            print(f"::warning::「{q}」を検索できません: {str(e).replace(tok, '***')[:200]}")
            continue
        for x in r.get('data', []):
            if x['id'] in seen or x.get('is_reply'):
                continue
            seen.add(x['id'])
            found.append({'q': q, 'mode': mode, 'user': x.get('username'), 'mine': x.get('username') == mine, 'text': (x.get('text') or '')[:400],
                          'type': x.get('media_type'), 'at': x.get('timestamp'), 'link': x.get('permalink')})
    others = sum(1 for f in found if not f['mine'])
    out = {'at': datetime.now(JST).isoformat(timespec='minutes'), 'approved': others > 0, 'posts': found}
    json.dump(out, open(os.path.join(ROOT, 'state', 'search.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"::notice::検索 {len(found)}件（他の人の投稿 {others}件）")
    if fails and len(fails) == len(WORDS):
        # 許可待ちのあいだは毎日失敗通知が届かないよう、知らせるだけで終える
        print('::notice::検索の許可がまだ有効になっていません（threads_keyword_search）')


def delete():
    """DELETE_ID の投稿を Threads から削除する（言葉選びが悪かった投稿の出し直し用）"""
    mid = os.environ.get('DELETE_ID', '').strip()
    if not mid.isdigit():
        raise SystemExit('削除する投稿のidがありません')
    tok, _ = token()
    try:
        call('DELETE', f'{API}/{mid}', {'access_token': tok})
    except Exception as e:
        print(f"::error::削除できませんでした: {str(e).replace(tok, '***')[:200]}")
        raise SystemExit(1)
    for f in glob.glob(os.path.join(ROOT, 'state', 'posted', '*.json')):
        rec = json.load(open(f, encoding='utf-8'))
        if rec.get('media_id') == mid:
            rec['deleted'] = datetime.now(JST).isoformat(timespec='minutes')
            json.dump(rec, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{mid} を削除しました')


def oauth():
    """許可コード（CODE）からトークンを作って暗号化して保存する。スマホでトークン生成ツールが使えないとき用。"""
    code, app = os.environ.get('CODE', '').strip().replace('#_', ''), os.environ.get('APP_ID', '').strip()
    if not (code and app and SECRET):
        raise SystemExit('コード・アプリID・鍵のどれかがありません')
    r = call('POST', 'https://graph.threads.net/oauth/access_token', {'client_id': app, 'client_secret': SECRET, 'code': code,
                                                                     'grant_type': 'authorization_code', 'redirect_uri': 'https://tatuya-st.github.io/threads-auto/callback.html'})
    tok = r['access_token']
    tok = call('GET', 'https://graph.threads.net/access_token', {'grant_type': 'th_exchange_token', 'client_secret': SECRET, 'access_token': tok})['access_token']
    me = works(tok)
    if not me:
        raise SystemExit('作ったトークンが使えません')
    encrypt(tok)
    print(f"::notice::トークンを作り直しました（{me.get('username')}・60日有効、毎週自動で延長）")


if __name__ == '__main__':
    {'oauth': oauth, 'publish': publish, 'refresh': refresh, 'insights': insights, 'comments': comments, 'search': search, 'delete': delete}[sys.argv[1] if len(sys.argv) > 1 else 'publish']()
