"""Nicholas's Assignment 3 coverage tests for home, book, and member pages."""

from datetime import date

import pytest


def test_home_page_links_to_management_pages_without_changing_state(client):
    response = client.get("/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Library Management System" in page
    for path in ("/ui/books", "/ui/members", "/ui/loans"):
        assert f'href="{path}"' in page
    for path in ("/books", "/members", "/loans"):
        assert client.get(path).get_json() == []


@pytest.mark.parametrize(
    "page_path, heading, form_label, api_path",
    [
        ("/ui/books", "Books", "Add a Book", "/books"),
        ("/ui/members", "Members", "Add a Member", "/members"),
    ],
)
def test_empty_management_page_renders_form_without_creating_records(
    client, page_path, heading, form_label, api_path
):
    response = client.get(page_path)

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert f"<h1>{heading}</h1>" in page
    assert form_label in page
    assert f'action="{page_path}"' in page
    assert client.get(api_path).get_json() == []


def test_book_form_creates_one_copy_book_and_redirects_to_listing(client):
    response = client.post(
        "/ui/books",
        data={
            "title": "A Wizard of Earthsea",
            "author": "Ursula K. Le Guin",
            "isbn": "9780547773742",
            "total_copies": "1",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/ui/books"
    assert client.get("/books").get_json() == [
        {
            "id": 1,
            "title": "A Wizard of Earthsea",
            "author": "Ursula K. Le Guin",
            "isbn": "9780547773742",
            "total_copies": 1,
            "available_copies": 1,
        }
    ]
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    for value in ("A Wizard of Earthsea", "Ursula K. Le Guin", "9780547773742"):
        assert value in page


def test_book_delete_form_removes_only_selected_book(client):
    books = []
    for title in ("Remove This Book", "Keep This Book"):
        response = client.post(
            "/books", json={"title": title, "author": "Test Author", "isbn": title}
        )
        assert response.status_code == 201
        books.append(response.get_json())

    response = client.post(f"/ui/books/{books[0]['id']}/delete")

    assert response.status_code == 302
    assert response.headers["Location"] == "/ui/books"
    assert client.get("/books").get_json() == [books[1]]
    page = client.get("/ui/books").get_data(as_text=True)
    assert "Remove This Book" not in page
    assert "Keep This Book" in page


def test_member_form_persists_identity_and_displays_membership_date(client):
    response = client.post(
        "/ui/members", data={"name": "Maya Chen", "email": "maya@example.com"}
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/ui/members"
    today = date.today().isoformat()
    assert client.get("/members").get_json() == [
        {"id": 1, "name": "Maya Chen", "email": "maya@example.com", "membership_date": today}
    ]
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    for value in ("Maya Chen", "maya@example.com", today):
        assert value in page


def test_member_delete_form_removes_only_selected_member(client):
    members = []
    for name in ("Remove This Member", "Keep This Member"):
        response = client.post(
            "/members", json={"name": name, "email": "member@example.com"}
        )
        assert response.status_code == 201
        members.append(response.get_json())

    response = client.post(f"/ui/members/{members[0]['id']}/delete")

    assert response.status_code == 302
    assert response.headers["Location"] == "/ui/members"
    assert client.get("/members").get_json() == [members[1]]
    page = client.get("/ui/members").get_data(as_text=True)
    assert "Remove This Member" not in page
    assert "Keep This Member" in page


@pytest.mark.parametrize(
    "api_path, page_path, payload",
    [
        ("/books", "/ui/books", {"title": "Keep Me", "author": "Author", "isbn": "keep"}),
        ("/members", "/ui/members", {"name": "Keep Me", "email": "keep@example.com"}),
    ],
)
def test_delete_form_for_missing_record_redirects_without_changing_existing_records(
    client, api_path, page_path, payload
):
    created = client.post(api_path, json=payload)
    assert created.status_code == 201

    response = client.post(f"{page_path}/999/delete")

    assert response.status_code == 302
    assert response.headers["Location"] == page_path
    assert client.get(api_path).get_json() == [created.get_json()]
    assert "Keep Me" in client.get(page_path).get_data(as_text=True)
