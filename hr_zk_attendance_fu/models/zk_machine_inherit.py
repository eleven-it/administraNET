# hr_zk_attendance_fu/models/zk_machine_inherit.py

from odoo import models, api, _
from datetime import datetime
import pytz
import logging

_logger = logging.getLogger(__name__)

class ZkMachineInherit(models.Model):
    _inherit = 'zk.machine'

    @api.model
    def _convert_timestamp(self, ts):
        atten_time = datetime.strptime(ts.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
        local_tz = pytz.timezone(self.env.user.partner_id.tz or 'GMT')
        local_dt = local_tz.localize(atten_time, is_dst=None)
        utc_dt = local_dt.astimezone(pytz.utc)
        final_dt = datetime.strptime(utc_dt.strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S")
        return final_dt.strftime("%Y-%m-%d %H:%M:%S")

    def download_attendance(self):
        _logger.info("++++++++++++Download Attendance FU Overridden (FORCED CONTEXT) ++++++++++++++++")
        return super(ZkMachineInherit, self.with_context(from_download_attendance=True)).download_attendance()

    def action_clean_attendance_data(self):
        # Solo para administradores
        if not self.env.user.has_group('base.group_system'):
            raise self.env['res.users'].UserError(_('Solo los administradores pueden ejecutar esta acción.'))
        self.env['hr.attendance'].sudo().search([]).unlink()
        self.env['zk.machine.attendance'].sudo().search([]).unlink()
        self.env['hr.attendance.inconsistency'].sudo().search([]).unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Limpieza completada'),
                'message': _('Se han eliminado todas las asistencias, fichadas e inconsistencias.'),
                'type': 'success',
                'sticky': False,
            }
        }
