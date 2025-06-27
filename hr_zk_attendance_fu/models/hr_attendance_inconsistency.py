# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class HrAttendanceInconsistency(models.Model):
    _name = 'hr.attendance.inconsistency'
    _description = 'Inconsistencias de Asistencia'
    _order = 'create_date desc'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    check_in = fields.Datetime(string='Hora de Entrada')
    check_out = fields.Datetime(string='Hora de Salida')
    motivo = fields.Text(string='Motivo de la Inconsistencia', required=True)
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('resolved', 'Resuelto')
    ], string='Estado', default='pending', required=True)
    machine_id = fields.Many2one('zk.machine', string='Máquina Biométrica')
    building_id = fields.Many2one('hr.zk.building', string='Edificio')

    def action_marcar_corregido(self):
        """Marca la inconsistencia como resuelta"""
        self.ensure_one()
        self.state = 'resolved'
        return True 