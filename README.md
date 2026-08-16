# Habit Tracker API

Alışkanlıkları (habit) ve günlük/haftalık tamamlama kayıtlarını takip eden basit bir FastAPI servisi.

## Kurulum

```bash
pip install -r requirements.txt
```

## Çalıştırma

```bash
uvicorn app.main:app --reload
```

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

`main`'e her push/PR'da GitHub Actions otomatik olarak testleri çalıştırır ve
Docker image'ının build olduğunu doğrular (`.github/workflows/ci.yml`).

## Kimlik doğrulama

Habit'ler artık kullanıcıya özel. Önce kayıt olup giriş yapman, sonra her istekte
aldığın token'ı `Authorization: Bearer <token>` header'ıyla göndermen gerekiyor.

```bash
# Kayıt
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "sen@example.com", "password": "en-az-8-karakter"}'

# Giriş (form-encoded, JSON değil)
curl -X POST http://127.0.0.1:8000/auth/login \
  -d "username=sen@example.com&password=en-az-8-karakter"

# Token'ı kullanarak habit oluşturma
curl -X POST http://127.0.0.1:8000/habits \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Kitap oku"}'
```

Token süresi 24 saat. `SECRET_KEY` ortam değişkeni ayarlanmazsa geliştirme amaçlı
sabit bir anahtar kullanılır — üretimde mutlaka kendi `SECRET_KEY`'ini ayarla.

## Endpoint'ler

| Method | Path | Açıklama | Auth |
| --- | --- | --- | --- |
| GET | `/health` | Servis durum kontrolü | Hayır |
| POST | `/auth/register` | Yeni kullanıcı kaydı | Hayır |
| POST | `/auth/login` | Giriş yap, access token al | Hayır |
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
