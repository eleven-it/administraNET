from odoo import models, fields

class ZkMachineAttendanceExtension(models.Model):
    _inherit = 'zk.machine.attendance'

    attendance_type = fields.Selection(selection_add=[
        ('16', 'Desconocido')
    ])
