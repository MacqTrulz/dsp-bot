# DSP Dünya Durumu

DSP Discord sunucusundaki **DÜNYA DURUMU** kanallarına otomatik Warframe bildirimleri gönderir.
GitHub Actions 15 dakikada bir çalıştırır, sunucu ya da açık bilgisayar gerekmez. Veri kaynağı [warframestat.us](https://api.warframestat.us/pc).

## Kanallar ve karakterler

Her kanal kendi adı ve avatarıyla yazar. Avatarlar `img/` klasöründe durur.

| Kanal | Karakter | Ne gelir | Etiket |
|---|---|---|---|
| #dünya-panosu | DSP Cephalon | Tek mesajlık canlı pano: döngüler (Cetus, Vallis, Cambion, Zariman, Duviri), Steel Path ödülü, Duviri seçimleri, Baro, sıfırlamalar, etkinlikler | yok |
| #baro-ki-teer | Relay Gözcüsü | Baro yola çıkınca haber, gelince envanter | Baro rolü |
| #sortie-archon | Sortie Komutanı | Günlük Sortie, haftalık özet (Archon Hunt, Deep/Temporal Archimedea, Teshin) | Sortie/Archon rolü |
| #void-fissure | Void Tarayıcısı | 15 dakikada bir güncellenen fissure paneli, değerli Steel Path fissure'larında ayrı uyarı | Fissure rolü (uyarıda) |
| #nightwave-etkinlik | Sinyal Kulesi | Nightwave görevleri, yeni etkinlikler, değerli ödüllü istilalar | Nightwave / Farm rolü |
| #oyun-haberleri | DSP Haber Ağı | Resmi Warframe haberleri (Türkçesi varsa Türkçe) | Haber rolü |

## Ayarlar

Settings → Secrets and variables → Actions.

**Secrets** (her kanalın webhook URL'si):
`WH_PANO`, `WH_BARO`, `WH_SORTIE`, `WH_FISSURE`, `WH_NIGHTWAVE`, `WH_HABER`

**Variables** (boş bırakılırsa o etiket atılmaz):

| Değişken | Ne işe yarar |
|---|---|
| `ROLE_BARO`, `ROLE_SORTIE`, `ROLE_NIGHTWAVE`, `ROLE_FARM`, `ROLE_FISSURE`, `ROLE_HABER` | Etiketlenecek rollerin ID'leri |
| `FISSURE_TIERS` | Uyarı atılacak Steel Path fissure seviyeleri. Varsayılan `Requiem,Omnia` |
| `INVASION_ITEMS` | Uyarı atılacak istila ödülleri. Varsayılan `Orokin Catalyst,Orokin Reactor,Forma,Exilus,Wraith,Vandal` |

## Dosyalar

| Dosya | Görevi |
|---|---|
| `wf_bildirim.py` | Veriyi çeker, mesajları gönderir ve günceller |
| `state.json` | Hangi bildirimlerin gönderildiğini ve panel mesaj ID'lerini tutar |
| `tools/avatar_uret.py` | Karakter avatarlarını SVG olarak üretir |
| `img/` | Avatarlar (PNG + SVG) |
| `.github/workflows/dunya-durumu.yml` | 15 dakikalık zamanlayıcı |

## Bakım

- **Elle çalıştırma:** Actions → **DSP Dünya Durumu** → **Run workflow**.
- **Avatarları yeniden üretmek:** `img/haber.png` dosyasını sil, sonraki çalışmada hepsi yeniden üretilir.
- **Panelleri yeniden atmak:** `wf_bildirim.py` içindeki `PERSONA_VERSION` sayısını bir artır. Eski paneller silinip yenileri atılır.
- **Durumu sıfırlamak:** `state.json` silinirse paneller yeniden atılır ve güncel Baro/Sortie gibi bildirimler bir kez daha gönderilebilir.
- Zamanlayıcı GitHub tarafında birkaç dakika gecikebilir.
