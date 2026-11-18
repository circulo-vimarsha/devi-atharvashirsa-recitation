#!/usr/bin/env python3
"""Time every word of private/text.json in a continuous recitation, and write private/timing.json.

    python3 tools/align.py <recording> [--who NAME] [--from-verse N] [--start SECONDS] [--report report.txt]

No speech recognition: the reciter breathes between phrases, so the recording falls into
sound phrases separated by short silences. A dynamic programme shares the words out among
those phrases so that each phrase is chanted at a steady pace (syllables per second), with
phrases preferring to end where a line or a daṇḍa ends. Inside a phrase the words get time
in proportion to their syllables, and each boundary is moved to the quietest moment nearby.
Only the standard library and GStreamer (gst-launch-1.0, to decode) are needed."""
import array, json, math, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RATE, HOP = 16000, 160          # 10 ms frames

C = '[क-हक़-य़ॸ-ॿ]'; NUK = '़?'; VIR = '्'
SIGN = '[ा-ौॕ-ॗॢॣ]'; MARK = '[ऀ-ः]'
VOW = '[ऄ-औॠॡॲ-ॷ]'
AKSHARA = re.compile(f'(?:{C}{NUK}{VIR})*{C}{NUK}(?:{VIR}|{SIGN})?{MARK}*|{VOW}{MARK}*|ॐ')
LONG = set('ािीूॄेैोौॆॊ') | set('आईऊॠएऐओऔ')


def weight(word):
    """syllables, a heavy one (long vowel, anusvāra, visarga, before a cluster) counting 1.5"""
    aks = [a for a in AKSHARA.findall(word)]
    w = 0.0
    for i, a in enumerate(aks):
        if a.endswith(VIR):
            continue
        heavy = any(ch in LONG for ch in a) or any(ch in 'ंःँ' for ch in a)
        nxt = aks[i + 1] if i + 1 < len(aks) else ''
        if VIR in nxt or nxt.endswith(VIR):
            heavy = True
        w += 1.5 if heavy else 1.0
    return max(w, 1.0)


def envelope(path):
    with tempfile.NamedTemporaryFile(suffix='.raw') as tmp:
        subprocess.run(['gst-launch-1.0', '-q', 'filesrc', f'location={path}', '!', 'decodebin', '!',
                        'audioconvert', '!', 'audioresample', '!',
                        f'audio/x-raw,format=S16LE,channels=1,rate={RATE}', '!', 'filesink', f'location={tmp.name}'],
                       check=True)
        a = array.array('h'); a.frombytes(Path(tmp.name).read_bytes())
    db = []
    for i in range(0, len(a) - HOP, HOP):
        s = a[i:i + HOP]
        db.append(20 * math.log10(math.sqrt(sum(x * x for x in s) / HOP) + 1))
    return [sum(db[max(0, i - 2):i + 3]) / len(db[max(0, i - 2):i + 3]) for i in range(len(db))]


def phrases(env, thr=55.0, gap=0.15, shortest=0.35):
    """sound stretches between silences of at least `gap` s; crumbs shorter than `shortest` join a neighbour"""
    out, i, n = [], 0, len(env)
    while i < n:
        if env[i] >= thr:
            j = i
            while j < n:
                if env[j] < thr:
                    k = j
                    while k < n and env[k] < thr:
                        k += 1
                    if (k - j) / 100 >= gap or k == n:
                        break
                    j = k
                else:
                    j += 1
            out.append([i / 100, j / 100])
            i = j
        else:
            i += 1
    merged = []
    for k, (a, b) in enumerate(out):
        if b - a < shortest:
            nxt = out[k + 1][0] - b if k + 1 < len(out) else 9
            if merged and a - merged[-1][1] < 0.6 and a - merged[-1][1] <= nxt:
                merged[-1][1] = b; continue
            if nxt < 0.6:
                out[k + 1][0] = a; continue
            continue   # a lone click or a murmur in a long silence: not chant
        merged.append([a, b])
    if len(merged) > 1 and merged[0][1] - merged[0][0] < shortest:
        merged[1][0] = merged[0][0]; merged.pop(0)
    return merged


def words_of(text, from_verse):
    ws = []
    for v in text['verses']:
        if v['n'] < from_verse:
            continue
        for li, line in enumerate(v['lines']):
            ps = line['pieces']
            idx = [k for k, p in enumerate(ps) if 'w' in p]
            for j, k in enumerate(idx):
                last = j == len(idx) - 1
                stop = last or any('p' in p for p in ps[k + 1:idx[j + 1]])   # a daṇḍa or the line's end follows
                ws.append({'v': v['n'], 'l': li, 'w': ps[k]['i'], 'deva': ps[k]['w'],
                           'wt': weight(ps[k]['w']) + (0.8 if last else 0), 'stop': stop, 'eol': last})
    return ws


