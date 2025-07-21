# -*- coding: utf-8 -*-
from odoo import models, fields, _

class HrZkBuilding(models.Model):
    _name = 'hr.zk.building'
    _description = 'Edificio para Asistencias Biométricas'
    _order = 'code, name'

    code = fields.Char(string='Código', required=True, index=True)
    name = fields.Char(string='Nombre', required=True)
    street = fields.Char(string='Dirección')
    responsible_id = fields.Many2one('res.partner', string='Responsable de Mantenimiento', required=False)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', _('El código del edificio debe ser único.')),
        ('name_uniq', 'unique(name)', _('El nombre del edificio debe ser único.')),
    ] 