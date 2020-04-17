from odoo import fields, models
from odoo.addons import decimal_precision as dp


class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Book'
    _order = 'date_release desc, name'
    _rec_name = 'short_name'
    name = fields.Char(string='Title', required=True)
    short_name = fields.Char(string='Short Title', size=100, translate=True)
    date_release = fields.Date(string='Release Date')
    date_updated = fields.Datetime('Last Updated')
    author_ids = fields.Many2many('res.partner', string='Authors')
    notes = fields.Text('Internal notes')
    state = fields.Selection(
        [('draft', 'Not Available'),
         ('available', 'Available'),
         ('lost', 'Lost')],
        'State')
    description = fields.Html(string='Description', sanitize=True, strip_style=False, translate=False)
    out_of_print = fields.Boolean('Out of print?')
    pages = fields.Integer(
        string='Number of pages',
        default=0,
        help='Total book page count',
        groups='base.group_user',
        states={'cancel': [('readonly', True)]},
        copy=True,
        index=False,
        readonly=False,
        required=False,
        company_depends=False,
    )
    reader_rating = fields.Float('Reader Average Rating', (14, 4))
    cost_price = fields.Float('Book Cost', dp.get_precision('Book Price'))

