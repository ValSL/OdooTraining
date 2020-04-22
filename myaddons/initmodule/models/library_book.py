from odoo import fields, models, api
from odoo.addons import decimal_precision as dp
from datetime import timedelta
from odoo.exceptions import UserError
from odoo.tools.translate import _


class BaseArchive(models.AbstractModel):
    _name = 'base.archive'
    active = fields.Boolean(default=True)

    def do_archive(self):
        for record in self:
            record.active = not record.active


class LibraryBook(models.Model):
    _name = 'library.book'
    _inherit = ['base.archive']
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
         ('borrowed', 'Borrowed'),
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

    ref_doc_id = fields.Reference(selection='_referencable_models', string='Reference Document')

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

    @api.model
    def _referencable_models(self):
        models = self.env['ir.model'].search([('field_id.name', '=', 'message_ids')])
        return [(x.model, x.name) for x in models]

    @api.model
    def is_allowed_transition(self, old_state, new_state):
        allowed = [
            ('draft', 'available'),
            ('available', 'borrowed'),
            ('borrowed', 'available'),
            ('available', 'lost'),
            ('borrowed', 'lost'),
            ('lost', 'available')
        ]
        return (old_state, new_state) in allowed

    @api.multi
    def change_state(self, new_state):
        for book in self:
            if self.is_allowed_transition(book.state, new_state):
                book.state = new_state
            else:
                msg = _(f'Moving from {book.state} to {new_state} is not allowed')
                raise UserError(msg)

    @api.multi
    def make_available(self):
        self.change_state('available')

    @api.multi
    def make_borrowed(self):
        self.change_state('borrowed')

    @api.multi
    def make_lost(self):
        self.change_state('lost')

    @api.model
    def get_all_library_members(self):
        library_member_model = self.env['library.member']  # This is an empty recordset of model library.member
        return library_member_model.search([])


class ResPartner(models.Model):
    _inherit = 'res.partner'
    _order = 'name'
    publisher_book_ids = fields.One2many('library.book', 'publisher_id', string='Published Books')
    author_book_ids = fields.Many2many('library.book', string='Authored Books')
    count_books = fields.Integer('Number of Authored Books', compute='_compute_count_books')

    @api.depends('author_book_ids')
    def _compute_count_books(self):
        for r in self:
            r.count_books = len(r.author_book_ids)


class LibraryMember(models.Model):
    _name = 'library.member'
    partner_id = fields.Many2one('res.partner', ondelete='cascade', delegate=True)
    date_start = fields.Date('Member Since')
    date_end = fields.Date('Termination Date')
    member_number = fields.Char()
    date_of_birth = fields.Date('Date of birth')
