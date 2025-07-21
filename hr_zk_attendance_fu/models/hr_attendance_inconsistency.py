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
        ('resolved', 'Resuelto'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='pending', required=True)
    machine_id = fields.Many2one('zk.machine', string='Máquina Biométrica')
    building_id = fields.Many2one('hr.zk.building', string='Edificio')
    suggestion = fields.Text(string='Correction Suggestion', translate=True)

    def action_marcar_corregido(self):
        """Mark the inconsistency as resolved and try to apply the correction to the attendance record."""
        self.ensure_one()
        attendance = self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee_id.id),
            ('check_in', '=', self.check_in),
            ('building_id', '=', self.building_id.id),
        ], limit=1)
        try:
            if attendance:
                # If the inconsistency is due to missing check_out, update it
                if not attendance.check_out and self.check_out:
                    attendance.check_out = self.check_out
                # If the inconsistency is due to missing check_in, update it
                if not attendance.check_in and self.check_in:
                    attendance.check_in = self.check_in
                # Optionally, handle other correction scenarios here
                self.suggestion = _('The inconsistency was resolved and the attendance record was updated.')
            else:
                # Crear nuevo registro de asistencia si no existe
                vals = {
                    'employee_id': self.employee_id.id,
                    'check_in': self.check_in,
                    'check_out': self.check_out,
                    'building_id': self.building_id.id,
                }
                self.env['hr.attendance'].create(vals)
                self.suggestion = _('The inconsistency was resolved and a new attendance record was created.')
            self.state = 'resolved'
        except Exception as e:
            self.suggestion = _('Error while resolving inconsistency: %(error)s. Please review the attendance record and correct manually. Employee: %(empl)s, Building: %(building)s, Check-in: %(checkin)s, Check-out: %(checkout)s.') % {
                'error': str(e),
                'empl': self.employee_id.name,
                'building': self.building_id.display_name,
                'checkin': self.check_in,
                'checkout': self.check_out
            }
            self.state = 'pending'
        return True

    def action_marcar_cancelado(self):
        """Marcar la inconsistencia como cancelada por error de registración."""
        self.ensure_one()
        self.state = 'cancelled'
        self.suggestion = _('La inconsistencia fue cancelada por error de registración. No se realizará ninguna acción sobre las asistencias.')
        return True 