from odoo import fields, models, api
from datetime import timedelta


class LibraryBook(models.Model):
    _inherit = 'library.book'

    date_return = fields.Date('Date tot return')

    def make_borrowed(self):
        day_to_borrow = self.category_id.max_borrow_days or 10
        self.date_return = fields.Date.today() + timedelta(days=day_to_borrow)
        return super().make_borrowed()

    def make_available(self):
        self.date_return = False
        return super().make_available()


class LibraryBookCategory(models.Model):
    _inherit = 'library.book.category'

    max_borrow_days = fields.Integer(
        'Maximum borrow days',
        help="For how many days book can be borrowed",
        default=10)
