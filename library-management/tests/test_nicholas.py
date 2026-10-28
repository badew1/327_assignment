"""Meaningful API tests for Nicholas's assigned library features."""


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
