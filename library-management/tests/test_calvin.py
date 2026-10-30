from datetime import date, timedelta

from app import store
from app.models.loan import Loan, LOAN_PERIOD_DAYS


# ---------- helpers ----------
def make_book(client, title="Clean Code", total_copies=1):
    r = client.post("/books", json={
        "title": title, "author": "Author", "isbn": "111",
        "total_copies": total_copies})
    assert r.status_code == 201
    return r.get_json()


def make_member(client, name="Alice"):
    r = client.post("/members", json={
        "name": name, "email": f"{name.lower()}@example.com"})
    assert r.status_code == 201
    return r.get_json()


def checkout(client, book_id, member_id):
    return client.post("/loans", json={"book_id": book_id, "member_id": member_id})


def available(client, book_id):
    return client.get(f"/books/{book_id}").get_json()["available_copies"]


# view all loans 
def test_list_loans_empty_initially(client):
    r = client.get("/loans")
    assert r.status_code == 200
    assert r.get_json() == []


def test_list_loans_shows_created_loan_with_borrower_and_due_date(client):
    book, member = make_book(client), make_member(client)
    created = checkout(client, book["id"], member["id"]).get_json()

    loans = client.get("/loans").get_json()
    assert len(loans) == 1
    assert loans[0]["id"] == created["id"]
    assert loans[0]["book_id"] == book["id"]
    assert loans[0]["member_id"] == member["id"]
    assert loans[0]["due_date"] is not None
    assert loans[0]["return_date"] is None


#filter loans 
def test_filter_loans_by_book_id(client):
    b1, b2 = make_book(client, "One"), make_book(client, "Two")
    m = make_member(client)
    checkout(client, b1["id"], m["id"])
    checkout(client, b2["id"], m["id"])

    loans = client.get(f"/loans?book_id={b2['id']}").get_json()
    assert len(loans) == 1
    assert loans[0]["book_id"] == b2["id"]


def test_filter_loans_by_member_id(client):
    """Expected to FAIL: the route filters l.book_id == member_id (defect 1)."""
    b1, b2 = make_book(client, "One"), make_book(client, "Two")
    m1, m2 = make_member(client, "Alice"), make_member(client, "Bob")
    checkout(client, b1["id"], m2["id"])   # loan 1: book 1, member 2
    checkout(client, b2["id"], m1["id"])   # loan 2: book 2, member 1

    loans = client.get(f"/loans?member_id={m2['id']}").get_json()
    assert len(loans) == 1
    assert loans[0]["member_id"] == m2["id"]


def test_filter_loans_no_match_returns_empty_list(client):
    book, member = make_book(client), make_member(client)
    checkout(client, book["id"], member["id"])
    assert client.get("/loans?book_id=999").get_json() == []

# check out a book 
def test_checkout_creates_loan_with_default_due_date(client):
    book, member = make_book(client), make_member(client)
    r = checkout(client, book["id"], member["id"])
    assert r.status_code == 201
    loan = r.get_json()
    assert loan["book_id"] == book["id"]
    assert loan["member_id"] == member["id"]
    assert loan["return_date"] is None
    assert loan["due_date"] == Loan.default_due_date().isoformat()


def test_checkout_decrements_available_copies(client):
    book, member = make_book(client, total_copies=2), make_member(client)
    checkout(client, book["id"], member["id"])
    assert available(client, book["id"]) == 1


def test_checkout_nonexistent_book_returns_404(client):
    member = make_member(client)
    r = checkout(client, 999, member["id"])
    assert r.status_code == 404
    assert client.get("/loans").get_json() == []


def test_checkout_nonexistent_member_rejected(client):
    """Expected to FAIL: no member validation, orphan loan created (defect 3)."""
    book = make_book(client)
    r = checkout(client, book["id"], 999)
    assert r.status_code == 404
    assert client.get("/loans").get_json() == []


def test_checkout_rejected_when_no_copies_available(client):
    """Expected to FAIL: second checkout of a 1-copy book succeeds (defect 2, R36)."""
    book = make_book(client, total_copies=1)
    m1, m2 = make_member(client, "Alice"), make_member(client, "Bob")
    assert checkout(client, book["id"], m1["id"]).status_code == 201

    r = checkout(client, book["id"], m2["id"])
    assert r.status_code in (400, 409)
    assert available(client, book["id"]) == 0          # not -1
    assert len(client.get("/loans").get_json()) == 1   # no second loan


def test_checkout_missing_fields_returns_400(client):
    """Expected to FAIL/ERROR: missing member_id raises KeyError (defect 6)."""
    book = make_book(client)
    r = client.post("/loans", json={"book_id": book["id"]})
    assert r.status_code == 400


#return a loan 
def test_return_sets_return_date_and_restores_copies(client):
    book, member = make_book(client), make_member(client)
    loan = checkout(client, book["id"], member["id"]).get_json()
    assert available(client, book["id"]) == 0

    r = client.put(f"/loans/{loan['id']}/return")
    assert r.status_code == 200
    assert r.get_json()["return_date"] == date.today().isoformat()
    assert available(client, book["id"]) == 1

    stored = client.get("/loans").get_json()[0]
    assert stored["return_date"] == date.today().isoformat()


def test_return_twice_rejected_and_copies_not_double_restored(client):
    book, member = make_book(client), make_member(client)
    loan = checkout(client, book["id"], member["id"]).get_json()
    client.put(f"/loans/{loan['id']}/return")

    r = client.put(f"/loans/{loan['id']}/return")
    assert r.status_code == 400
    assert available(client, book["id"]) == 1


def test_return_nonexistent_loan_returns_404(client):
    assert client.put("/loans/999/return").status_code == 404


def test_checkout_return_checkout_cycle(client):
    """Chained workflow: a returned copy can be borrowed again."""
    book = make_book(client, total_copies=1)
    m1, m2 = make_member(client, "Alice"), make_member(client, "Bob")
    loan = checkout(client, book["id"], m1["id"]).get_json()
    client.put(f"/loans/{loan['id']}/return")

    r = checkout(client, book["id"], m2["id"])
    assert r.status_code == 201
    assert available(client, book["id"]) == 0