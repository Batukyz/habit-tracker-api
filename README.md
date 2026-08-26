# Habit Tracker API

Alışkanlıkları (habit) ve günlük/haftalık tamamlama kayıtlarını takip eden basit bir FastAPI servisi.

## Kurulum

```bash
pip install -r requirements.txt
```

## Çalıştırma

Önce veritabanı tablolarını oluşturmak için migration'ları uygula (bir defalık,
ya da modelller değiştiğinde tekrar):

```bash
alembic upgrade head
```

Sonra sunucuyu başlat:

```bash
uvicorn app.main:app --reload
```

## Web arayüzü

Swagger üzerinden token kopyalayıp yapıştırmak yerine, basit bir giriş/kayıt
ekranı ve habit paneli sunan hafif bir web arayüzü de var:

```
http://127.0.0.1:8000/app/
```

Sağ üstteki 🌙/☀️ butonuyla **açık mod** ve **dark mod** arasında geçiş
yapabilirsin — tercihin tarayıcında hatırlanır. Modern, canlı bir iki renkli
(duotone) marka paleti kullanılıyor: canlı indigo (`#6C5CE7`) + canlı mercan
(`#E8114A`), ana butonlarda ve seçili öğelerde bir gradyan olarak birleşiyor;
streak (🔥) rakamları mercan rengiyle öne çıkıyor. Yuvarlak köşeler ve nazik
geçiş animasyonlarıyla tasarlandı; tüm renk çiftleri WCAG kontrastına göre
doğrulandı.

Kayıt ol / giriş yap → habit ekle → "✓ Bugün" butonuyla check-in yap → güncel
streak'i gör → "Arşivle" ile kaldır. Yeni habit eklerken 🙂 butonuyla ~90
emojilik bir panelden seçim yapabilir, bir **kategori** seçebilirsin (Sağlık,
Spor & Fitness, Finans, vb.) — ya da "📚 Habit kütüphanesinden hızlı ekle" ile
her biri kendi emojisi, kategorisi ve (varsa) birimiyle eşleşmiş 60 klasik
habit'ten, üstteki kategori filtrelerine göre daraltarak tek tıkla ekleyebilirsin
— zaten eklenmiş olanlar otomatik soluklaşıp devre dışı kalır.

Bir habit'in başlığına tıklayınca, o habit'in ay ay gezilebilen bir takvim
görünümüyle (‹ Ocak, 2026 › tarzı, ok tuşlarıyla önceki/sonraki aya geçilebilir)
tüm geçmişini, kategorisini, güncel/en uzun serisini ve tamamlanma oranını
gösteren bir detay ekranı açılır. **Miktar takibi olan habit'ler** (kütüphaneden
"Su iç", "Araç bakımı kontrol et" gibi birimli eklenenler, ya da manuel oluşturup
`tracking_unit` alanı API üzerinden ayarlananlar) için "✓ Bugün" butonuna
basınca, tarayıcının çirkin `prompt()` kutusu yerine uygulamanın kendi temasına
uyan bir pencerede hem ne kadar yapıldığı (örn. "Kaç km?") hem de isteğe bağlı
bir **not** sorulur (örn. "Yağ değişimi, lastik rotasyonu") — takvimde o günün
hücresinde miktar ve not ikonu görünür (üzerine gelince notu okuyabilirsin),
detay ekranında "Toplam km" gibi bir satır eklenir. Ayrıca notu olan tüm
check-in'ler, takvimin altında tarih + miktar + not metniyle okunaklı bir
liste halinde de gösterilir — sadece hover'a güvenmen gerekmez.

Bir habit'in detayında "✏️ Düzenle" ile başlığını/kategorisini/miktar birimini
sonradan değiştirebilir; ana ekrandaki "🗄️ Arşivlenenleri göster" panelinden
arşivlediğin habitleri görüp "Geri Yükle" ya da (onay isteyen) "Kalıcı Sil"
ile yönetebilirsin.

Token'lar tarayıcının `localStorage`'ında tutulur, süresi dolan access token
otomatik yenilenir (refresh akışı arka planda çalışır). Saf HTML/CSS/JS —
ekstra build aracı veya bağımlılık gerekmez, `app/static/index.html`
dosyasında tek parça halinde.

## Veritabanı migration'ları

Şema artık Alembic ile yönetiliyor — `app/models.py` içindeki modeller
otomatik olarak tablo oluşturmuyor. `models.py`'de değişiklik yaptığında:

