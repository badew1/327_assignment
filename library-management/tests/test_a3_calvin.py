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


def test_ui_checkout_creates_loan_and_decrements_copies(client):
    book, member = _book(client), _member(client)
    r = client.post("/ui/loans", data={"book_id": book["id"], "member_id": member["id"]})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/ui/loans")
    assert len(store.loans) == 1
    assert store.books[book["id"]].available_copies == 0


def test_ui_checkout_unknown_book_creates_no_loan(client):
    member = _member(client)
    r = client.post("/ui/loans", data={"book_id": 999, "member_id": member["id"]})
    assert r.status_code == 302
    assert len(store.loans) == 0


def test_ui_return_sets_return_date_and_restores_copy(client):
    book, member = _book(client), _member(client)
    client.post("/ui/loans", data={"book_id": book["id"], "member_id": member["id"]})
    loan_id = next(iter(store.loans))
    r = client.post(f"/ui/loans/{loan_id}/return")
    assert r.status_code == 302
    assert store.loans[loan_id].return_date is not None
    assert store.books[book["id"]].available_copies == 1


def test_ui_return_twice_does_not_restore_a_second_copy(client):
    book, member = _book(client), _member(client)
    client.post("/ui/loans", data={"book_id": book["id"], "member_id": member["id"]})
    loan_id = next(iter(store.loans))
    client.post(f"/ui/loans/{loan_id}/return")
    client.post(f"/ui/loans/{loan_id}/return")
    assert store.books[book["id"]].available_copies == 1


def test_ui_return_unknown_loan_changes_nothing(client):
    book = _book(client)
    r = client.post("/ui/loans/999/return")
    assert r.status_code == 302
    assert store.books[book["id"]].available_copies == 1


from datetime import date, timedelta
from unittest.mock import patch


def _overdue_loan(client):
    book = client.post(
        "/books",
        json={"title": "Dune", "author": "Frank Herbert", "isbn": "9780441013593", "total_copies": 1},
    ).get_json()
    member = client.post(
        "/members", json={"name": "Sam Lee", "email": "sam@example.com"}
    ).get_json()
    loan = client.post(
        "/loans", json={"book_id": book["id"], "member_id": member["id"]}
    ).get_json()
    store.loans[loan["id"]].due_date = date.today() - timedelta(days=3)
    return loan["id"], book["id"], member["id"]


def test_reminder_failed_notification_returns_200_with_notified_false(client, monkeypatch):
    loan_id, book_id, _ = _overdue_loan(client)
    monkeypatch.setattr(
        "app.routes.loans.send_notification", lambda recipient, subject, message: False
    )

    response = client.post(f"/loans/{loan_id}/reminder")

    assert response.status_code == 200
    assert response.get_json() == {"loan_id": loan_id, "notified": False}
    assert store.loans[loan_id].return_date is None
    assert store.books[book_id].available_copies == 0