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


class LimitHit(RuntimeError):
    """Threadsの書き込み上限（429）。その日の書き込みは止める（連打・別ルートでの回避はしない）"""


LIMIT_P = os.path.join(ROOT, 'state', 'limit.json')


def limited_today():
    try:
        return json.load(open(LIMIT_P, encoding='utf-8')).get('date') == datetime.now(JST).strftime('%Y-%m-%d')
    except Exception:
        return False


STATUS_P = os.path.join(ROOT, 'state', 'status.txt')


def night_info(now, handed):
    """ルイの今夜の商品投稿がどうなっているかを、レイに伝える（マスターの中継なし）"""
    day = now.strftime('%Y%m%d')
    fs = sorted(glob.glob(os.path.join(ROOT, 'queue', day + '-*-night.json')))
    line = 'まだ（マスターの「OK」が出てから投稿します）'
    if handed:
        line = 'ボツになりました。今夜の商品投稿はレイが出してください（リンクもレイが使ってよい）'
    elif fs:
        q = json.load(open(fs[-1], encoding='utf-8'))
        pp = os.path.join(ROOT, 'state', 'posted', os.path.basename(fs[-1]))
        nm = (q.get('items') or [{}])[0].get('name', '')[:25]
        if os.path.exists(pp):
            r = json.load(open(pp, encoding='utf-8'))
            line = ('ボツ・削除しました' if r.get('deleted') else '投稿しました') + (f'（{nm}）' if nm else '')
        else:
            line = 'マスターの確認待ち' + (f'（{nm}）' if nm else '')
    return f"\n■ルイの今夜の商品投稿\n・{line}\n"


def room_info(now):
    """11/03 マスター指示：レイにも楽天ROOMの情報を渡す（セール日程・売れ筋・出した商品・ROOMの入口）"""
    def load(n, d):
        try:
            return json.load(open(os.path.join(ROOT, 'state', n), encoding='utf-8'))
        except Exception:
            return d
    r = load('research.json', {})
    out = ["\n■楽天ROOMの情報（ルイが自動で更新）",
           "・ROOM：https://room.rakuten.co.jp/room_a9a129c5a9/items",
           "・コレクション：https://room.rakuten.co.jp/room_a9a129c5a9/collections"]
    sales = []
    for s in r.get('sales', []):
        try:
            st, en = datetime.fromisoformat(s['s']).replace(tzinfo=JST), datetime.fromisoformat(s['e']).replace(tzinfo=JST)
        except Exception:
            continue
        if en >= now and st <= now + timedelta(days=7):
            sales.append(f"{s['label']} {st.strftime('%m/%d %H:%M')}〜{en.strftime('%m/%d %H:%M')}" + ('（開催中）' if st <= now else ''))
    if sales:
        out.append('・7日以内のセール：' + ' ／ '.join(sales[:5]))
    if r.get('hot_words'):
        out.append('・今売れ筋の種類：' + '、'.join(r['hot_words'][:10]))
    sent = load('sent.json', {})
    gone = lambda v: load(os.path.join('posted', (v.get('post') or '') + '.json'), {}).get('deleted')
    recent = sorted((v for v in sent.values() if isinstance(v, dict) and v.get('at') and not gone(v)), key=lambda v: v['at'], reverse=True)[:5]
    if recent:
        out.append('・ルイがThreadsに出した商品（同じ商品は出さないでください）：' + ' ／ '.join(v['name'][:25] for v in recent))
    return '\n'.join(out) + '\n'


