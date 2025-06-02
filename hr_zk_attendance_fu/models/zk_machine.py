from odoo import models, fields, _
from odoo.exceptions import UserError
import pytz
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class ZkMachine(models.Model):
    _inherit = 'zk.machine'

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

        from zk import ZK
        zk = ZK(self.name, port=self.port_no, timeout=15, password=0, force_udp=False, ommit_ping=True)

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

                if zk_attendance_model.search([('device_id', '=', uid), ('punching_time', '=', time)], limit=1):
                    continue

                zk_attendance_model.create({
                    'employee_id': emp.id,
                    'device_id': uid,
                    'attendance_type': str(rec.status),
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
                        hr_attendance_model.create({
                            'employee_id': emp.id,
                            'check_in': time,
                            'address_id': self.address_id.id,
                        })
                elif rec.punch == 1:  # check-out
                    open_att = hr_attendance_model.search([
                        ('employee_id', '=', emp.id),
                        ('check_out', '=', False),
                        ('address_id', '=', self.address_id.id)
                    ], order='check_in desc', limit=1)
                    if open_att:
                        open_att.write({'check_out': time})
