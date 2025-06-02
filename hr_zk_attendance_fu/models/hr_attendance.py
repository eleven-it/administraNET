from odoo import models, fields

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    address_id = fields.Many2one('res.partner', string='Work Location')
    zk_machine_id = fields.Many2one(
        'zk.machine',
        string='Biometric Device',
        help='Biometric device from which the attendance was downloaded',
        readonly=True
    )
