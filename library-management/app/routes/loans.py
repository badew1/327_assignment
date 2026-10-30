from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from app import store
from app.models.loan import Loan, LOAN_PERIOD_DAYS

FINE_PER_DAY = 0.25  # dollars charged per day overdue

loans_bp = Blueprint("loans", __name__, url_prefix="/loans")


@loans_bp.route("", methods=["GET"])
def list_loans():
    results = list(store.loans.values())
    member_id = request.args.get("member_id", type=int)
    book_id = request.args.get("book_id", type=int)
    if member_id is not None:
        results = [l for l in results if l.book_id == member_id]
    if book_id is not None:
        results = [l for l in results if l.book_id == book_id]
    return jsonify([l.to_dict() for l in results])


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
