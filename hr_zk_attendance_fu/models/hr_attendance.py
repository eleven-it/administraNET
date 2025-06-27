# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import pytz
import logging

_logger = logging.getLogger(__name__)

try:
    from zk import ZK, const
except ImportError:
    _logger.error("Pyzk library not installed. Please run: pip install pyzk")


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    building_id = fields.Many2one("hr.zk.building", string="Building", required=False)

    attendance_inconsistency_count = fields.Integer(
        string="Inconsistencias",
        compute="_compute_inconsistency_count"
    )

    @api.constrains('check_in', 'check_out', 'employee_id', 'building_id')
    def _check_validity(self):
        for attendance in self:
            # Permitir solo una asistencia abierta por empleado y edificio
            open_attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('building_id', '=', attendance.building_id.id),
                ('check_out', '=', False),
                ('id', '!=', attendance.id),
            ], limit=1)
            if open_attendances:
                raise ValidationError(_(
                    'No se puede crear una nuevo registro de asistencia para %(empl_name)s, el empleado no ha registrado su salida desde %(check_in)s en el edificio %(building)s',
                    empl_name=attendance.employee_id.name,
                    check_in=open_attendances.check_in,
                    building=attendance.building_id.display_name
                ))

    def _compute_inconsistency_count(self):
        for rec in self:
            rec.attendance_inconsistency_count = self.env['hr.attendance.inconsistency'].search_count([
                ('employee_id', '=', rec.employee_id.id),
                ('check_in', '=', rec.check_in),
                ('check_out', '=', rec.check_out),
            ])

    def _migrate_address_to_building(self):
        """Método para migrar address_id a building_id"""
        _logger = logging.getLogger(__name__)
        count = 0
        attendances = self.search([('building_id', '=', False), ('address_id', '!=', False)])
        for att in attendances:
            building = self.env['hr.zk.building'].search([('responsible_id', '=', att.address_id.id)], limit=1)
            if building:
                att.building_id = building.id
                count += 1
        _logger.info('Migración address_id -> building_id completada. Registros actualizados: %s', count)
        return True

    @api.model
    def download_attendance(self):
        zk_machine_model = self.env['zk.machine']
        zk_attendance_model = self.env['zk.machine.attendance'] if 'zk.machine.attendance' in self.env else None
        hr_employee_model = self.env['hr.employee']

        machines = zk_machine_model.search([('state', '=', 'confirmed')])
        total_downloaded = 0

        for machine in machines:
            _logger.info("Connecting to device %s:%s", machine.name, machine.port_no)

            try:
                zk = ZK(machine.name, port=machine.port_no, timeout=20, password=0, force_udp=False, ommit_ping=True)
                conn = zk.connect()
                conn.disable_device()
                users = conn.get_users()
                records = conn.get_attendance()
            except Exception as e:
                _logger.warning("Failed to connect or fetch data from device %s: %s", machine.name, str(e))
                continue

            if not records:
                _logger.info("No attendance records found for device %s", machine.name)
                conn.enable_device()
                conn.disconnect()
                continue

            # Crear índices rápidos
            user_dict = {str(u.user_id): u for u in users}
            employees = hr_employee_model.search([('device_id', '!=', False)])
            emp_dict = {str(e.device_id): e for e in employees}

            for rec in records:
                timestamp = rec.timestamp
                device_uid = str(rec.user_id)

                # Convertir a UTC con timezone del usuario
                local_tz = pytz.timezone(self.env.user.tz or 'UTC')
                local_dt = local_tz.localize(timestamp)
                atten_time = local_dt.astimezone(pytz.utc)

                employee = emp_dict.get(device_uid)
                if not employee and device_uid in user_dict:
                    user_data = user_dict[device_uid]
                    employee = hr_employee_model.create({
                        'name': user_data.name or f"Employee {device_uid}",
                        'device_id': device_uid
                    })
                    emp_dict[device_uid] = employee
                    _logger.info("Created new employee: %s", employee.name)

                if not employee:
                    _logger.warning("Employee with device_id %s not found and cannot be created", device_uid)
                    continue

                # Registrar fichada en zk.machine.attendance si el modelo existe
                if zk_attendance_model:
                    existing_zk = zk_attendance_model.search([
                        ('device_id', '=', device_uid),
                        ('punching_time', '=', atten_time)
                    ], limit=1)
                    if not existing_zk:
                        zk_attendance_model.create({
                            'employee_id': employee.id,
                            'device_id': device_uid,
                            'attendance_type': str(rec.status),
                            'punch_type': str(rec.punch),
                            'punching_time': atten_time,
                            'address_id': machine.address_id.id,
                        })

                # Validar si ya hay una entrada abierta en este edificio
                existing_attendance = self.search([
                    ('employee_id', '=', employee.id),
                    ('check_out', '=', False),
                    ('building_id', '=', machine.building_id.id)
                ], limit=1)

                if rec.punch == 0:  # Check-in
                    if not existing_attendance:
                        self.create({
                            'employee_id': employee.id,
                            'check_in': atten_time,
                            'building_id': machine.building_id.id,
                        })
                        total_downloaded += 1
                elif rec.punch == 1:  # Check-out
                    if existing_attendance and atten_time > existing_attendance.check_in:
                        existing_attendance.write({'check_out': atten_time})
                        total_downloaded += 1

            conn.enable_device()
            conn.disconnect()
            _logger.info("Processed device %s. Records downloaded: %d", machine.name, total_downloaded)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Download Attendance'),
                'message': _('%d attendance records were processed.') % total_downloaded,
                'sticky': False,
            },
        }
