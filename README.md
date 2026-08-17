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

Kayıt ol / giriş yap → habit ekle → "✓ Bugün" butonuyla check-in yap → güncel
streak'i gör → "Arşivle" ile kaldır. Token'lar tarayıcının `localStorage`'ında
tutulur, süresi dolan access token otomatik yenilenir (refresh akışı arka planda
çalışır). Saf HTML/CSS/JS — ekstra build aracı veya bağımlılık gerekmez,
`app/static/index.html` dosyasında tek parça halinde.

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
| GET | `/habits` | Kendi habit'lerini listele (filtre + sayfalama) | Evet |
| GET | `/habits/{habit_id}` | Tek bir habit'i getir | Evet |
| PUT | `/habits/{habit_id}` | Habit'i güncelle | Evet |
| DELETE | `/habits/{habit_id}` | Habit'i arşivle (kalıcı silmez, geçmişi korur) | Evet |
| POST | `/habits/{habit_id}/logs` | Habit için tamamlama kaydı (check-in) oluştur | Evet |
| GET | `/habits/{habit_id}/logs` | Habit'in tamamlama geçmişini listele | Evet |
| DELETE | `/habits/{habit_id}/logs/{log_id}` | Bir tamamlama kaydını sil | Evet |
| GET | `/habits/{habit_id}/streak` | Habit'in güncel kesintisiz serisini (streak) hesapla | Evet |
| GET | `/habits/{habit_id}/stats` | Habit istatistikleri: toplam check-in, güncel/en uzun streak, tamamlanma oranı | Evet |

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

## Arşivleme

`DELETE /habits/{habit_id}` habit'i veritabanından silmez, `is_archived=true`
olarak işaretler — check-in geçmişi, streak ve istatistikler korunur. Arşivlenmiş
bir habit varsayılan `GET /habits` listesinde görünmez ama tekil olarak
(`GET /habits/{habit_id}`, loglar, streak, stats) erişilebilir kalır. Geri
almak için: `PUT /habits/{habit_id}` ile `{"is_archived": false}` gönder.
