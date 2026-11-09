#!/usr/bin/env python3
"""
DSP Dünya Durumu bildirimcisi  (v2)
-----------------------------------
warframestat.us API'sinden Warframe dünya durumunu okur ve Discord webhook'ları
ile DSP sunucusuna Türkçe bildirim gönderir. GitHub Actions 15 dakikada bir çalıştırır.

  #dünya-panosu        Canlı pano (döngüler, Steel Path, Duviri, etkinlikler, sıfırlamalar)
  #baro-ki-teer        Baro yola çıkınca haber + gelince envanter            (@Baro Ki'Teer)
  #sortie-archon       Günlük Sortie + haftalık sıfırlama özeti               (@Sortie/Archon)
  #void-fissure        Canlı fissure paneli + değerli Steel Path fissure'ları (@Fissure/Relic)
  #nightwave-etkinlik  Nightwave görevleri, yeni etkinlikler, değerli istilalar (@Nightwave, @Farm)
  #oyun-haberleri      Resmi Warframe haberleri                              (@Oyun Haberleri)

Ayarlar (GitHub > Settings > Secrets and variables > Actions):
  Secrets   : WH_PANO, WH_BARO, WH_SORTIE, WH_FISSURE, WH_NIGHTWAVE, WH_HABER
  Variables : ROLE_BARO, ROLE_SORTIE, ROLE_NIGHTWAVE, ROLE_FARM, ROLE_FISSURE, ROLE_HABER
  (İsteğe bağlı) FISSURE_TIERS (vars. "Requiem,Omnia"), INVASION_ITEMS (vars. aşağıda)
Tanımlanmayan webhook'un bölümü sessizce atlanır. Sadece standart Python kütüphanesi.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = os.environ.get("API_BASE", "https://api.warframestat.us/pc")
STATE_FILE = Path(os.environ.get("STATE_FILE", Path(__file__).with_name("state.json")))
UA = "DSP-Dunya-Durumu/2.0 (Discord community notifier)"

GOLD, PURPLE, RED, CYAN, GREEN = 0xD6B15A, 0x9D6BFF, 0xE3343C, 0x5EC8E6, 0x2ECC71
FOOTER = {"text": "DSP · Dünya Durumu"}

ENDLESS = {"Survival", "Defense", "Interception", "Disruption", "Excavation", "Void Cascade",
           "Void Flood", "Void Armageddon", "Alchemy", "Mirror Defense"}
DEFAULT_INV = "Orokin Catalyst,Orokin Reactor,Forma,Exilus,Wraith,Vandal"

# Açık dünya döngüleri: durum -> (Türkçe ad, emoji, süre sn, sonraki durum)
CYCLES = {
    "cetusCycle":   ("Cetus · Plains of Eidolon", {"day": ("Gündüz", "☀️", 6000, "night"), "night": ("Gece", "🌙", 3000, "day")}),
    "vallisCycle":  ("Fortuna · Orb Vallis",      {"warm": ("Sıcak", "🔥", 400, "cold"), "cold": ("Soğuk", "❄️", 1200, "warm")}),
    "cambionCycle": ("Necralisk · Cambion Drift", {"fass": ("Fass", "🟠", 6000, "vome"), "vome": ("Vome", "🔵", 3000, "fass")}),
    "zarimanCycle": ("Zariman",                   {"corpus": ("Corpus", "🔷", 9000, "grineer"), "grineer": ("Grineer", "🟥", 9000, "corpus")}),
}


# --------------------------------------------------------------------------- yardımcılar
def env(name, default=""):
    return (os.environ.get(name) or default).strip()


def ts(iso):
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def tag(sec, style="R"):
    return f"<t:{int(sec)}:{style}>"


def t(iso, style="R"):
    return tag(ts(iso), style)


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
            if e.code == 429 and attempt < 2:
                wait = float(json.loads(e.read() or b"{}").get("retry_after", 2))
                time.sleep(min(wait, 10))
                continue
            return e.code, None
        except Exception as e:
            print(f"  ! {method} {url.split('?')[0][:60]}: {e}")
            if attempt < 2:
                time.sleep(2)
                continue
            return 0, None
    return 0, None


_cache = {}


def api(path):
    if path in _cache:
        return _cache[path]
    code, data = http("GET", f"{API}/{path}/?language=en")
    if code != 200 or data is None:
        print(f"  ! API okunamadı: {path} ({code})")
        data = None
    _cache[path] = data
    return data


def send(hook, embeds, role=None, text=None):
    if not hook:
        return None
    content = " ".join(x for x in (f"<@&{role}>" if role else "", text or "") if x)
    body = {"embeds": embeds, "allowed_mentions": {"parse": [], "roles": [role] if role else []}}
    if content:
        body["content"] = content
    code, data = http("POST", hook + ("&" if "?" in hook else "?") + "wait=true", body)
    if code in (200, 204) and data:
        return data.get("id")
    print(f"  ! Discord'a gönderilemedi ({code})")
    return None


def edit(hook, msg_id, embeds):
    code, _ = http("PATCH", f"{hook.split('?')[0]}/messages/{msg_id}", {"embeds": embeds})
    return code == 200


def panel(state, key, hook, embeds):
    """Tek mesajı sürekli günceller; mesaj silinmişse yenisini atar."""
    msg = state.get(key)
    if msg and edit(hook, msg, embeds):
        return
    new_id = send(hook, embeds)
    if new_id:
        state[key] = new_id


def cut(text, limit=4000):
    return text if len(text) <= limit else text[: limit - 20].rsplit("\n", 1)[0] + "\n…"


def items_of(reward):
    """API ödül nesnesinden 'Ad' / '3x Ad' listesi üretir."""
    out = []
    for c in (reward or {}).get("countedItems") or []:
        out.append(f"{c['count']}x {c['type']}" if c.get("count", 1) > 1 else c["type"])
    for i in (reward or {}).get("items") or []:
        if i not in " ".join(out):
            out.append(i)
    return out


def next_weekly_reset():
    d = datetime.now(timezone.utc)
    days = (7 - d.weekday()) % 7 or 7
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()) + days * 86400


def next_daily_reset():
    d = datetime.now(timezone.utc)
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()) + 86400


def archimedea_name(a):
    k = (a.get("typeKey") or a.get("type") or "").replace(" ", "")
    return {"CT_LAB": "Deep Archimedea", "CT_HEX": "Temporal Archimedea"}.get(k, k or "Archimedea")


# --------------------------------------------------------------------------- 1) Dünya panosu
def dunya_panosu(state):
    hook = env("WH_PANO")
    if not hook:
        return
    lines = []
    for path, (title, states) in CYCLES.items():
        c = api(path)
        if not c or c.get("state") not in states:
            continue
        st, exp = c["state"], ts(c["expiry"])
        while exp <= now():  # API eskiyse döngüyü ileri sar
            st = states[st][3]
            exp += states[st][2]
        name, emo, _, nxt = states[st]
        extra = " · **Eidolon avı zamanı!**" if path == "cetusCycle" and st == "night" else ""
        lines.append(f"{emo} **{title}:** {name} — {states[nxt][0]} {tag(exp)}{extra}")
    emb1 = {"title": "🌍 Açık Dünya Döngüleri", "color": CYAN,
            "description": "\n".join(lines) or "_Veri alınamadı._"}

    embs = [emb1]
    sp = api("steelPath")
    du = api("duviriCycle")
    info = []
    if sp and sp.get("currentReward"):
        rot = [r["name"] for r in sp.get("rotation") or []]
        cur = sp["currentReward"]["name"]
        nxt = rot[(rot.index(cur) + 1) % len(rot)] if cur in rot else None
        info.append(f"🗡️ **Steel Path (Teshin):** {cur} ({sp['currentReward'].get('cost', '?')} Steel Essence)"
                    + (f"\n  Sonraki hafta: {nxt}" if nxt else ""))
    if du:
        ch = {c.get("category"): c.get("choices") for c in du.get("choices") or []}
        mood = {"sorrow": "Hüzün", "fear": "Korku", "joy": "Neşe", "anger": "Öfke", "envy": "Kıskançlık"}.get(du.get("state"), du.get("state", "?"))
        info.append(f"🌀 **Duviri:** Ruh hali {mood} (değişim {t(du['expiry'])})")
        if ch.get("normal"):
            info.append(f"  Circuit Warframe'leri: {', '.join(ch['normal'])}")
        if ch.get("hard"):
            info.append(f"  Steel Path Circuit silahları: {', '.join(ch['hard'])}")
    vt = api("voidTrader")
    if vt and vt.get("activation"):
        if ts(vt["activation"]) > now():
            info.append(f"🛒 **Baro Ki'Teer:** {vt['location']} — geliş {t(vt['activation'])}")
        else:
            info.append(f"🛒 **Baro Ki'Teer:** {vt['location']} rölesinde — ayrılış {t(vt['expiry'])}")
    info.append(f"🔄 **Günlük sıfırlama:** {tag(next_daily_reset())} · **Haftalık:** {tag(next_weekly_reset())}")
    embs.append({"title": "📌 Bu Hafta", "color": GOLD, "description": cut("\n".join(info))})

    ev = [e for e in (api("events") or []) if e.get("expiry") and ts(e["expiry"]) > now()]
    if ev:
        el = []
        for e in ev:
            prog = f" · %{e['health']:.0f}" if isinstance(e.get("health"), (int, float)) else ""
            where = e.get("node") or e.get("victimNode") or ""
            el.append(f"• **{e.get('description', 'Etkinlik')}**{(' — ' + where) if where else ''}{prog} · bitiş {t(e['expiry'])}")
        embs.append({"title": "🎉 Aktif Etkinlikler", "color": PURPLE, "description": cut("\n".join(el))})
    embs[-1]["footer"] = FOOTER
    embs[0]["description"] = f"Son güncelleme: {tag(now())}\n\n" + embs[0]["description"]
    panel(state, "pano_msg", hook, embs)


# --------------------------------------------------------------------------- 2) Baro
def baro(state):
    hook, role = env("WH_BARO"), env("ROLE_BARO")
    vt = api("voidTrader")
    if not hook or not vt or not vt.get("id"):
        return
    start, end = ts(vt["activation"]), ts(vt["expiry"])
    key = f"{vt['id']}:{vt['activation']}"
    if now() < start and state.get("baro_upcoming") != key:
        emb = {"title": "🛒 Baro Ki'Teer yolda", "color": GOLD, "footer": FOOTER,
               "description": f"**{vt['location']}**\nGeliş: {t(vt['activation'], 'F')} ({t(vt['activation'])})\n"
                              f"Ayrılış: {t(vt['expiry'], 'F')}"}
        if send(hook, [emb]):
            state["baro_upcoming"] = key
    elif start <= now() < end and state.get("baro_arrived") != key:
        inv = vt.get("inventory") or []
        if not inv and now() - start < 3600:
            return
        lines = [f"• **{i.get('item', '?')}** — {i.get('ducats', 0)} Ducat · {int(i.get('credits', 0)):,} Kredi".replace(",", ".")
                 for i in inv]
        desc = (f"**{vt['location']}** rölesinde! Ayrılış: {t(vt['expiry'])}\n\n" +
                ("\n".join(lines) if lines else "_Envanter henüz yayınlanmadı._"))
        emb = {"title": "🛒 Baro Ki'Teer geldi!", "color": GOLD, "footer": FOOTER, "description": cut(desc)}
        if send(hook, [emb], role):
            state["baro_arrived"] = key


# --------------------------------------------------------------------------- 3) Sortie + haftalık sıfırlama
def sortie(state):
    hook, role = env("WH_SORTIE"), env("ROLE_SORTIE")
    if not hook:
        return
    s = api("sortie")
    if s and s.get("id") and s.get("variants") and state.get("sortie") != s["id"]:
        lines = [f"**{n}. {v['missionType']}** — {v['node']}\n  ⚠️ {v['modifier']}" for n, v in enumerate(s["variants"], 1)]
        emb = {"title": f"🎯 Günlük Sortie — {s['boss']}", "color": RED, "footer": FOOTER,
               "description": f"Düşman: **{s['faction']}** · Bitiş: {t(s['expiry'])}\n\n" + "\n".join(lines)}
        if send(hook, [emb], role):
            state["sortie"] = s["id"]

    a = api("archonHunt")
    if not (a and a.get("id") and a.get("missions")) or state.get("archon") == a["id"]:
        return
    embs = [{"title": f"🔥 Archon Hunt — {a['boss']}", "color": PURPLE,
             "description": f"Düşman: **{a['faction']}** · Bitiş: {t(a['expiry'])}\n\n" +
                            "\n".join(f"**{n}. {m['type']}** — {m['node']}" for n, m in enumerate(a["missions"], 1))}]
    for ar in api("archimedeas") or []:
        ml = []
        for n, m in enumerate(ar.get("missions") or [], 1):
            risks = ", ".join(r["name"] for r in m.get("risks") or [])
            ml.append(f"**{n}. {m['missionType']}** ({m.get('faction', '?')}) — {m.get('deviation', {}).get('name', '')}"
                      + (f"\n  Riskler: {risks}" if risks else ""))
        mods = ", ".join(p["name"] for p in ar.get("personalModifiers") or [])
        embs.append({"title": f"🏛️ {archimedea_name(ar)}", "color": GOLD,
                     "description": cut("\n".join(ml) + (f"\n\nKişisel değiştiriciler: {mods}" if mods else ""))})
    sp = api("steelPath")
    extra = f"🗡️ Teshin'de bu hafta: **{sp['currentReward']['name']}**\n" if sp and sp.get("currentReward") else ""
    embs.append({"title": "♻️ Diğer haftalık sıfırlamalar", "color": CYAN, "footer": FOOTER,
                 "description": extra + "Netracell, Kahl'ın görevleri, Archimedea ve Nightwave haftalık görevleri yenilendi.\n"
                                        f"Sonraki sıfırlama: {tag(next_weekly_reset(), 'F')}"})
    if send(hook, embs, role, "**Haftalık sıfırlama!**"):
        state["archon"] = a["id"]


# --------------------------------------------------------------------------- 4) Nightwave
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
    state["nw_seen"] = sorted(seen & {c["id"] for c in active})


# --------------------------------------------------------------------------- 5) Etkinlikler + istilalar
def etkinlik_istila(state):
    hook = env("WH_NIGHTWAVE")
    if not hook:
        return
    first = "ev_seen" not in state
    # yeni oyun içi etkinlikler
    events = api("events")
    if events is not None:
        seen = set(state.get("ev_seen", []))
        for e in events:
            if e["id"] in seen or not e.get("expiry") or ts(e["expiry"]) <= now():
                continue
            if not first:
                rewards = []
                for r in e.get("rewards") or []:
                    rewards += items_of(r)
                for st in e.get("interimSteps") or []:
                    rewards += items_of(st.get("reward"))
                where = e.get("node") or e.get("victimNode") or ""
                desc = (f"{e.get('tooltip', '')}\n\n" + (f"📍 {where}\n" if where else "") + f"⏳ Bitiş: {t(e['expiry'])}" +
                        (f"\n\n**Ödüller:** {', '.join(dict.fromkeys(rewards))}" if rewards else ""))
                send(hook, [{"title": f"🎉 Yeni etkinlik: {e.get('description', 'Etkinlik')}", "color": PURPLE,
                             "footer": FOOTER, "description": cut(desc)}])
            seen.add(e["id"])
        state["ev_seen"] = sorted(seen & {e["id"] for e in events})

    # değerli istilalar
    invs = api("invasions")
    if invs is None:
        return
    wanted = [w.strip().lower() for w in env("INVASION_ITEMS", DEFAULT_INV).split(",") if w.strip()]
    seen = set(state.get("inv_seen", []))
    hits = []
    for i in invs:
        if i.get("completed") or i["id"] in seen:
            continue
        sides = [(i.get("attacker") or {}), (i.get("defender") or {})]
        loot = [x for s in sides for x in items_of(s.get("reward"))]
        good = [x for x in loot if any(w in x.lower() for w in wanted)]
        if good:
            hits.append((i, good))
        seen.add(i["id"])
    state["inv_seen"] = sorted(seen & {i["id"] for i in invs})
    if hits and not first:
        lines = [f"• **{', '.join(g)}** — {i['node']} ({i.get('desc', '')}) · %{i.get('completion', 0):.0f}" for i, g in hits]
        send(hook, [{"title": "⚔️ Değerli istila!", "color": GREEN, "footer": FOOTER,
                     "description": cut("\n".join(lines) + "\n\nİstilalar tamamlanınca kaybolur, acele et!")}],
             env("ROLE_FARM"))


# --------------------------------------------------------------------------- 6) Fissure paneli + akıllı etiket
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
         "description": cut(block([f for f in fs if f.get("isStorm")])), "footer": FOOTER},
    ]
    embeds[0]["description"] = f"Son güncelleme: {tag(now())}\n\n" + embeds[0]["description"]
    panel(state, "fissure_msg", hook, embeds)

    # değerli Steel Path endless fissure'ları için etiket
    tiers = {x.strip() for x in env("FISSURE_TIERS", "Requiem,Omnia").split(",") if x.strip()}
    first = "fis_seen" not in state
    seen = set(state.get("fis_seen", []))
    good = [f for f in fs if f.get("isHard") and f.get("tier") in tiers and f.get("missionType") in ENDLESS
            and f["id"] not in seen]
    if good and not first:
        lines = [f"**{f['tier']}** · {f['missionType']} · {f['node']} · {f['enemy']} · bitiş {t(f['expiry'])}" for f in good]
        send(hook, [{"title": "🔔 Steel Path endless fissure açıldı", "color": RED, "footer": FOOTER,
                     "description": "\n".join(lines)}], env("ROLE_FISSURE"))
    state["fis_seen"] = sorted((seen | {f["id"] for f in good}) & {f["id"] for f in fs})


# --------------------------------------------------------------------------- 7) Resmi haberler
def haberler(state):
    hook, role = env("WH_HABER"), env("ROLE_HABER")
    news = api("news")
    if not hook or news is None:
        return
    first = "news_seen" not in state
    seen = set(state.get("news_seen", []))
    for n in sorted(news, key=lambda x: x.get("date") or ""):
        if n["id"] in seen:
            continue
        seen.add(n["id"])
        try:
            age = now() - ts(n.get("date") or "1970-01-01T00:00:00.000Z")
        except ValueError:
            age = 10 ** 9
        if age > 3 * 86400 or (first and age > 86400):  # eski / sabit haberleri atla
            continue
        title = (n.get("translations") or {}).get("tr") or n.get("message", "Haber")
        emb = {"title": f"📰 {title}"[:250], "color": GOLD, "footer": FOOTER,
               "description": f"[Habere git]({n['link']})" if n.get("link") else ""}
        if n.get("link"):
            emb["url"] = n["link"]
        if n.get("imageLink"):
            emb["image"] = {"url": n["imageLink"]}
        send(hook, [emb], role)
    state["news_seen"] = sorted(seen & {n["id"] for n in news})


# --------------------------------------------------------------------------- ana akış
SECTIONS = (("Dünya panosu", dunya_panosu), ("Baro", baro), ("Sortie/Haftalık", sortie),
            ("Nightwave", nightwave), ("Etkinlik/İstila", etkinlik_istila), ("Fissure", fissures),
            ("Haberler", haberler))


def main():
    hooks = ("WH_PANO", "WH_BARO", "WH_SORTIE", "WH_FISSURE", "WH_NIGHTWAVE", "WH_HABER")
    if not any(env(k) for k in hooks):
        print("Hiç webhook tanımlı değil.")
        return 0
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    before = json.dumps(state, sort_keys=True)
    for name, fn in SECTIONS:
        try:
            fn(state)
            print(f"✓ {name}")
        except Exception as e:
            print(f"! {name} hata: {type(e).__name__}: {e}")
    if json.dumps(state, sort_keys=True) != before:
        STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
        print("Durum dosyası güncellendi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
