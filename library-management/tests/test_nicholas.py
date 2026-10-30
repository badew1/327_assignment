"""Meaningful API tests for Nicholas's assigned library features."""

from datetime import date, timedelta


def create_book(client, **overrides):
    """Create a book with valid defaults and return its JSON representation."""
    payload = {
        "title": "The Left Hand of Darkness",
        "author": "Ursula K. Le Guin",
        "isbn": "978-0441478125",
        "total_copies": 2,
    }
    payload.update(overrides)
    response = client.post("/books", json=payload)
    assert response.status_code == 201
    return response.get_json()


def create_member(client, **overrides):
    """Create a member with valid defaults and return its JSON representation."""
    payload = {
        "name": "Maya Chen",
        "email": "maya.chen@example.com",
    }
    payload.update(overrides)
    response = client.post("/members", json=payload)
    assert response.status_code == 201
    return response.get_json()


def test_create_book_persists_complete_record(client):
    """Creating a book returns all fields and stores it for later retrieval."""
    created = create_book(client)

    assert created == {
        "id": 1,
        "title": "The Left Hand of Darkness",
        "author": "Ursula K. Le Guin",
        "isbn": "978-0441478125",
        "total_copies": 2,
        "available_copies": 2,
    }

    get_response = client.get("/books/1")
    assert get_response.status_code == 200
    assert get_response.get_json() == created

    list_response = client.get("/books")
    assert list_response.status_code == 200
    assert list_response.get_json() == [created]


def test_book_search_matches_title_and_author_case_insensitively(client):
    """Book search finds title/author substrings and excludes unrelated books."""
    left_hand = create_book(client)
    parable = create_book(
        client,
        title="Parable of the Sower",
        author="Octavia E. Butler",
        isbn="978-0446675505",
    )

    title_response = client.get("/books?search=left HAND")
    assert title_response.status_code == 200
    assert title_response.get_json() == [left_hand]

    author_response = client.get("/books?search=butler")
    assert author_response.status_code == 200
    assert author_response.get_json() == [parable]

    no_match_response = client.get("/books?search=asimov")
    assert no_match_response.status_code == 200
    assert no_match_response.get_json() == []


def test_update_book_changes_requested_fields_and_preserves_others(client):
    """A partial update persists while omitted fields keep their prior values."""
    original = create_book(client)

    update_response = client.put(
        "/books/1",
        json={"title": "The Dispossessed", "total_copies": 4},
    )
    assert update_response.status_code == 200
    updated = update_response.get_json()
    assert updated == {
        **original,
        "title": "The Dispossessed",
        "total_copies": 4,
    }

    get_response = client.get("/books/1")
    assert get_response.status_code == 200
    assert get_response.get_json() == updated


def test_zero_copy_book_is_recorded_as_unavailable_boundary(client):
    """The zero-copy boundary produces a book with no available copies."""
    created = create_book(client, total_copies=0)

    assert created["total_copies"] == 0
    assert created["available_copies"] == 0


def test_delete_book_removes_it_from_subsequent_reads(client):
    """Deleting an existing book removes both the detail and list representation."""
    create_book(client)

    delete_response = client.delete("/books/1")
    assert delete_response.status_code == 204
    assert delete_response.data == b""

    assert client.get("/books/1").status_code == 404
    assert client.get("/books").get_json() == []


def test_unknown_book_operations_return_not_found_without_changing_state(client):
    """Get, update, and delete reject an ID that is not present."""
    get_response = client.get("/books/999")
    update_response = client.put("/books/999", json={"title": "Missing"})
    delete_response = client.delete("/books/999")

    assert get_response.status_code == 404
    assert get_response.get_json() == {"error": "Book not found"}
    assert update_response.status_code == 404
    assert update_response.get_json() == {"error": "Book not found"}
    assert delete_response.status_code == 404
    assert delete_response.get_json() == {"error": "Book not found"}
    assert client.get("/books").get_json() == []


def test_create_member_persists_complete_record(client):
    """Creating a member stores identity fields and the membership date."""
    created = create_member(client)

    assert created == {
        "id": 1,
        "name": "Maya Chen",
        "email": "maya.chen@example.com",
        "membership_date": date.today().isoformat(),
    }

    get_response = client.get("/members/1")
    assert get_response.status_code == 200
    assert get_response.get_json() == created

    list_response = client.get("/members")
    assert list_response.status_code == 200
    assert list_response.get_json() == [created]


