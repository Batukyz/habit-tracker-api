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

## Endpoint'ler

| Method | Path | Açıklama |
| --- | --- | --- |
| GET | `/health` | Servis durum kontrolü |
| POST | `/habits` | Yeni habit oluştur |
| GET | `/habits` | Tüm habit'leri listele |
| GET | `/habits/{habit_id}` | Tek bir habit'i getir |
| PUT | `/habits/{habit_id}` | Habit'i güncelle |
| DELETE | `/habits/{habit_id}` | Habit'i sil |
| POST | `/habits/{habit_id}/logs` | Habit için tamamlama kaydı (check-in) oluştur |
| GET | `/habits/{habit_id}/logs` | Habit'in tamamlama geçmişini listele |
| DELETE | `/habits/{habit_id}/logs/{log_id}` | Bir tamamlama kaydını sil |
| GET | `/habits/{habit_id}/streak` | Habit'in güncel kesintisiz serisini (streak) hesapla |

Streak, `frequency` alanına göre günlük veya haftalık ardışık periyotları sayar; en son kayıttan geriye doğru ilk boşlukta durur.