def write_status():
    """レイが書き込み前に見る今日の合図（https://tatuya-st.github.io/threads-auto/state/status.txt）"""
    now = datetime.now(JST)
    stop = limited_today()
    who = 'ルイ' if now.day % 2 else 'レイ'
    try:  # 11/03：ルイの商品投稿がボツになった日は、その日のリンクと夜の商品投稿をレイに渡す
        hand = json.load(open(os.path.join(ROOT, 'state', 'handover.json'), encoding='utf-8'))
    except Exception:
        hand = {}
    today = now.strftime('%Y-%m-%d')
    if today in hand:
        who = f"レイ（{hand[today]}）"
    txt = (f"日付：{now.strftime('%Y-%m-%d')}（日本時間）\n"
           f"書き込み：{'止める（Threadsの書き込み上限が出たため、今日は投稿も返信もしない）' if stop else 'OK'}\n"
           f"今日のリンク：{who}\n"
           f"更新：{now.strftime('%H:%M')}\n")
    try:  # ルイからレイへの連絡（マスターの中継なしで届ける）
        note = open(os.path.join(ROOT, 'state', 'to_rei.txt'), encoding='utf-8').read().strip()
    except OSError:
        note = ''
    if note:
        txt += f"\n■ルイからレイへの連絡\n{note}\n"
    txt += night_info(now, today in hand)
    txt += room_info(now)
    open(STATUS_P, 'w', encoding='utf-8').write(txt)


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
            if e.code == 429 and method == 'POST':
                # 書き込みの上限：やり直さず、今日はもう書き込まない（レイにも伝えるため記録する）
                os.makedirs(os.path.dirname(LIMIT_P), exist_ok=True)
                json.dump({'date': datetime.now(JST).strftime('%Y-%m-%d'), 'at': datetime.now(JST).isoformat(timespec='minutes')},
                          open(LIMIT_P, 'w', encoding='utf-8'), ensure_ascii=False)
                write_status()
                raise LimitHit(f'書き込み上限(429) {body[:200]}')
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
    # 保存済み（作り直した）トークンを優先。Secrets は貼り直されたときだけ先に試す（古いトークンで上書きしないように）
    import hashlib
    sec = os.environ.get('THREADS_TOKEN', '').strip()
    seen_p = os.path.join(ROOT, 'state', 'secret_seen.txt')
    h = hashlib.sha256(sec.encode()).hexdigest()[:16] if sec else ''
    seen = open(seen_p).read().strip() if os.path.exists(seen_p) else None
    if seen is None and h:
        open(seen_p, 'w').write(h)
        seen = h
    fresh = bool(h) and h != seen
    tries = [('secret', sec), ('saved', decrypt())] if fresh else [('saved', decrypt()), ('secret', sec)]
    for src, tok in tries:
        if not tok:
            continue
        me = works(tok)
        if not me:
            continue
        if src == 'secret' and fresh and h:
            open(seen_p, 'w').write(h)
        if src == 'secret' and SECRET and fresh:
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
                if it.get('replace_link'):
                    # 11/04 マスター指示：ROOMのトップに飛ぶ古いリンク返信を消し、商品ページに直接飛ぶリンクに差し替える
                    old = call('GET', f"{API}/{it['to']}/replies", {'fields': 'id,text,username', 'access_token': tok})
                    for x in old.get('data', []):
                        if x.get('username') == me.get('username') and 'room.rakuten.co.jp' in (x.get('text') or ''):
                            call('DELETE', f"{API}/{x['id']}", {'access_token': tok})
                            print('古いリンク返信を消しました')
                    time.sleep(5)
                cid = call('POST', f"{API}/{me['id']}/threads", {'media_type': 'TEXT', 'text': it['text'], 'reply_to_id': it['to'], 'access_token': tok})['id']
                time.sleep(3)
                mid = call('POST', f"{API}/{me['id']}/threads_publish", {'creation_id': cid, 'access_token': tok})['id']
                rec['done'].append({'to': it['to'], 'reply_id': mid})
                done_to.add(str(it['to']))
            except Exception as e:
                msg = str(e).replace(tok, '***')[:200]
                rec['ng'].append({'to': it.get('to'), 'error': msg})
                if isinstance(e, LimitHit):
                    print('::error::書き込み上限が出たため、今日の返信はここで止めます')
                    break
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
            if (r.get('reply') == 'ok' or r.get('link') == 'ok' or r.get('boost') == 'link') and (r.get('link_at') or r.get('at')):
                t = datetime.fromisoformat(r.get('link_at') or r['at'])  # あとから付けたリンクは付けた時刻で数える
                last = t if last is None or t > last else last
        except Exception:
            pass
    return last