```bash
alembic revision --autogenerate -m "kisa aciklama"
alembic upgrade head
```

Yeni migration dosyasını (`alembic/versions/` altında) commit'lemeyi unutma.

## Test

```bash
pytest
```

## Docker ile çalıştırma

```bash
docker compose up --build
```

`docker-compose.yml` artık gerçek bir **PostgreSQL** servisi (`db`) içeriyor —
API konteyneri `db` sağlıklı hale gelene kadar bekleyip ona bağlanıyor, veriler
adlandırılmış bir Docker volume'ünde (`habit-postgres-data`) kalıcı saklanıyor.
Konteynerin başlangıcında (`Dockerfile` CMD) `alembic upgrade head` otomatik
çalışıp Postgres şemasını oluşturuyor/günceliyor.

Kendi `SECRET_KEY`'ini kullanmak için:

```bash
SECRET_KEY=kendi-gizli-anahtarin docker compose up --build
```

Docker olmadan yerel geliştirme (`uvicorn app.main:app --reload`) hâlâ varsayılan
olarak SQLite kullanır — hızlı, sıfır kurulum gerektiren local dev için Postgres
şart değil; `DATABASE_URL` ortam değişkenini kendin ayarlarsan (örn. yerel bir
Postgres'e) o da çalışır.

Bu geliştirme makinesinde Docker CLI kurulu olmadığı için burada bizzat
doğrulayamadım — bunun yerine CI'daki `postgres-e2e` job'u gerçek bir Postgres'i
`docker compose` ile ayağa kaldırıp migration'ları çalıştırıyor ve `/auth/register`
ile uçtan uca test ediyor. Bu job yeşil, yani Postgres akışı gerçekten doğrulanmış
durumda (ilk migration'daki `CURRENT_TIMESTAMP`/`CURRENT_DATE` server default
ifadeleri dahil).

## CI

`main`'e her push/PR'da GitHub Actions otomatik olarak: migration'ların modellerle
uyumlu olduğunu (`alembic check`), testlerin geçtiğini, Docker image'ının build
olup ayağa kalktığını (`/health` kontrolü) doğrular (`.github/workflows/ci.yml`).

## Loglama ve hata yönetimi

Her istek, method/path/durum kodu/süre bilgisiyle konsola loglanır. Beklenmeyen
bir hata (500) oluşursa, gerçek exception sunucu loguna yazılır ama istemciye
sadece `{"detail": "Internal server error"}` döner — iç detaylar (stack trace,
sorgu, dosya yolu) dışarı sızmaz.

## Kimlik doğrulama

Habit'ler artık kullanıcıya özel. Önce kayıt olup giriş yapman, sonra her istekte
aldığın token'ı `Authorization: Bearer <token>` header'ıyla göndermen gerekiyor.

```bash
# Kayıt
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "sen@example.com", "password": "en-az-8-karakter"}'

# Giriş (form-encoded, JSON değil) — access_token ve refresh_token döner
curl -X POST http://127.0.0.1:8000/auth/login \
  -d "username=sen@example.com&password=en-az-8-karakter"

# Token'ı kullanarak habit oluşturma
curl -X POST http://127.0.0.1:8000/habits \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Kitap oku"}'

# access_token suresi dolunca, sifre girmeden yenisini almak icin:
curl -X POST http://127.0.0.1:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'

# Cikis yap (refresh token'i gecersiz kilar)
curl -X POST http://127.0.0.1:8000/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'
```

`access_token` 30 dakika, `refresh_token` 30 gün geçerli. Her `/auth/refresh`
çağrısı eski refresh token'ı geçersiz kılıp yenisini döner (rotasyon) — çalınmış
bir refresh token'ın tekrar kullanılması bu sayede engellenir. `/auth/logout`,
verilen refresh token'ı kalıcı olarak iptal eder.

**Sınır:** `access_token`'lar stateless JWT olduğu için, çıkış yapıldığında ya da
refresh token iptal edildiğinde hâlâ süresi dolmamış bir access token bir sonraki
30 dakika boyunca geçerli kalmaya devam eder — sadece refresh akışı kesilir. Bu,
kısa access token ömrüyle (30 dk) kabul edilebilir bir risk seviyesine indirgenmiştir.

`SECRET_KEY` ortam değişkeni ayarlanmazsa geliştirme amaçlı sabit bir anahtar
kullanılır — üretimde mutlaka kendi `SECRET_KEY`'ini ayarla.

## Şifre sıfırlama

```bash
# 1. Sıfırlama iste (kayıtlı olsun olmasın aynı cevabı döner, e-posta sızdırmaz)
curl -X POST http://127.0.0.1:8000/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "sen@example.com"}'

# 2. E-postana gelen (ya da SMTP ayarlanmadıysa sunucu logunda görünen) token ile sıfırla
curl -X POST http://127.0.0.1:8000/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"token": "<reset_token>", "new_password": "yeni-en-az-8-karakter"}'
```

Reset token'ı 60 dakika geçerli, tek kullanımlık. Şifre sıfırlanınca kullanıcının
tüm refresh token'ları iptal edilir — açık tüm oturumlar yeniden giriş yapmak
zorunda kalır.

**E-posta gönderimi:** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
`SMTP_FROM` ortam değişkenleri ayarlanmadıysa e-posta gönderilmez, token yalnızca
sunucu loguna yazılır (geliştirme/test için). Gerçek e-posta göndermek için bu
değişkenleri kendi SMTP sağlayıcına (Gmail, SendGrid, vb.) göre ayarla.

## Rate limiting

Brute-force şifre denemelerine karşı `/auth/register`, `/auth/login`,
`/auth/forgot-password` ve `/auth/reset-password` IP başına dakikada 5 istekle
sınırlı; limit aşılırsa `429 Too Many Requests` döner. Diğer tüm endpoint'ler
için genel bir üst sınır (dakikada 200 istek) var.

## Endpoint'ler

| Method | Path | Açıklama | Auth |
| --- | --- | --- | --- |
| GET | `/health` | Servis durum kontrolü | Hayır |
| POST | `/auth/register` | Yeni kullanıcı kaydı | Hayır |
| POST | `/auth/login` | Giriş yap, access + refresh token al | Hayır |
| POST | `/auth/refresh` | Refresh token ile yeni access + refresh token al | Hayır |
| POST | `/auth/logout` | Refresh token'ı iptal et | Hayır |
| POST | `/auth/forgot-password` | Şifre sıfırlama token'ı iste | Hayır |
| POST | `/auth/reset-password` | Token ile şifreyi sıfırla | Hayır |
| GET | `/me` | Kendi profilini gör | Evet |
| PUT | `/me` | E-posta/şifreni güncelle | Evet |
| POST | `/habits` | Yeni habit oluştur | Evet |
| GET | `/habits` | Kendi habit'lerini listele (frequency/is_completed/category filtresi + arama + sayfalama) | Evet |
| GET | `/habits/{habit_id}` | Tek bir habit'i getir | Evet |
| PUT | `/habits/{habit_id}` | Habit'i güncelle | Evet |
| DELETE | `/habits/{habit_id}` | Habit'i arşivle (kalıcı silmez, geçmişi korur) | Evet |
| DELETE | `/habits/{habit_id}/permanent` | Arşivlenmiş bir habit'i kalıcı olarak sil (önce arşivlenmiş olmalı) | Evet |
| POST | `/habits/{habit_id}/logs` | Habit için tamamlama kaydı (check-in) oluştur, isteğe bağlı `amount` ve `note` ile | Evet |
| GET | `/habits/{habit_id}/logs` | Habit'in tamamlama geçmişini listele | Evet |
| DELETE | `/habits/{habit_id}/logs/{log_id}` | Bir tamamlama kaydını sil | Evet |
| GET | `/habits/{habit_id}/streak` | Habit'in güncel kesintisiz serisini (streak) hesapla | Evet |
| GET | `/habits/{habit_id}/stats` | Habit istatistikleri: toplam check-in, güncel/en uzun streak, tamamlanma oranı, (varsa) toplam miktar | Evet |
| POST | `/events` | Yeni plan/etkinlik oluştur (`title` + `event_date`) | Evet |
| GET | `/events` | Kendi planlarını listele (`date_from`/`date_to`/`is_done` filtresi, tarihe göre sıralı) | Evet |
| GET | `/events/{event_id}` | Tek bir planı getir | Evet |
| PUT | `/events/{event_id}` | Planı güncelle (örn. `is_done: true` ile tamamlandı işaretle) | Evet |
| DELETE | `/events/{event_id}` | Planı sil | Evet |
| GET | `/overview` | Genel özet: aktif habit sayısı, bugün tamamlanan, en uzun güncel seri, bugünkü/geciken planlar | Evet |

`Habit`, tekrar eden bir alışkanlık; `Event` ise "24 Ağustos'ta toplantım var"
gibi **tek seferlik, belirli bir tarihe bağlı bir plan/görev**. Web arayüzünde
"Habit'lerim" ekranının en üstünde üç sayılık bir **özet paneli** var (en uzun
güncel seri, bugün kaç habit tamamlandı, kaç geciken plan var) — `GET /overview`
ile besleniyor, her check-in/arşivleme/plan işleminde otomatik güncellenir.
Altında üç bölüm var: **"⏰ Geciken planlar"** (tarihi geçmiş ama tamamlandı
işaretlenmemiş planlar — sadece böyle bir plan varsa görünür, hiçbiri sessizce
kaybolmaz), **"📅 Bugün yapmam gerekenler"** (bugüne ait planlar, işaretleyerek
tamamlandı yapabilirsin) ve **"🗓️ Yaklaşan planlar"** (bugünden sonraki tüm
planlar, tarihleriyle birlikte, buradan yeni plan da ekleyebilirsin).

`Habit`'in `tracking_unit` alanı (örn. `"litre"`, `"sayfa"`, `"km"`) ayarlıysa, o
habit sadece işaretlenen bir şey değil, **miktar takip edilen** bir habit'tir —
`POST .../logs` çağrısına `amount` (negatif olmayan bir sayı — eksi değer `422`
ile reddedilir) eklenebilir, `stats` de tüm zamanların toplam miktarını
(`total_amount`) döner. Her check-in kaydına
ayrıca isteğe bağlı serbest metin bir `note` eklenebilir (örn. "yağ değişimi,
15.230 km'de yapıldı") — miktar takibi olmayan habit'ler için de kullanılabilir.
`Habit`'in `category` alanı (örn. `"Sağlık"`, `"Spor & Fitness"`) ile
sınıflandırılabilir ve `GET /habits?category=...` ile filtrelenebilir.

Habit'ler kullanıcıya özeldir: bir kullanıcı başka bir kullanıcının habit'ine
eriştiğinde de (o habit hiç yokmuş gibi) `404` alır — habit'in varlığı bile sızdırılmaz.

Streak, `frequency` alanına göre günlük veya haftalık ardışık periyotları sayar; en son kayıttan geriye doğru ilk boşlukta durur. `stats` ayrıca tüm zamanların en uzun serisini ve habit oluşturulduğundan bu yana beklenen periyotlara göre tamamlanma yüzdesini de döner.

`GET /habits` şu query parametrelerini destekler:

| Parametre | Açıklama |
| --- | --- |
| `frequency` | `daily` veya `weekly` ile filtrele |
| `is_completed` | `true`/`false` ile filtrele |
| `search` | Başlıkta geçen metne göre ara (büyük/küçük harf duyarsız) |
| `include_archived` | `true` ise arşivlenmiş habit'ler de listeye dahil olur (varsayılan `false`) |
| `skip` | Atlanacak kayıt sayısı (varsayılan 0) |
| `limit` | Sayfa başına kayıt sayısı (varsayılan 20, en fazla 100) |

## Arşivleme ve kalıcı silme

`DELETE /habits/{habit_id}` habit'i veritabanından silmez, `is_archived=true`
olarak işaretler — check-in geçmişi, streak ve istatistikler korunur. Arşivlenmiş
bir habit varsayılan `GET /habits` listesinde görünmez ama tekil olarak
(`GET /habits/{habit_id}`, loglar, streak, stats) erişilebilir kalır. Geri
almak için: `PUT /habits/{habit_id}` ile `{"is_archived": false}` gönder
(web arayüzünde: "🗄️ Arşivlenenleri göster" → "Geri Yükle").

Gerçekten ve kalıcı olarak silmek istersen: `DELETE /habits/{habit_id}/permanent`.
Bu endpoint **sadece habit zaten arşivlenmişse** çalışır (aksi halde `400`
döner) — yanlışlıkla kalıcı veri kaybını önlemek için önce arşivleme
zorunludur. Web arayüzünde bu, arşiv listesindeki "Kalıcı Sil" butonuna denk
gelir ve bir onay istenir.

## Habit'i düzenleme

Web arayüzünde bir habit'in detay ekranında "✏️ Düzenle" butonuyla başlığını,
kategorisini ve miktar birimini (`tracking_unit`) sonradan değiştirebilirsin —
habit'i eklerken kategori atamayı unutsan bile daha sonra ekleyebilirsin.
API tarafında bu `PUT /habits/{habit_id}` ile yapılır.
