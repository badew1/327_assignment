from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from notification_service import send_notification

from app import store
from app.models.loan import Loan, LOAN_PERIOD_DAYS

FINE_PER_DAY = 0.25  # dollars charged per day overdue

loans_bp = Blueprint("loans", __name__, url_prefix="/loans")


@loans_bp.route("", methods=["GET"])
def list_loans():
    results = list(store.loans.values())

    try:
        member_id = _parse_optional_id("member_id")
        book_id = _parse_optional_id("book_id")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    status = request.args.get("status", "all").lower()
    if status not in {"all", "active", "returned"}:
        return jsonify(
            {"error": "status must be one of: all, active, returned"}
        ), 400

    if member_id is not None:
        results = [loan for loan in results if loan.member_id == member_id]
    if book_id is not None:
        results = [loan for loan in results if loan.book_id == book_id]
    if status == "active":
        results = [loan for loan in results if loan.return_date is None]
    elif status == "returned":
        results = [loan for loan in results if loan.return_date is not None]

    return jsonify([loan.to_dict() for loan in results])


def _parse_optional_id(name):
    raw_value = request.args.get(name)
    if raw_value is None:
        return None

    try:
        return int(raw_value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be an integer") from error


@loans_bp.route("", methods=["POST"])
def checkout_book():
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")
    member_id = data.get("member_id")
    if not isinstance(book_id, int) or not isinstance(member_id, int):
        return jsonify({"error": "book_id and member_id are required integers"}), 400

    book = store.books.get(book_id)
    if book is None:
        return jsonify({"error": "Book not found"}), 404
    if store.members.get(member_id) is None:
        return jsonify({"error": "Member not found"}), 404
    if book.available_copies < 1:
        return jsonify({"error": "No copies available"}), 400

    book.available_copies -= 1
    loan_id = store.next_id("loan")
    loan = Loan(
        id=loan_id,
        book_id=book_id,
        member_id=member_id,
        due_date=Loan.default_due_date(),
    )
    store.loans[loan_id] = loan
    return jsonify(loan.to_dict()), 201


@loans_bp.route("/<int:loan_id>/return", methods=["PUT"])
def return_book(loan_id):
    loan = store.loans.get(loan_id)
    if loan is None:
        return jsonify({"error": "Loan not found"}), 404
    if loan.return_date is not None:
        return jsonify({"error": "Loan already returned"}), 400

    loan.return_date = date.today()
    book = store.books.get(loan.book_id)
    book.available_copies += 1

    return jsonify(loan.to_dict())


@loans_bp.route("/<int:loan_id>/renew", methods=["PUT"])
def renew_loan(loan_id):
    loan = store.loans.get(loan_id)
    if loan is None:
        return jsonify({"error": "Loan not found"}), 404
    if loan.return_date is not None:
        return jsonify({"error": "Loan already returned"}), 400

    loan.due_date = loan.due_date + timedelta(days=LOAN_PERIOD_DAYS)
    return jsonify(loan.to_dict())


@loans_bp.route("/<int:loan_id>/reminder", methods=["POST"])
def send_overdue_reminder(loan_id):
    loan = store.loans.get(loan_id)
    if loan is None:
        return jsonify({"error": "Loan not found"}), 404
    if loan.return_date is not None:
        return jsonify({"error": "Loan already returned"}), 400
    if loan.due_date >= date.today():
        return jsonify({"error": "Loan is not overdue"}), 400

    member = store.members.get(loan.member_id)
    if member is None:
        return jsonify({"error": "Member not found"}), 404
    book = store.books.get(loan.book_id)
    if book is None:
        return jsonify({"error": "Book not found"}), 404

    sent = send_notification(
        member.email,
        "[City Library] Overdue reminder",
        f'Hi {member.name}, "{book.title}" was due on '
        f"{loan.due_date.isoformat()}. Please return it to the library.",
    )
    return jsonify({"loan_id": loan.id, "notified": sent})


@loans_bp.route("/<int:loan_id>/fine", methods=["GET"])
def get_fine(loan_id):
    loan = store.loans.get(loan_id)
    if loan is None:
        return jsonify({"error": "Loan not found"}), 404
    end_date = loan.return_date or date.today()
    days_overdue = max(0, (end_date - loan.due_date).days)
    fine_amount = round(days_overdue * FINE_PER_DAY, 2)

    return jsonify({"loan_id": loan_id, "fine_amount": fine_amount})