def test_multiple_members_receive_distinct_sequential_ids(client):
    """Server-assigned IDs remain unique as multiple members are registered."""
    first = create_member(client)
    second = create_member(
        client,
        name="Jordan Patel",
        email="jordan.patel@example.com",
    )

    assert first["id"] == 1
    assert second["id"] == 2
    assert first["id"] != second["id"]
    assert client.get("/members").get_json() == [first, second]


def test_update_member_changes_requested_field_and_preserves_others(client):
    """A partial member update persists without replacing omitted fields."""
    original = create_member(client)

    update_response = client.put(
        "/members/1",
        json={"email": "maya.updated@example.com"},
    )
    assert update_response.status_code == 200
    updated = update_response.get_json()
    assert updated == {
        **original,
        "email": "maya.updated@example.com",
    }

    get_response = client.get("/members/1")
    assert get_response.status_code == 200
    assert get_response.get_json() == updated


def test_delete_member_removes_it_from_subsequent_reads(client):
    """Deleting a member removes both the detail and list representation."""
    create_member(client)

    delete_response = client.delete("/members/1")
    assert delete_response.status_code == 204
    assert delete_response.data == b""

    assert client.get("/members/1").status_code == 404
    assert client.get("/members").get_json() == []


def test_unknown_member_operations_return_not_found_without_changing_state(client):
    """Get, update, and delete reject a member ID that is not present."""
    get_response = client.get("/members/999")
    update_response = client.put("/members/999", json={"name": "Missing"})
    delete_response = client.delete("/members/999")

    assert get_response.status_code == 404
    assert get_response.get_json() == {"error": "Member not found"}
    assert update_response.status_code == 404
    assert update_response.get_json() == {"error": "Member not found"}
    assert delete_response.status_code == 404
    assert delete_response.get_json() == {"error": "Member not found"}
    assert client.get("/members").get_json() == []


def test_checkout_and_return_updates_loan_and_book_state(client):
    """A complete loan workflow updates dates and available-copy counts."""
    create_book(client)
    create_member(client)

    checkout_response = client.post(
        "/loans",
        json={"book_id": 1, "member_id": 1},
    )
    assert checkout_response.status_code == 201
    loan = checkout_response.get_json()
    assert loan == {
        "id": 1,
        "book_id": 1,
        "member_id": 1,
        "loan_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=14)).isoformat(),
        "return_date": None,
    }
    assert client.get("/books/1").get_json()["available_copies"] == 1
    assert client.get("/loans").get_json() == [loan]

    return_response = client.put("/loans/1/return")
    assert return_response.status_code == 200
    returned_loan = return_response.get_json()
    assert returned_loan["return_date"] == date.today().isoformat()
    assert client.get("/books/1").get_json()["available_copies"] == 2

    repeated_return = client.put("/loans/1/return")
    assert repeated_return.status_code == 400
    assert repeated_return.get_json() == {"error": "Loan already returned"}
    assert client.get("/books/1").get_json()["available_copies"] == 2


def test_checkout_unknown_book_returns_not_found_without_creating_loan(client):
    """Checkout rejects a missing book and leaves the loan collection empty."""
    create_member(client)

    response = client.post(
        "/loans",
        json={"book_id": 999, "member_id": 1},
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "Book not found"}
    assert client.get("/loans").get_json() == []


def test_checkout_rejects_book_when_no_copies_are_available(client):
    """A one-copy book cannot have two simultaneous active loans."""
    create_book(client, total_copies=1)
    create_member(client)
    create_member(
        client,
        name="Jordan Patel",
        email="jordan.patel@example.com",
    )
    first_checkout = client.post(
        "/loans",
        json={"book_id": 1, "member_id": 1},
    )
    assert first_checkout.status_code == 201
    assert client.get("/books/1").get_json()["available_copies"] == 0

    second_checkout = client.post(
        "/loans",
        json={"book_id": 1, "member_id": 2},
    )

    observed = (
        second_checkout.status_code,
        client.get("/books/1").get_json()["available_copies"],
        len(client.get("/loans").get_json()),
    )
    assert observed == (400, 0, 1)


def test_checkout_rejects_unknown_member_without_changing_book_state(client):
    """A loan must reference an existing member before availability is changed."""
    create_book(client, total_copies=1)

    response = client.post(
        "/loans",
        json={"book_id": 1, "member_id": 999},
    )

    observed = (
        response.status_code,
        client.get("/books/1").get_json()["available_copies"],
        client.get("/loans").get_json(),
    )
    assert observed == (404, 1, [])
