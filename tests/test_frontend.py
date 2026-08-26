def test_frontend_index_served(anon_client):
    response = anon_client.get("/app/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Habit Tracker" in response.text


def test_frontend_redirects_without_trailing_slash(anon_client):
    response = anon_client.get("/app", follow_redirects=False)
    assert response.status_code in (301, 307, 308)


def test_frontend_admin_page_served(anon_client):
    response = anon_client.get("/app/admin.html")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Yönetici Paneli" in response.text
