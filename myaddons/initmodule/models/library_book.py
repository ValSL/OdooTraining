from odoo import fields, models, api
from odoo.addons import decimal_precision as dp
from datetime import timedelta


class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Book'
    _order = 'date_release desc, name'
    _rec_name = 'short_name'
    name = fields.Char(string='Title', required=True)
    short_name = fields.Char(string='Short Title', size=100, translate=True, index=True)
    date_release = fields.Date(string='Release Date')
    date_updated = fields.Datetime('Last Updated')
    author_ids = fields.Many2many('res.partner', string='Authors')
    notes = fields.Text('Internal notes')
    state = fields.Selection(
        [('draft', 'Not Available'),
         ('available', 'Available'),
         ('lost', 'Lost')],
        'State', default='draft')
    description = fields.Html(string='Description', sanitize=True, strip_style=False, translate=False)
    cover = fields.Binary('Book Cover')
    out_of_print = fields.Boolean('Out of print?')
    pages = fields.Integer(
        string='Number of pages',
        default=0,
        help='Total book page count',
        groups='base.group_user',
        states={'lost': [('readonly', True)]},
        copy=True,
        index=False,
        readonly=False,
        required=False,
        company_depends=False,
    )
    reader_rating = fields.Float('Reader Average Rating', (14, 4))
    cost_price = fields.Float('Book Cost', dp.get_precision('Book Price'))
    currency_id = fields.Many2one('res.currency', string='Currency')
    retail_price = fields.Monetary('Retail Price')
    publisher_id = fields.Many2one('res.partner', string='Publisher', ondelete='set null', context={}, domain=[])
    publisher_city = fields.Char(string='Publiser City', related='publisher_id.city', readonly=True)
    category_id = fields.Many2one('library.book.category')

    age_days = fields.Float(
        string='Days Since Release',
        compute='_compute_age',
        inverse='_inverce_age',
        search='_search_age',
        store=False,
        compute_sudo=False
    )

    @api.depends('date_release')
    def _compute_age(self):
        today = fields.Date.today()
        for book in self.filtered('date_release'):
            delta = today - book.date_release
            book.age_days = delta.days

    def _inverce_age(self):
        today = fields.Date.today()
        for book in self.filtered('date_release'):
            d = today - timedelta(days=book.age_days)
            book.date_release = d

    def _search_age(self, operator, value):
        today = fields.Date.today()
        value_days = timedelta(days=value)
        value_date = today - value_days
        # convert the operator:
        # book with age > value have a date < value_date
        operator_map = {
            '>': '<', '>=': '<=',
            '<': '>', '<=': '>=',
        }
        new_op = operator_map.get(operator, operator)
        return [('date_release', new_op, value_date)]

    _sql_constraints = [
        ('name_uniq', 'UNIQUE (name)', 'Book title must be unique'),
        ('positive_page', 'CHECK(pages>0)', 'No of pages must be positive')
    ]

    def name_get(self):
        """ This method used to customize display name of the record """
        result = []
        for record in self:
            rec_name = "%s (%s)" % (record.name, record.date_release)
            result.append((record.id, rec_name))
        return result

    @api.constrains('date_release')
    def _check_release_date(self):
        for r in self:
            if r.date_release > fields.Date.today():
                raise models.ValidationError('Release date must be in the past')


class ResPartner(models.Model):
    _inherit = 'res.partner'
    publisher_book_ids = fields.One2many('library.book', 'publisher_id', string='Published Books')
    author_book_ids = fields.Many2many('library.book', string='Authored Books')
