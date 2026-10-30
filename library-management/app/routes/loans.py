from datetime import date, timedelta

from flask import Blueprint, jsonify, request

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
    data = request.get_json()
    book = store.books.get(data["book_id"])
    if book is None:
        return jsonify({"error": "Book not found"}), 404

    book.available_copies -= 1

    loan_id = store.next_id("loan")
    loan = Loan(
        id=loan_id,
        book_id=data["book_id"],
        member_id=data["member_id"],
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


@loans_bp.route("/<int:loan_id>/fine", methods=["GET"])
def get_fine(loan_id):
    loan = store.loans.get(loan_id)
    if loan is None:
        return jsonify({"error": "Loan not found"}), 404

    # BUG: always uses date.today() as the end date, even when the book has
    # already been returned. A returned loan should use loan.return_date so
    # the fine is fixed at the moment of return — but that line is missing here.
    end_date = date.today()
    days_overdue = max(0, (end_date - loan.due_date).days)
    fine_amount = round(days_overdue * FINE_PER_DAY, 2)

    return jsonify({"loan_id": loan_id, "fine_amount": fine_amount})