def align(ws, ph, rate):
    """dp[p][n]: best cost for phrases[:p] holding words[:n]"""
    P, N, INF, MAXW, SKIP = len(ph), len(ws), float('inf'), 40, 6.0
    cum = [0.0]
    for w in ws:
        cum.append(cum[-1] + w['wt'])
    dp = [[INF] * (N + 1) for _ in range(P + 1)]
    back = [[0] * (N + 1) for _ in range(P + 1)]
    dp[0][0] = 0.0
    for p in range(1, P + 1):
        dp[p][0], back[p][0] = dp[p - 1][0] + SKIP, (0, 1)
        for n in range(1, N + 1):
            end = ws[n - 1]
            endpen = 0.0 if end['eol'] else (0.4 if end['stop'] else 2.5)
            best, arg = INF, (0, 0)
            for k in (1, 2):   # a group of words in one phrase, or across two (a breath inside a line)
                if p - k < 0:
                    continue
                dur = sum(b - a for a, b in ph[p - k:p])
                for m in range(max(0, n - MAXW), n):
                    if dp[p - k][m] == INF:
                        continue
                    W = cum[n] - cum[m]
                    eols = sum(1 for j in range(m, n - 1) if ws[j]['eol'])   # lines run together without a breath
                    c = (dp[p - k][m] + math.sqrt(W) * math.log(dur / (W / rate)) ** 2 + endpen
                         + 0.25 * eols + (1.2 if k == 2 else 0) + (3 if k == 2 and n - m < 2 else 0))
                    if c < best:
                        best, arg = c, (m, k)
            if dp[p - 1][n] + SKIP < best:   # a phrase that is not in the text (an invocation, a cough)
                best, arg = dp[p - 1][n] + SKIP, (n, 1)
            dp[p][n], back[p][n] = best, arg
    if dp[P][N] == INF:
        raise SystemExit('no alignment: more phrases than words?')
    cuts, n, p = [], N, P
    while p > 0:
        m, k = back[p][n]; cuts.append((m, n, p - k, p)); n, p = m, p - k
    return dp[P][N], cuts[::-1]


def quietest(env, t, span=0.25):
    i0, i1 = max(0, int((t - span) * 100)), min(len(env) - 1, int((t + span) * 100))
    k = min(range(i0, i1 + 1), key=lambda i: env[i] + abs(i / 100 - t) * 8)   # quiet, and not far
    return k / 100


def main():
    rec = Path(sys.argv[1]).expanduser()
    arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
    text = json.loads((ROOT / 'private/text.json').read_text())
    ws = words_of(text, int(arg('--from-verse', 0)))
    env = envelope(rec)
    ph = [x for x in phrases(env) if x[0] >= float(arg('--start', 0))]   # what comes before the text begins
    total = sum(w['wt'] for w in ws)
    rate = total / sum(b - a for a, b in ph)
    cost, cuts = None, None
    for _ in range(4):   # the pace the alignment finds, fed back
        cost, cuts = align(ws, ph, rate)
        rate = sum(sum(w['wt'] for w in ws[m:n]) for m, n, _, _ in cuts) / sum(ph[p1 - 1][1] - ph[p0][0] for m, n, p0, p1 in cuts if n > m)
    out, report = [], []
    for m, n, p0, p1 in cuts:
        if m == n:
            report.append(f'{ph[p0][0]:7.2f}-{ph[p1 - 1][1]:7.2f}  (not in the text)'); continue
        spans = ph[p0:p1]; a, b = spans[0][0], spans[-1][1]
        W = sum(w['wt'] for w in ws[m:n]); sound = sum(y - x for x, y in spans)

        def clock(x):   # x seconds of sound into the group → time in the recording, skipping the breath
            for s0, s1 in spans:
                if x <= s1 - s0:
                    return s0 + x
                x -= s1 - s0
            return b
        bounds, acc = [a], 0.0
        for w in ws[m:n - 1]:
            acc += sound * w['wt'] / W
            bounds.append(quietest(env, clock(acc)))
        bounds.append(b)
        for w, t0, t1 in zip(ws[m:n], bounds, bounds[1:]):
            out.append({'v': w['v'], 'l': w['l'], 'w': w['w'], 't0': round(t0, 2), 't1': round(t1, 2)})
        report.append(f'{a:7.2f}-{b:7.2f}  {W / sound:4.1f}/s {"+" if p1 - p0 > 1 else " "} ' + ' '.join(w['deva'] for w in ws[m:n]))
    timing = {'audio': 'audio/recitation.mp3', 'who': arg('--who', ''), 'words': out,
              'verses': sorted({w['v'] for w in out})}
    (ROOT / 'private/timing.json').write_text(json.dumps(timing, ensure_ascii=False, separators=(',', ':')))
    if arg('--report'):
        Path(arg('--report')).write_text('\n'.join(report) + '\n')
    print(f'{len(ph)} phrases, {len(ws)} words, pace {rate:.2f} weight/s, cost {cost:.1f}')


if __name__ == '__main__':
    main()
