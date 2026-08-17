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

Veritabanı, adlandırılmış bir Docker volume'ünde (`habit-data`) kalıcı olarak saklanır,
konteyner yeniden başlasa da veriler kaybolmaz. Kendi `SECRET_KEY`'ini kullanmak için:

```bash
SECRET_KEY=kendi-gizli-anahtarin docker compose up --build
```

## CI

`main`'e her push/PR'da GitHub Actions otomatik olarak: migration'ların modellerle
uyumlu olduğunu (`alembic check`), testlerin geçtiğini, Docker image'ının build
olup ayağa kalktığını (`/health` kontrolü) doğrular (`.github/workflows/ci.yml`).

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

## Rate limiting

Brute-force şifre denemelerine karşı `/auth/register` ve `/auth/login` IP başına
dakikada 5 istekle sınırlı; limit aşılırsa `429 Too Many Requests` döner. Diğer
tüm endpoint'ler için genel bir üst sınır (dakikada 200 istek) var.

## Endpoint'ler

| Method | Path | Açıklama | Auth |
| --- | --- | --- | --- |
| GET | `/health` | Servis durum kontrolü | Hayır |
| POST | `/auth/register` | Yeni kullanıcı kaydı | Hayır |
| POST | `/auth/login` | Giriş yap, access + refresh token al | Hayır |
| POST | `/auth/refresh` | Refresh token ile yeni access + refresh token al | Hayır |
| POST | `/auth/logout` | Refresh token'ı iptal et | Hayır |
| GET | `/me` | Kendi profilini gör | Evet |
| PUT | `/me` | E-posta/şifreni güncelle | Evet |
| POST | `/habits` | Yeni habit oluştur | Evet |
| GET | `/habits` | Kendi habit'lerini listele (filtre + sayfalama) | Evet |
| GET | `/habits/{habit_id}` | Tek bir habit'i getir | Evet |
| PUT | `/habits/{habit_id}` | Habit'i güncelle | Evet |
| DELETE | `/habits/{habit_id}` | Habit'i sil | Evet |
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
| `skip` | Atlanacak kayıt sayısı (varsayılan 0) |
| `limit` | Sayfa başına kayıt sayısı (varsayılan 20, en fazla 100) |
