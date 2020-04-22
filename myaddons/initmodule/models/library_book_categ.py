from odoo import fields, models, api


class BookCategory(models.Model):
    _name = 'library.book.category'
    name = fields.Char('Category')
    description = fields.Text('Description')

    _parent_store = True
    _parent_name = 'parent_id'
    parent_path = fields.Char(index=True)

    parent_id = fields.Many2one(
        'library.book.category',
        string='Parent Category',
        ondelete='restrict',
        index=True
    )
    child_ids = fields.One2many(
        'library.book.category',
        'parent_id',
        string='Child Categories'
    )

    @api.constrains
    def _check_hierarchy(self):
        if not self._check_recursion():
            raise models.ValidationError('Error! You cannot create recursive categories.')
