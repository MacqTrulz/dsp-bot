#!/usr/bin/env python3
"""
DSP Dünya Durumu bildirimcisi
-----------------------------
warframestat.us API'sinden Warframe dünya durumunu okur ve Discord webhook'ları
ile DSP sunucusundaki kanallara Türkçe bildirim gönderir.

  #baro-ki-teer        Baro yola çıkınca haber + gelince envanter (@Baro Ki'Teer)
  #sortie-archon       Günlük Sortie ve haftalık Archon Hunt (@Sortie/Archon)
  #void-fissure        Sürekli güncellenen tek bir fissure paneli (etiket yok)
  #nightwave-etkinlik  Yeni Nightwave görevleri (haftalıklarda @Nightwave)

Ayarlar ortam değişkenlerinden okunur (GitHub > Settings > Secrets/Variables):
  WH_BARO, WH_SORTIE, WH_FISSURE, WH_NIGHTWAVE   -> webhook URL'leri (SECRET)
  ROLE_BARO, ROLE_SORTIE, ROLE_NIGHTWAVE         -> etiketlenecek rol ID'leri
Sadece standart Python kütüphanesi kullanır.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = os.environ.get("API_BASE", "https://api.warframestat.us/pc")
STATE_FILE = Path(os.environ.get("STATE_FILE", Path(__file__).with_name("state.json")))
UA = "DSP-Dunya-Durumu/1.0 (Discord community notifier)"

GOLD, PURPLE, RED, CYAN = 0xD6B15A, 0x9D6BFF, 0xE3343C, 0x5EC8E6
FOOTER = {"text": "DSP · Dünya Durumu"}


# --------------------------------------------------------------------------- yardımcılar
def env(name):
    return (os.environ.get(name) or "").strip()


def ts(iso):
    """ISO tarih -> unix saniye."""
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def t(iso, style="R"):
    """Discord zaman etiketi: herkes kendi saat diliminde görür."""
    return f"<t:{ts(iso)}:{style}>"


def now():
    return int(time.time())


def http(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "User-Agent": UA, "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:  # Discord hız sınırı
                wait = float(json.loads(e.read() or b"{}").get("retry_after", 2))
                time.sleep(min(wait, 10))
                continue
            return e.code, None
        except Exception as e:  # ağ hatası
            print(f"  ! {method} {url.split('?')[0][:60]}: {e}")
            if attempt < 2:
                time.sleep(2)
                continue
            return 0, None
    return 0, None


def api(path):
    code, data = http("GET", f"{API}/{path}/?language=en")
    if code != 200 or data is None:
        print(f"  ! API okunamadı: {path} ({code})")
        return None
    return data


def send(hook, embeds, role=None):
    """Webhook'a mesaj gönderir, mesaj ID'sini döndürür."""
    if not hook:
        return None
    body = {"embeds": embeds, "allowed_mentions": {"parse": [], "roles": [role] if role else []}}
    if role:
        body["content"] = f"<@&{role}>"
    code, data = http("POST", hook + ("&" if "?" in hook else "?") + "wait=true", body)
    if code in (200, 204) and data:
        return data.get("id")
    print(f"  ! Discord'a gönderilemedi ({code})")
    return None


def edit(hook, msg_id, embeds):
    code, _ = http("PATCH", f"{hook.split('?')[0]}/messages/{msg_id}", {"embeds": embeds})
    return code == 200


def cut(text, limit=4000):
    return text if len(text) <= limit else text[: limit - 20].rsplit("\n", 1)[0] + "\n…"


# --------------------------------------------------------------------------- bölümler
def baro(state):
    hook, role = env("WH_BARO"), env("ROLE_BARO")
    vt = api("voidTrader")
    if not hook or not vt or not vt.get("id"):
        return
    vid, start, end = vt["id"], ts(vt["activation"]), ts(vt["expiry"])
    key = f"{vid}:{vt['activation']}"
    if now() < start and state.get("baro_upcoming") != key:
        emb = {"title": "🛒 Baro Ki'Teer yolda", "color": GOLD, "footer": FOOTER,
               "description": f"**{vt['location']}**\nGeliş: {t(vt['activation'], 'F')} ({t(vt['activation'])})\n"
                              f"Ayrılış: {t(vt['expiry'], 'F')}"}
        if send(hook, [emb]):
            state["baro_upcoming"] = key
    elif start <= now() < end and state.get("baro_arrived") != key:
        inv = vt.get("inventory") or []
        if not inv and now() - start < 3600:
            return  # envanter genelde birkaç dakika içinde yayınlanır; bir sonraki turda tekrar bak
        lines = [f"• **{i.get('item', '?')}** — {i.get('ducats', 0)} Ducat · {int(i.get('credits', 0)):,} Kredi".replace(",", ".")
                 for i in inv]
        desc = (f"**{vt['location']}** rölesinde! Ayrılış: {t(vt['expiry'])}\n\n" +
                ("\n".join(lines) if lines else "_Envanter henüz yayınlanmadı._"))
        emb = {"title": "🛒 Baro Ki'Teer geldi!", "color": GOLD, "footer": FOOTER, "description": cut(desc)}
        if send(hook, [emb], role):
            state["baro_arrived"] = key


def sortie(state):
    hook, role = env("WH_SORTIE"), env("ROLE_SORTIE")
    s = api("sortie")
    if hook and s and s.get("id") and s.get("variants") and state.get("sortie") != s["id"]:
        lines = []
        for n, v in enumerate(s["variants"], 1):
            lines.append(f"**{n}. {v['missionType']}** — {v['node']}\n  ⚠️ {v['modifier']}")
        emb = {"title": f"🎯 Günlük Sortie — {s['boss']}", "color": RED, "footer": FOOTER,
               "description": f"Düşman: **{s['faction']}** · Bitiş: {t(s['expiry'])}\n\n" + "\n".join(lines)}
        if send(hook, [emb], role):
            state["sortie"] = s["id"]

    a = api("archonHunt")
    if hook and a and a.get("id") and a.get("missions") and state.get("archon") != a["id"]:
        lines = [f"**{n}. {m['type']}** — {m['node']}" for n, m in enumerate(a["missions"], 1)]
        emb = {"title": f"🔥 Haftalık Archon Hunt — {a['boss']}", "color": PURPLE, "footer": FOOTER,
               "description": f"Düşman: **{a['faction']}** · Bitiş: {t(a['expiry'])}\n\n" + "\n".join(lines)}
        if send(hook, [emb], role):
            state["archon"] = a["id"]


def nightwave(state):
    hook, role = env("WH_NIGHTWAVE"), env("ROLE_NIGHTWAVE")
    nw = api("nightwave")
    if not hook or not nw:
        return
    active = nw.get("activeChallenges") or []
    seen = set(state.get("nw_seen", []))
    new = [c for c in active if c["id"] not in seen]
    if new:
        def line(c):
            desc = c.get("desc") or ""
            text = "" if desc.startswith("[PH]") or not desc else f" — {desc}"
            return f"• **{c['title']}**{text} · {c['reputation']} itibar · bitiş {t(c['expiry'])}"
        groups = [("☀️ Günlük", [c for c in new if c.get("isDaily")]),
                  ("📅 Haftalık", [c for c in new if not c.get("isDaily") and not c.get("isElite")]),
                  ("💀 Elit Haftalık", [c for c in new if c.get("isElite")])]
        desc = "\n\n".join(f"**{g}**\n" + "\n".join(line(c) for c in cs) for g, cs in groups if cs)
        weekly = any(not c.get("isDaily") for c in new)
        emb = {"title": f"🌃 Nightwave — Sezon {nw.get('season', '?')}: yeni görevler", "color": PURPLE,
               "footer": FOOTER, "description": cut(desc)}
        if send(hook, [emb], role if weekly else None):
            seen.update(c["id"] for c in new)
    # sadece aktif görevleri hatırla (dosya büyümesin)
    state["nw_seen"] = sorted(seen & {c["id"] for c in active})


def fissures(state):
    hook = env("WH_FISSURE")
    fs = api("fissures")
    if not hook or fs is None:
        return
    fs = [f for f in fs if ts(f["expiry"]) > now()]
    fs.sort(key=lambda f: (f.get("tierNum", 9), f["expiry"]))

    def block(items):
        if not items:
            return "_Şu an yok._"
        return "\n".join(f"**{f['tier']}** · {f['missionType']} · {f['node']} · {f['enemy']} · {t(f['expiry'])}"
                         for f in items)

    embeds = [
        {"title": "💎 Void Fissure — Normal", "color": CYAN,
         "description": cut(block([f for f in fs if not f.get("isHard") and not f.get("isStorm")]))},
        {"title": "🗡️ Void Fissure — Steel Path", "color": RED,
         "description": cut(block([f for f in fs if f.get("isHard")]))},
        {"title": "🚀 Void Storm — Railjack", "color": PURPLE,
         "description": cut(block([f for f in fs if f.get("isStorm")])),
         "footer": FOOTER},
    ]
    embeds[0]["description"] = f"Son güncelleme: <t:{now()}:R>\n\n" + embeds[0]["description"]
    msg = state.get("fissure_msg")
    if msg and edit(hook, msg, embeds):
        return
    new_id = send(hook, embeds)
    if new_id:
        state["fissure_msg"] = new_id


# --------------------------------------------------------------------------- ana akış
def main():
    if not any(env(k) for k in ("WH_BARO", "WH_SORTIE", "WH_FISSURE", "WH_NIGHTWAVE")):
        print("Hiç webhook tanımlı değil (WH_BARO, WH_SORTIE, WH_FISSURE, WH_NIGHTWAVE).")
        return 0
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    before = json.dumps(state, sort_keys=True)
    for name, fn in (("Baro", baro), ("Sortie/Archon", sortie), ("Nightwave", nightwave), ("Fissure", fissures)):
        try:
            fn(state)
            print(f"✓ {name}")
        except Exception as e:  # bir bölüm hata verse de diğerleri çalışsın
            print(f"! {name} hata: {type(e).__name__}: {e}")
    after = json.dumps(state, sort_keys=True)
    if after != before:
        STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
        print("Durum dosyası güncellendi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
