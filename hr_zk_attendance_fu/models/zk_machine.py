from odoo import models, fields, _
from odoo.exceptions import UserError
import pytz
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class ZkMachine(models.Model):
    _inherit = 'zk.machine'

    building_id = fields.Many2one('hr.zk.building', string='Edificio', required=False)

    def _convert_timestamp(self, ts):
        atten_time = datetime.strptime(ts.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
        local_tz = pytz.timezone(self.env.user.partner_id.tz or 'GMT')
        local_dt = local_tz.localize(atten_time, is_dst=None)
        utc_dt = local_dt.astimezone(pytz.utc)
        final_dt = datetime.strptime(utc_dt.strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S")
        return fields.Datetime.to_string(final_dt)

def download_attendance(self):
    _logger.info("++++++++++++Download Attendance Ejecutado++++++++++++++++++++++")
    zk_attendance_model = self.env['zk.machine.attendance']
    hr_attendance_model = self.env['hr.attendance']
    count_downloaded = 0
    skipped_invalid_types = {}
    skipped_invalid_checkouts = []

    from zk import ZK
    zk = ZK(self.name, port=self.port_no, timeout=15, password=0, force_udp=False, ommit_ping=True)

    valid_attendance_types = ['1', '2', '3', '4', '15']

    with self.open_connection(zk) as conn:
        if not conn:
            raise UserError(_('Unable to connect, check parameters and network.'))

        users = conn.get_users()
        records = conn.get_attendance()

        if not records:
            return

        employees = {str(e.device_id): e for e in self.env['hr.employee'].search([('device_id', '!=', False)])}
        user_dict = {str(u.user_id): u for u in users} if users else {}

        for rec in records:
            time = self._convert_timestamp(rec.timestamp)
            uid = str(rec.user_id)
            emp = employees.get(uid)

            if not emp and uid in user_dict:
                emp = self.env['hr.employee'].create({
                    'device_id': uid,
                    'name': user_dict[uid].name or "Empleado " + uid,
                })
                employees[uid] = emp

            if not emp:
                continue

            att_type = str(rec.status)
            if att_type not in valid_attendance_types:
                skipped_invalid_types[att_type] = skipped_invalid_types.get(att_type, 0) + 1
                continue

            if zk_attendance_model.search([('device_id', '=', uid), ('punching_time', '=', time)], limit=1):
                continue

            zk_attendance_model.create({
                'employee_id': emp.id,
                'device_id': uid,
                'attendance_type': att_type,
                'punch_type': str(rec.punch),
                'punching_time': time,
                'address_id': self.address_id.id,
            })

            if rec.punch == 0:  # check-in
                if not hr_attendance_model.search([
                    ('employee_id', '=', emp.id),
                    ('check_out', '=', False),
                    ('address_id', '=', self.address_id.id)
                ], limit=1):
                    hr_attendance_model.with_context(from_download_attendance=True).create({
                        'employee_id': emp.id,
                        'check_in': time,
                        'address_id': self.address_id.id,
                        'zk_machine_id': self.id,
                    })

            elif rec.punch == 1:  # check-out
                open_att = hr_attendance_model.search([
                    ('employee_id', '=', emp.id),
                    ('check_out', '=', False),
                    ('address_id', '=', self.address_id.id)
                ], order='check_in desc', limit=1)

                if open_att:
                    open_att.ensure_one()
                    open_att.flush()
                    if open_att.check_in and time > open_att.check_in:
                        try:
                            open_att.write({
                                'check_out': time,
                                'zk_machine_id': self.id,
                            })
                        except Exception as e:
                            _logger.error(
                                f"❌ Error al registrar salida para {emp.name} (ID {emp.id}) "
                                f"en {self.address_id.display_name}. Entrada: {open_att.check_in}, "
                                f"Salida: {time}. Error: {str(e)}"
                            )
                    else:
                        skipped_invalid_checkouts.append(f"{emp.name} ({uid})")
                        _logger.warning(
                            f"⚠️ Check-out inválido ignorado para {emp.name} (ID {emp.id}) "
                            f"en {self.address_id.display_name}. Salida: {time} anterior a entrada: {open_att.check_in}"
                        )

            count_downloaded += 1

    # Mensaje resumen visual
    msg = _('%d registros descargados.') % count_downloaded

    if skipped_invalid_types:
        msg += '<br/><b>Tipos inválidos ignorados:</b><ul>'
        for t, n in skipped_invalid_types.items():
            msg += f"<li>Tipo {t}: {n} registros</li>"
        msg += "</ul>"

    if skipped_invalid_checkouts:
        msg += '<b>Salidas inválidas (no se registraron):</b><ul>'
        for name in skipped_invalid_checkouts:
            msg += f"<li>{name}</li>"
        msg += "</ul>"

    _logger.info("✔️ Download Attendance Finalizado. %d registros procesados.", count_downloaded)

    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'title': _('Download Attendance'),
            'message': msg,
            'sticky': False,
            'type': 'warning' if skipped_invalid_types or skipped_invalid_checkouts else 'success',
        },
    }
