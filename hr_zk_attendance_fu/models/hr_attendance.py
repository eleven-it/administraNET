from odoo import models, fields

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    address_id = fields.Many2one('res.partner', string='Work Location')