def thin_link(q):
    """直近にリンクを貼っていたら、今回はリンク返信を付けずプロフィール案内にする（PR表記は残す）"""
    last = last_link_at()
    # レイ（別のAI）とリンク枠を分け合う：奇数日＝ルイ、偶数日＝レイ（日本時間）。
    # 偶数日はルイはリンクを付けない。state/link_off.json の日付も臨時で付けない日にできる
    try:
        off = json.load(open(os.path.join(ROOT, 'state', 'link_off.json'), encoding='utf-8'))
    except Exception:
        off = []
    today = datetime.now(JST)
    try:
        hand = json.load(open(os.path.join(ROOT, 'state', 'handover.json'), encoding='utf-8'))
    except Exception:
        hand = {}
    blocked = today.day % 2 == 0 or today.strftime('%Y-%m-%d') in off or today.strftime('%Y-%m-%d') in hand
    if q.get('master_link'):  # マスターが「リンク付きで」と明示した投稿は、日付の割り当てより優先する
        blocked = False
        last = None
    has_link = 'http' in (q.get('text') or '') or 'http' in (q.get('reply') or '')
    if not has_link or (not blocked and (not last or datetime.now(JST) - last >= timedelta(hours=LINK_GAP_H))):
        return q
    if 'http' in (q.get('text') or ''):  # 11/05：売る投稿はリンクが本文（1通目）。リンクを付けない日は本文からURLの行だけ外す
        tl = [l for l in q['text'].split('\n') if 'http' not in l and '見られます👇' not in l]
        q = dict(q, text='\n'.join(tl + ['楽天ROOMはプロフィールのリンクから📌']), _nolink=True)
        print(f"{q.get('id')} は今日リンクを付けない日のため、本文にURLを入れない")
        if 'http' not in (q.get('reply') or ''):
            return q
    # 商品名は返信に残し、URLの行だけ外す（リンクはプロフィールへ）
    lines = [l for l in q['reply'].split('\n') if 'http' not in l and 'ここからどうぞ' not in l and 'ここから見られます' not in l]
    q = dict(q, reply='\n'.join(lines + ['楽天ROOMはプロフィールのリンクから📌']), _nolink=True)
    q['text'] = (q.get('text') or '').replace('【PR】返信に楽天ROOMのリンクがあります', '【PR】楽天ROOMはプロフィールのリンクから')
    print(f"{q.get('id')} は直近にリンクを貼ったため、今回は返信にURLを付けない")
    return q


