# Library Management System (LMS)

A small Flask REST API for tracking books, members, and loans. Data is stored
**in memory** (plain Python objects, no database) and is reset every time the
app restarts — this project is meant to run before you've covered databases.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

The API runs at `http://127.0.0.1:5000`.

## Web UI

Open `http://127.0.0.1:5000/` in a browser for a basic HTML front end (plain
forms and tables, no JavaScript) to add/delete books and members, and check
books in/out:

| Page | Path |
|---|---|
| Home | `/` |
| Books | `/ui/books` |
| Members | `/ui/members` |
| Loans | `/ui/loans` |

This UI is separate from the JSON API below — it's there so you can see the
app working without a REST client, and calls the same in-memory store.

## Entities

- **Book**: `id, title, author, isbn, total_copies, available_copies`
- **Member**: `id, name, email, membership_date`
- **Loan**: `id, book_id, member_id, loan_date, due_date, return_date`

## JSON API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/books` | List all books |
| POST | `/books` | Create a book |
| GET | `/books/<id>` | Get one book |
| PUT | `/books/<id>` | Update a book |
| DELETE | `/books/<id>` | Delete a book |
| GET | `/members` | List all members |
| POST | `/members` | Create a member |
| GET | `/members/<id>` | Get one member |
| PUT | `/members/<id>` | Update a member |
| DELETE | `/members/<id>` | Delete a member |
| POST | `/loans` | Check out a book (`book_id`, `member_id`) Returns 201 with the loan. Returns 400 if either ID is missing or not an integer, or if no copies are available. Returns 404 if the book or member does not exist. A rejected request changes no data. |
| PUT | `/loans/<id>/return` | Return a loaned book |
| POST | `/loans/<id>/reminder` | Request an overdue reminder. Returns 200 with `loan_id` and `notified`. Returns 400 if the loan has been returned or its due date is today or later. Returns 404 if the loan, member, or book does not exist. |
| GET | `/loans?member_id=&book_id=&status=` | Filter loans by member, book, and history status (`all`, `active`, or `returned`); invalid filters return 400 |

Reminders are requested through the endpoint; they are not sent automatically.
An overdue, unreturned loan triggers a notification to the member's email address
with the subject `[City Library] Overdue reminder` and a message containing their
name, book title, and due date. If the service returns `False`, the endpoint still
returns 200 with `notified: false`. Sending a reminder does not change the loan,
book availability, or member record. Repeated valid requests attempt another send.

The provided `notification_service.py` sits beside `run.py` and simulates delivery
in memory without sending email or making network calls. The customization adds
`[City Library]` to subjects that do not already have that prefix. Its
`send_notification(recipient, subject, message) -> bool` interface is unchanged.

## Tests

```bash
python -m pytest
```

`tests/test_a3_nicholas.py` covers the home, book, and member pages, plus the
overdue reminder success path. A stub returns `True` to check the response and
unchanged application records. A mock checks the exact recipient, subject,
message, and call count, as well as the response and unchanged records. Both
replace `app.routes.loans.send_notification`, so the simulator is not called.
