def test_home(client, db):
    r = client.get("/")
    assert r.status_code == 200


def test_block(client, admin_user):
    client.login(username="admin", password="password")
    r = client.get("/block/")
    assert r.status_code == 200