def publish():
    repo = os.environ['GITHUB_REPOSITORY']
    todo = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'queue', '*.json'))):
        qid = os.path.splitext(os.path.basename(f))[0]
        if not os.path.exists(os.path.join(ROOT, 'state', 'posted', qid + '.json')):
            q_ = json.load(open(f, encoding='utf-8'))
            if q_.get('hold'):  # マスターの画像待ち。届くまで出さない
                print(f'{qid} はマスターの画像待ちなので出しません')
                continue
            todo.append((qid, q_))
    has_rep = any(not os.path.exists(os.path.join(ROOT, 'state', 'replied', os.path.basename(f)))
                  for f in glob.glob(os.path.join(ROOT, 'queue', 'replies', '*.json')))
    if not todo and not has_rep:
        print('公開待ちなし')
        return
    if limited_today():
        print('今日はThreadsの書き込み上限が出たため、投稿も返信もしません（明日から再開）')
        return
    tok, me = token()
    rep_ok = send_replies(tok, me) if has_rep and not limited_today() else True
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
        if limited_today():
            print(f'{qid} は書き込み上限のため出しません')
            break
        if not remote_has(f'queue/{qid}.json'):  # 11/03：マスターの「ボツ」で queue から消された投稿は出さない
            print(f'{qid} はボツで取り消されたので出しません')
            continue
        if remote_has(f'state/posted/{qid}.json'):
            print(f'{qid} はほかの実行で公開済みなので出しません')
            continue
        q = thin_link(q)
        # 二重投稿の最終チェック：すでに Threads に出した商品が入っていたら公開しない
        # 商品つきの投稿には必ずPR表記を入れる（ステマ規制対策）
        # 11/05 レイ決定：PR表記は【PR】に統一（※PR は使わない）。ROOM全体への誘導投稿も同じ
        for k in ('text', 'reply'):
            if q.get(k):
                q[k] = q[k].replace('※PR：', '【PR】').replace('※PR\n', '【PR】').replace('※PR', '【PR】')
        if q.get('items') and '【PR】' not in (q.get('text') or ''):
            q['text'] = '【PR】' + (q.get('text') or '').lstrip()
        if 'http' in (q.get('reply') or '') and '【PR】' not in q['reply']:
            q['reply'] = '【PR】' + q['reply'].lstrip()
        # 同じ商品コードに加え、同じ商品名も二度と出さない（楽天の「同じSNSで同じ商品は1回まで」対策）
        nm = lambda s: ''.join((s or '').split()).lower()
        sent_names = {nm(v.get('name')) for v in sent.values() if isinstance(v, dict)}
        dup = [it['itemcode'] for it in q['items'] if it['itemcode'] in sent or nm(it.get('name')) in sent_names]
        rec = {'id': qid, 'axis': q.get('axis'), 'theme': q.get('theme'), 'codes': [it['itemcode'] for it in q['items']]}
        try:
            made = datetime.strptime(qid[:13], '%Y%m%d-%H%M').replace(tzinfo=JST)
        except ValueError:
            made = datetime.now(JST)
        if q.get('released'):  # マスターの画像を待ってから出す投稿は、出してよくなった時刻から数える
            try:
                made = datetime.fromisoformat(q['released'])
            except ValueError:
                pass
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
              pic = q.get('kind') != 'talk' or q.get('image')  # 会話投稿でも image:true なら画像つき
              if not pic:
                  params = {'media_type': 'TEXT', 'text': q['text'], 'access_token': tok}
              else:
                  img = f'https://raw.githubusercontent.com/{repo}/{sha}/images/{qid}.png'
                  params = {'media_type': 'IMAGE', 'image_url': img, 'text': q['text'], 'access_token': tok}
                  if os.path.exists(os.path.join(ROOT, 'images', qid + '_2.png')):
                      # 2枚投稿（カルーセル）：1枚ずつ準備してから、まとめて1本にする
                      kids = []
                      for nm2 in (qid, qid + '_2'):
                          u = f'https://raw.githubusercontent.com/{repo}/{sha}/images/{nm2}.png'
                          k = call('POST', f"{API}/{me['id']}/threads", {'media_type': 'IMAGE', 'image_url': u, 'is_carousel_item': 'true', 'access_token': tok})['id']
                          wait_ready(k, tok)
                          kids.append(k)
                      params = {'media_type': 'CAROUSEL', 'children': ','.join(kids), 'text': q['text'], 'access_token': tok}
              if q.get('topic'):
                  params['topic_tag'] = q['topic']
              cid = call('POST', f"{API}/{me['id']}/threads", params)['id']
              if pic:
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
              if 'http' in q['text']:
                  rec['link'] = 'ok'  # 11/05：本文（1通目）にリンクを入れた記録（1日1回の決まりに数える）
              # リンクは本文ではなく自分の返信に付ける（失敗しても投稿本体はそのまま）
              if q.get('reply'):
                  try:
                      time.sleep(20)
                      rid = call('POST', f"{API}/{me['id']}/threads", {'media_type': 'TEXT', 'text': q['reply'], 'reply_to_id': mid, 'access_token': tok})['id']
                      time.sleep(3)
                      call('POST', f"{API}/{me['id']}/threads_publish", {'creation_id': rid, 'access_token': tok})
                      rec['reply'] = 'ok' if 'http' in q['reply'] else 'nolink'
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
            if isinstance(e, LimitHit):
                rec['skipped'] = '書き込み上限(429)のため今日は止めた'
                print('::error::Threadsの書き込み上限が出ました。今日の書き込みは止めます')
            print(f'::error::{qid} を投稿できませんでした: {msg}')
        os.makedirs(os.path.join(ROOT, 'state', 'posted'), exist_ok=True)
        json.dump(rec, open(os.path.join(ROOT, 'state', 'posted', qid + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        json.dump(sent, open(sent_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(qid, rec.get('permalink') or rec.get('skipped'))
    if failed or not rep_ok:
        raise SystemExit(1)


def save_rei_posts(tok, me):
    """同じアカウントでルイが出していない投稿＝レイの投稿。話題かぶりを避けるため直近3日分を state/rei_posts.json に残す
    （マスターがルイの投稿をレイに、レイの投稿をルイに中継しなくて済むように）"""
    mine = set()
    for f in glob.glob(os.path.join(ROOT, 'state', 'posted', '*.json')):
        try:
            mine.add(str(json.load(open(f, encoding='utf-8')).get('media_id')))
        except Exception:
            pass
    try:
        r = call('GET', f"{API}/{me['id']}/threads", {'fields': 'id,text,timestamp,permalink', 'limit': 50, 'access_token': tok})
    except Exception as e:
        print(f"::warning::レイの投稿を読めませんでした: {str(e).replace(tok, '***')[:150]}")
        return
    since = datetime.now(JST) - timedelta(days=3)
    rei = []
    for x in r.get('data', []):
        try:
            t = datetime.strptime(x['timestamp'], '%Y-%m-%dT%H:%M:%S%z').astimezone(JST)
        except (KeyError, ValueError):
            continue
        if str(x.get('id')) in mine or t < since:
            continue
        rei.append({'at': t.isoformat(timespec='minutes'), 'text': (x.get('text') or '')[:300], 'link': x.get('permalink')})
    json.dump({'at': datetime.now(JST).isoformat(timespec='minutes'), 'posts': rei},
              open(os.path.join(ROOT, 'state', 'rei_posts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"::notice::レイの投稿（直近3日）{len(rei)}件を記録")


ROOM_COLS = 'https://room.rakuten.co.jp/room_a9a129c5a9/collections'
# 伸びた投稿へのあとがけ返信。話題ごとに言い方を変え、同じ文が続かないようにする
BOOST_LINK = [
    (r'顔|洗面|お湯|水|歯|口|風呂', '【PR】洗面所まわりで実際に使ってるもの、楽天ROOMに置いてます。のぞくだけでもどうぞ\n'),
    (r'スマホ|iPhone|充電|ケース|アプリ|電池', '【PR】スマホまわりで買ってよかった小物、楽天ROOMにまとめてます\n'),
    (r'寒|冬|暖|加湿|コート|布団|毛布', '【PR】冬支度で買ったもの・迷ってるもの、楽天ROOMに並べてます\n'),
    (r'', '【PR】このへんの話で気になってるもの、楽天ROOMにまとめてます\n'),
]
BOOST_PROF = [
    (r'顔|洗面|お湯|水|歯|口|風呂', '【PR】洗面所まわりで使ってるものは、プロフィールの楽天ROOMに置いてます🧴'),
    (r'スマホ|iPhone|充電|ケース|アプリ|電池', '【PR】スマホまわりの小物は、プロフィールの楽天ROOMにまとめてます📱'),
    (r'寒|冬|暖|加湿|コート|布団|毛布', '【PR】冬支度のものは、プロフィールの楽天ROOMに並べてます🧣'),
    (r'', '【PR】気になってるものは、プロフィールの楽天ROOMにまとめてます📌'),
]


def boost(tok, me, posts):
    """11/06：30日で閲覧1.4万人に対しプロフィールのリンクは29クリック。伸びた投稿にROOMへの道がなかったのが原因。
    直近30時間のルイの投稿でいちばん見られているもの（閲覧200以上）に、あとから自分の返信でROOMへの道を付ける。
    ・ルイのリンクの日（奇数日）で20時間あいていれば、URL付き（その日のリンク1回分に数える）
    ・それ以外の日はURLなしで「プロフィールの楽天ROOM」へ案内（レイのリンク枠は使わない）。1日1本まで"""
    if limited_today():
        return
    now = datetime.now(JST)
    today = now.strftime('%Y-%m-%d')
    recs = []
    for f in glob.glob(os.path.join(ROOT, 'state', 'posted', '*.json')):
        try:
            r = json.load(open(f, encoding='utf-8'))
            recs.append((f, r))
        except Exception:
            pass
    if any((r.get('boost_at') or '')[:10] == today for _, r in recs):
        return  # 今日はもう付けた
    try:
        off = json.load(open(os.path.join(ROOT, 'state', 'link_off.json'), encoding='utf-8'))
    except Exception:
        off = []
    try:
        hand = json.load(open(os.path.join(ROOT, 'state', 'handover.json'), encoding='utf-8'))
    except Exception:
        hand = {}
    last = last_link_at()
    link_ok = now.day % 2 == 1 and today not in off and today not in hand and (not last or now - last >= timedelta(hours=LINK_GAP_H))
    best = None
    for f, r in recs:
        if not r.get('media_id') or not r.get('at') or r.get('boost') or r.get('reply') == 'ok' or r.get('link') == 'ok':
            continue
        try:
            if now - datetime.fromisoformat(r['at']) > timedelta(hours=30):
                continue
        except ValueError:
            continue
        v = (posts.get(r['id']) or {}).get('views') or 0
        if v >= 200 and (best is None or v > best[0]):
            best = (v, f, r)
    if not best:
        return
    v, f, r = best
    if not link_ok and r.get('reply'):
        return  # すでにプロフィール案内の返信が付いている投稿には重ねない
    try:
        q = json.load(open(os.path.join(ROOT, 'queue', r['id'] + '.json'), encoding='utf-8'))
        body = q.get('text') or ''
    except Exception:
        body = ''
    table = BOOST_LINK if link_ok else BOOST_PROF
    txt = next(t for k, t in table if _re.search(k, body))
    if link_ok:
        txt += ROOM_COLS
    try:
        rid = call('POST', f"{API}/{me['id']}/threads", {'media_type': 'TEXT', 'text': txt, 'reply_to_id': r['media_id'], 'access_token': tok})['id']
        time.sleep(3)
        call('POST', f"{API}/{me['id']}/threads_publish", {'creation_id': rid, 'access_token': tok})
    except Exception as e:
        print(f"::warning::伸びた投稿への返信は付けられませんでした: {str(e).replace(tok, '***')[:150]}")
        return
    r['boost'] = 'link' if link_ok else 'profile'
    r['boost_at'] = now.isoformat(timespec='minutes')
    if link_ok:
        r['link_at'] = r['boost_at']
    json.dump(r, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"::notice::{r['id']}（閲覧{v}）にROOMへの返信を付けました（{r['boost']}）")


def link_clicks(tok, me):
    """Threadsのリンクのクリック数（プロフィール・投稿のリンク）を読む。読めなくても他の処理は止めない"""
    try:
        r = call('GET', f"{API}/{me['id']}/threads_insights", {'metric': 'clicks', 'access_token': tok})
        out = {}
        for m in r.get('data', []):
            for x in m.get('link_total_values') or []:
                out[x.get('link_url', '?')] = x.get('value', 0)
        return out
    except Exception as e:
        print(f"::warning::クリック数は読めませんでした: {str(e).replace(tok, '***')[:120]}")
        return None


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
    out['clicks'] = link_clicks(tok, me)
    json.dump(out, open(os.path.join(ROOT, 'state', 'insights.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    try:
        boost(tok, me, out['posts'])
    except Exception as e:
        print(f"::warning::あとがけ返信でエラー: {str(e).replace(tok, '***')[:150]}")
    # 日ごとの記録（ダッシュボードと投稿時間の調整に使う）。60日分だけ残す
    save_rei_posts(tok, me)
    write_status()
    log_p = os.path.join(ROOT, 'state', 'insights_log.json')
    log = json.load(open(log_p, encoding='utf-8')) if os.path.exists(log_p) else {}
    log[out['at'][:10]] = {'account': out['account'], 'posts': out['posts'], 'clicks': out.get('clicks')}
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
    write_status()
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
