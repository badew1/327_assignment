from app import store


def _book(client, copies=1):
    return client.post("/books", json={
        "title": "T", "author": "A", "isbn": "1", "total_copies": copies}).get_json()


def _member(client):
    return client.post("/members", json={
        "name": "Alice", "email": "alice@example.com"}).get_json()


def test_home_page_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Library Management System" in r.data


def test_loans_page_lists_existing_loans(client):
    book, member = _book(client), _member(client)
    client.post("/loans", json={"book_id": book["id"], "member_id": member["id"]})
    r = client.get("/ui/loans")
    assert r.status_code == 200
    assert len(store.loans) == 1