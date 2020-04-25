from odoo import fields, models, api
from odoo.addons import decimal_precision as dp
from datetime import timedelta
from odoo.exceptions import UserError
from odoo.tools.translate import _
import logging

logger = logging.getLogger(__name__)


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
    isbn = fields.Char('ISBN')
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
    manager_remarks = fields.Text('Manager Remarks')
    old_edition = fields.Many2one('library.book', string='Old Edition')

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

    @api.multi
    def name_get(self):
        result = []
        for book in self:
            authors = book.author_ids.mapped('name')  # Здесь почему-то mapped не возвращает список всех авторов,
            name = '%s (%s)' % (book.name, ', '.join(authors))  # возвращается только последний
            result.append((book.id, name))
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

    @api.model
    def create(self, values):
        if not self.user_has_groups('initmodule.group_librarian'):
            if 'manager_remarks' in values:
                raise UserError('You are not allowed to modify manager_remarks')
        return super().create(values)

    @api.model
    def _name_search(self, name='', args=None, operator='ilike',  # Не совсем ясно
                     limit=100, name_get_uid=None):
        print("===", args)
        args = [] if args is None else args.copy()
        if not (name == '' and operator == 'ilike'):
            args += ['|', '|',
                     ('name', operator, name),
                     ('isbn', operator, name),
                     ('author_ids.name', operator, name)
                     ]
            books_ids = self.search(args).ids
            return self.browse(books_ids).name_get()
        return super(LibraryBook, self)._name_search(
            name=name, args=args, operator=operator,
            limit=limit, name_get_uid=name_get_uid)

    @api.multi
    def write(self, values):
        if not self.user_has_groups('initmodule.group_librarian'):
            if 'manager_remarks' in values:
                raise UserError('You are not allowed to modify manager_remarks')
        return super().write(values)

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

    @api.multi
    def change_update_date(self):
        self.ensure_one()
        self.date_updated = fields.Datetime.today()

    @api.multi
    def find_book(self):
        domain = [
            '|',
            '&', ('name', 'ilike', 'FullLongTitle'), ('category_id.name', 'ilike', 'FirstCateg'),
            '&', ('name', 'ilike', 'Book Name2'), ('category_id.name', 'ilike', 'Category Name2')
        ]
        books = self.search(domain)
        logger.info(f'Books find {books}')
        return True

    @api.model
    def get_all_library_members(self):
        library_member_model = self.env['library.member']  # This is an empty recordset of model library.member
        return library_member_model.search([])

    @api.model
    def books_with_multiple_authors(self, all_books):
        def predicate(book):
            if len(book.author_ids) > 1:
                return True
            return all_books.filtered(predicate)

    def filter_books(self):
        all_books = self.search([])
        filtered_books = self.books_with_multiple_authors(all_books)
        logger.info(f'Filtered books {filtered_books}')

    def create_categories(self):
        categ1 = {
            'name': 'Child category 1',
            'description': 'Description for child 1'
        }
        categ2 = {
            'name': 'Child category 2',
            'description': 'Description for child 2'
        }
        parent_category = {
            'name': 'Parent category',
            'email': 'Description for parent category',
            'child_ids': [
                (0, 0, categ1),
                (0, 0, categ2),
            ]
        }
        # Total 3 records (1 parent and 2 child) will be craeted in library.book.category model
        record = self.env['library.book.category'].create(parent_category)
        return True

    def mapped_books(self):
        all_books = self.search([])
        books_authors = self.get_author_names(all_books)
        logger.info('Books Authors: %s', books_authors)

    @api.model
    def get_author_names(self, all_books):
        return all_books.mapped('author_ids.name')

    def sort_books(self):
        all_books = self.search([])
        books_sorted = self.sort_books_by_date(all_books)
        logger.info(f'Before {all_books}')
        logger.info(f'After {books_sorted}')

    @api.model
    def sort_books_by_date(self, books):
        return books.sorted(key='date_release')


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
