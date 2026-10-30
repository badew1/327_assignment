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

# renew a loan
def test_renew_extends_due_date_by_loan_period(client):
    book, member = make_book(client), make_member(client)
    loan = checkout(client, book["id"], member["id"]).get_json()
    old_due = date.fromisoformat(loan["due_date"])

    r = client.put(f"/loans/{loan['id']}/renew")
    assert r.status_code == 200
    new_due = date.fromisoformat(r.get_json()["due_date"])
    assert new_due == old_due + timedelta(days=LOAN_PERIOD_DAYS)

    stored = client.get("/loans").get_json()[0]
    assert stored["due_date"] == new_due.isoformat()


def test_renew_twice_extends_cumulatively(client):
    book, member = make_book(client), make_member(client)
    loan = checkout(client, book["id"], member["id"]).get_json()
    old_due = date.fromisoformat(loan["due_date"])
    client.put(f"/loans/{loan['id']}/renew")
    r = client.put(f"/loans/{loan['id']}/renew")
    assert date.fromisoformat(r.get_json()["due_date"]) == \
        old_due + timedelta(days=2 * LOAN_PERIOD_DAYS)


def test_renew_returned_loan_rejected(client):
    book, member = make_book(client), make_member(client)
    loan = checkout(client, book["id"], member["id"]).get_json()
    client.put(f"/loans/{loan['id']}/return")
    assert client.put(f"/loans/{loan['id']}/renew").status_code == 400


def test_renew_nonexistent_loan_returns_404(client):
    assert client.put("/loans/999/renew").status_code == 404


# overdue fine
def test_fine_is_zero_when_not_overdue(client):
    book, member = make_book(client), make_member(client)
    loan = checkout(client, book["id"], member["id"]).get_json()
    r = client.get(f"/loans/{loan['id']}/fine")
    assert r.status_code == 200
    assert r.get_json()["loan_id"] == loan["id"]
    assert r.get_json()["fine_amount"] == 0


def test_fine_is_025_per_day_overdue(client):
    book, member = make_book(client), make_member(client)
    loan = checkout(client, book["id"], member["id"]).get_json()
    store.loans[loan["id"]].due_date = date.today() - timedelta(days=10)
    assert client.get(f"/loans/{loan['id']}/fine").get_json()["fine_amount"] == 2.5


def test_fine_nonexistent_loan_returns_404(client):
    assert client.get("/loans/999/fine").status_code == 404


def test_fine_stops_growing_after_return(client):
    """Expected to FAIL: fine uses today, not return_date (defect 4)."""
    book, member = make_book(client), make_member(client)
    loan = checkout(client, book["id"], member["id"]).get_json()
    stored = store.loans[loan["id"]]
    stored.due_date = date.today() - timedelta(days=10)
    stored.return_date = date.today() - timedelta(days=6)   # returned 4 days late

    fine = client.get(f"/loans/{loan['id']}/fine").get_json()["fine_amount"]
    assert fine == 1.0   # 4 days * 0.25; observed 2.5




# reservations
def test_list_reservations_empty_initially(client):
    assert client.get("/reservations").get_json() == []


def test_create_reservation_returns_fields_and_is_listed(client):
    book, member = make_book(client), make_member(client)
    r = client.post("/reservations", json={
        "book_id": book["id"], "member_id": member["id"]})
    assert r.status_code == 201
    res = r.get_json()
    assert res["book_id"] == book["id"]
    assert res["member_id"] == member["id"]
    assert res["fulfilled"] is False

    listed = client.get("/reservations").get_json()
    assert [x["id"] for x in listed] == [res["id"]]


def test_create_reservation_nonexistent_book_or_member_404(client):
    book, member = make_book(client), make_member(client)
    assert client.post("/reservations", json={
        "book_id": 999, "member_id": member["id"]}).status_code == 404
    assert client.post("/reservations", json={
        "book_id": book["id"], "member_id": 999}).status_code == 404
    assert client.get("/reservations").get_json() == []


def test_filter_reservations_by_book_and_member(client):
    b1, b2 = make_book(client, "One"), make_book(client, "Two")
    m1, m2 = make_member(client, "Alice"), make_member(client, "Bob")
    client.post("/reservations", json={"book_id": b1["id"], "member_id": m1["id"]})
    client.post("/reservations", json={"book_id": b2["id"], "member_id": m2["id"]})

    by_book = client.get(f"/reservations?book_id={b2['id']}").get_json()
    assert len(by_book) == 1 and by_book[0]["book_id"] == b2["id"]

    by_member = client.get(f"/reservations?member_id={m1['id']}").get_json()
    assert len(by_member) == 1 and by_member[0]["member_id"] == m1["id"]


def test_reserved_book_cannot_be_checked_out_by_another_member(client):
    """Expected to FAIL: checkout ignores reservations (defect 5, R3)."""
    book = make_book(client, total_copies=1)
    alice, bob, carol = (make_member(client, n) for n in ("Alice", "Bob", "Carol"))
    loan = checkout(client, book["id"], alice["id"]).get_json()
    client.post("/reservations", json={"book_id": book["id"], "member_id": bob["id"]})
    client.put(f"/loans/{loan['id']}/return")

    r = checkout(client, book["id"], carol["id"])   # Bob is next in line
    assert r.status_code in (400, 409)


    # checkout validation enhancement
def test_rejected_checkout_leaves_state_unchanged(client):
    book = make_book(client, total_copies=1)
    r = checkout(client, book["id"], 999)
    assert r.status_code == 404
    assert available(client, book["id"]) == 1
    assert client.get("/loans").get_json() == []


def test_checkout_non_integer_ids_return_400(client):
    book = make_book(client)
    member = make_member(client)
    r = client.post("/loans", json={"book_id": "abc", "member_id": member["id"]})
    assert r.status_code == 400
    r = client.post("/loans", json={"book_id": book["id"], "member_id": None})
    assert r.status_code == 400
    assert client.get("/loans").get_json() == []


def test_two_copy_book_allows_two_checkouts_then_rejects_third(client):
    book = make_book(client, total_copies=2)
    m1, m2, m3 = (make_member(client, n) for n in ("Alice", "Bob", "Carol"))
    assert checkout(client, book["id"], m1["id"]).status_code == 201
    assert checkout(client, book["id"], m2["id"]).status_code == 201
    assert available(client, book["id"]) == 0

    r = checkout(client, book["id"], m3["id"])
    assert r.status_code == 400
    assert available(client, book["id"]) == 0
    assert len(client.get("/loans").get_json()) == 2